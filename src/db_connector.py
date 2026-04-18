"""MySQL database connection manager for the HIS production system."""
from __future__ import annotations

import os
from typing import Any

import pandas as pd
import pymysql

from src.utils import setup_logger

logger = setup_logger("db_connector")


class DBConnector:
    """Manage MySQL connections to the HIS production database.

    Database password is read from the DB_PASSWORD environment variable
    to avoid storing credentials in config files or source code.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        db_cfg = config.get("database", {})
        self.host = db_cfg.get("host", "")
        self.user = db_cfg.get("user", "")
        self.password = os.getenv("DB_PASSWORD", db_cfg.get("password", ""))
        self.database = db_cfg.get("database", "")
        self.charset = db_cfg.get("charset", "utf8mb4")
        self._conn: pymysql.Connection | None = None

    def is_configured(self) -> bool:
        """Check whether the minimum connection parameters are set."""
        return bool(self.host and self.user and self.password and self.database)

    def get_connection(self) -> pymysql.Connection:
        """Return an open connection, creating one if needed."""
        if self._conn is None or not self._conn.open:
            if not self.is_configured():
                raise RuntimeError(
                    "Database not configured. Set DB_PASSWORD env var and check config/settings.yaml [database] section."
                )
            self._conn = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                charset=self.charset,
                connect_timeout=15,
                read_timeout=300,
                cursorclass=pymysql.cursors.DictCursor,
            )
            logger.info("Connected to %s@%s/%s", self.user, self.host, self.database)
        return self._conn

    def execute_query(self, sql: str, params: tuple | None = None) -> pd.DataFrame:
        """Execute a SELECT query and return results as a DataFrame."""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        except pymysql.Error as exc:
            logger.error("Query failed: %s — %s", sql[:200], exc)
            raise

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and self._conn.open:
            self._conn.close()
            self._conn = None
            logger.info("Database connection closed")
