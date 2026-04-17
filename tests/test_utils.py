from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.utils import ensure_dir, load_config, setup_logger


def test_load_config_success() -> None:
    config = load_config("config/settings.yaml")

    assert config["model"]["name"] == "shibing624/text2vec-base-chinese-sentence"
    assert config["index"]["top_k"] == 5
    assert config["thresholds"]["auto_map"] == pytest.approx(0.95)


def test_load_config_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.yaml"

    with pytest.raises(FileNotFoundError):
        load_config(str(missing_path))


def test_ensure_dir_creates_nested(tmp_path: Path) -> None:
    nested_dir = tmp_path / "nested" / "child" / "leaf"

    ensure_dir(nested_dir)

    assert nested_dir.exists()
    assert nested_dir.is_dir()


def test_ensure_dir_existing(tmp_path: Path) -> None:
    existing_dir = tmp_path / "already" / "exists"
    existing_dir.mkdir(parents=True)

    ensure_dir(existing_dir)

    assert existing_dir.exists()
    assert existing_dir.is_dir()


def test_setup_logger_uses_expected_format() -> None:
    logger = setup_logger("test-utils-logger")

    assert logger.level == logging.INFO
    assert logger.handlers

    formatter = logger.handlers[0].formatter
    assert formatter is not None
    assert "%(asctime)s" in formatter._fmt
    assert "%(name)s" in formatter._fmt
    assert "%(levelname)s" in formatter._fmt
