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

    def normalize(self, unit: str | None) -> str:
        normalized = str(unit or "").strip()
        return self.EQUIVALENTS.get(normalized, normalized)

    def is_convertible(self, from_unit: str, to_unit: str, standard_code: str | None = None) -> bool:
        source = self.normalize(from_unit)
        target = self.normalize(to_unit)
        if source == target:
            return True
        return standard_code == self.GLUCOSE_CODE and {source, target} == {"mg/dL", "mmol/L"}

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
        if standard_code == self.GLUCOSE_CODE and source == "mg/dL" and target == "mmol/L":
            return value / 18.0
        if standard_code == self.GLUCOSE_CODE and source == "mmol/L" and target == "mg/dL":
            return value * 18.0
        raise ValueError(f"Unsupported unit conversion: {source} -> {target}")
