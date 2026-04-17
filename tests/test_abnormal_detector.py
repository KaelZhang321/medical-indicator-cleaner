from __future__ import annotations

from src.abnormal_detector import derive_abnormal_status


def test_source_flag_normal() -> None:
    result = derive_abnormal_status(10.0, None, None, "0")

    assert result == {
        "abnormal_flag_source": "0",
        "is_abnormal": False,
        "abnormal_direction": None,
    }


def test_source_flag_low() -> None:
    result = derive_abnormal_status(10.0, None, None, "1")

    assert result["is_abnormal"] is True
    assert result["abnormal_direction"] == "low"


def test_derive_high_from_reference() -> None:
    result = derive_abnormal_status(124.0, 90.0, 120.0, None)

    assert result["is_abnormal"] is True
    assert result["abnormal_direction"] == "high"


def test_derive_normal_from_reference() -> None:
    result = derive_abnormal_status(110.0, 90.0, 120.0, None)

    assert result["is_abnormal"] is False
    assert result["abnormal_direction"] is None
