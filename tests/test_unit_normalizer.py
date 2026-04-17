from __future__ import annotations

from src.unit_normalizer import UnitNormalizer


def test_normalize_equivalent_unit() -> None:
    assert UnitNormalizer().normalize("ng/ml") == "ng/mL"


def test_normalize_chinese_second() -> None:
    assert UnitNormalizer().normalize("秒") == "s"


def test_convert_mg_dl_to_mmol_l_for_glucose() -> None:
    value = UnitNormalizer().convert(90.0, "mg/dL", "mmol/L", standard_code="HY-XT-001")

    assert round(value, 2) == 5.0


def test_is_convertible() -> None:
    normalizer = UnitNormalizer()

    assert normalizer.is_convertible("mg/dL", "mmol/L", standard_code="HY-XT-001") is True
    assert normalizer.is_convertible("kg", "mmol/L", standard_code="HY-XT-001") is False
