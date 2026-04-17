from __future__ import annotations

import math


def derive_abnormal_status(
    numeric_value: float | None,
    ref_min: float | None,
    ref_max: float | None,
    source_flag: str | None,
) -> dict[str, str | bool | None]:
    """Derive abnormal state from HIS flag first, then numeric reference bounds."""
    if isinstance(source_flag, float) and math.isnan(source_flag):
        normalized_flag = None
    else:
        normalized_flag = None if source_flag in {None, "", "nan", "None"} else str(source_flag)
    if normalized_flag == "0":
        return {"abnormal_flag_source": "0", "is_abnormal": False, "abnormal_direction": None}
    if normalized_flag == "1":
        return {"abnormal_flag_source": "1", "is_abnormal": True, "abnormal_direction": "low"}
    if normalized_flag == "2":
        return {"abnormal_flag_source": "2", "is_abnormal": True, "abnormal_direction": "high"}

    if numeric_value is None:
        return {"abnormal_flag_source": normalized_flag, "is_abnormal": None, "abnormal_direction": None}
    if ref_min is not None and numeric_value < ref_min:
        return {"abnormal_flag_source": normalized_flag, "is_abnormal": True, "abnormal_direction": "low"}
    if ref_max is not None and numeric_value > ref_max:
        return {"abnormal_flag_source": normalized_flag, "is_abnormal": True, "abnormal_direction": "high"}
    if ref_min is not None or ref_max is not None:
        return {"abnormal_flag_source": normalized_flag, "is_abnormal": False, "abnormal_direction": None}
    return {"abnormal_flag_source": normalized_flag, "is_abnormal": None, "abnormal_direction": None}
