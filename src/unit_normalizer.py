from __future__ import annotations


class UnitNormalizer:
    """Normalize common medical units and handle limited safe conversions."""

    EQUIVALENTS = {
        "ng/ml": "ng/mL",
        "ng/ML": "ng/mL",
        "u/ml": "U/mL",
        "U/ml": "U/mL",
        "U/ML": "U/mL",
        "iu/ml": "IU/mL",
        "IU/ml": "IU/mL",
        "umol/L": "μmol/L",
        "μmol/l": "μmol/L",
        "秒": "s",
        "次/分": "bpm",
        "kg/m²": "kg/平方米",
    }

    GLUCOSE_CODE = "HY-XT-001"
    CONVERSION_FACTORS = {
        ("HY-XT-001", "mg/dL", "mmol/L"): 1 / 18.0,
        ("HY-XT-001", "mmol/L", "mg/dL"): 18.0,
        ("HY-BZ-001", "mg/dL", "mmol/L"): 1 / 38.67,
        ("HY-BZ-001", "mmol/L", "mg/dL"): 38.67,
        ("HY-BZ-002", "mg/dL", "mmol/L"): 1 / 88.57,
        ("HY-BZ-002", "mmol/L", "mg/dL"): 88.57,
        ("HY-SG-002", "mg/dL", "μmol/L"): 88.4,
        ("HY-SG-002", "μmol/L", "mg/dL"): 1 / 88.4,
    }

    def normalize(self, unit: str | None) -> str:
        normalized = str(unit or "").strip()
        return self.EQUIVALENTS.get(normalized, normalized)

    def is_convertible(self, from_unit: str, to_unit: str, standard_code: str | None = None) -> bool:
        source = self.normalize(from_unit)
        target = self.normalize(to_unit)
        if source == target:
            return True
        return (standard_code, source, target) in self.CONVERSION_FACTORS

    def convert(
        self,
        value: float,
        from_unit: str,
        to_unit: str,
        standard_code: str | None = None,
    ) -> float:
        source = self.normalize(from_unit)
        target = self.normalize(to_unit)
        if source == target:
            return value
        factor = self.CONVERSION_FACTORS.get((standard_code, source, target))
        if factor is not None:
            return value * factor
        raise ValueError(f"Unsupported unit conversion: {source} -> {target}")
