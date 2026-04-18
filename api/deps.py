"""Shared dependencies for FastAPI routes."""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db_connector import DBConnector
from src.db_data_source import DBDataSource
from src.dict_manager import DictManager
from src.l1_rule_cleaner import L1RuleCleaner
from src.risk_analyzer import calc_deviation, classify_quadrant
from src.utils import load_config

import pandas as pd


@lru_cache()
def get_config() -> dict[str, Any]:
    return load_config("config/settings.yaml")


@lru_cache()
def get_dict_manager() -> DictManager:
    config = get_config()
    return DictManager(config["data"]["standard_dict"], config["data"]["alias_dict"])


@lru_cache()
def get_cleaner() -> L1RuleCleaner:
    return L1RuleCleaner(get_dict_manager())


def get_db() -> DBConnector:
    """Create a DB connection (not cached — caller must close)."""
    return DBConnector(get_config())


def get_data_source(db: DBConnector) -> DBDataSource:
    return DBDataSource(db)


def get_risk_weights() -> pd.DataFrame:
    """Load risk weights, return empty DataFrame if file missing."""
    path = get_config()["data"].get("risk_weight", "data/risk_weight.csv")
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except FileNotFoundError:
        return pd.DataFrame(columns=["standard_code", "risk_weight", "risk_category"])


def get_reference_ranges() -> pd.DataFrame:
    """Load reference ranges, return empty DataFrame if file missing."""
    path = get_config()["data"].get("reference_range_standard", "data/reference_range_standard.csv")
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
        for col in ["ref_min", "ref_max", "age_min", "age_max"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except FileNotFoundError:
        return pd.DataFrame()
