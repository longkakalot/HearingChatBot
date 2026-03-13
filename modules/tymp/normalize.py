# modules/tymp/normalize.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .constants import (
    MAX_COMPLIANCE_ML,
    MAX_ECV_ML,
    MAX_GRADIENT_DAPA,
    MAX_PRESSURE_DAPA,
    MIN_COMPLIANCE_ML,
    MIN_ECV_ML,
    MIN_GRADIENT_DAPA,
    MIN_PRESSURE_DAPA,
)


def _in_range(value: Optional[float], min_value: float, max_value: float) -> bool:
    if value is None:
        return False
    return min_value <= value <= max_value


def build_quality_flags(side_data: Dict[str, Any]) -> List[str]:
    """
    Build các cờ kỹ thuật sơ bộ từ dữ liệu đã normalize.
    Đây KHÔNG phải quality scoring đầy đủ (quality.py vẫn giữ nguyên).
    """
    flags: List[str] = []

    ecv = side_data.get("ecv_ml")
    compliance = side_data.get("compliance_ml")
    pressure = side_data.get("pressure_dapa")
    gradient = side_data.get("gradient_dapa")

    if ecv is None:
        flags.append("missing_ecv")
    elif not _in_range(ecv, MIN_ECV_ML, MAX_ECV_ML):
        flags.append("ecv_out_of_range")

    if compliance is None:
        flags.append("missing_compliance")
    elif not _in_range(compliance, MIN_COMPLIANCE_ML, MAX_COMPLIANCE_ML):
        flags.append("compliance_out_of_range")

    if pressure is None:
        flags.append("missing_pressure")
    elif not _in_range(pressure, MIN_PRESSURE_DAPA, MAX_PRESSURE_DAPA):
        flags.append("pressure_out_of_range")

    if gradient is None:
        flags.append("missing_gradient")
    elif not _in_range(gradient, MIN_GRADIENT_DAPA, MAX_GRADIENT_DAPA):
        flags.append("gradient_out_of_range")

    return flags


def normalize_side_data(
    *,
    side_obj: Any,
    pressure_value: Optional[float],
    pressure_source: str,
) -> Dict[str, Any]:
    """
    Chuẩn hóa dữ liệu một bên tai về contract metric thống nhất.

    side_obj hiện tại là object/dataclass từ extraction.py
    (đang có các field như volume_ml, compliance_ml, gradient_dapa...)
    """

    ecv = getattr(side_obj, "volume_ml", None)
    compliance = getattr(side_obj, "compliance_ml", None)
    gradient = getattr(side_obj, "gradient_dapa", None)

    data = {
        "ecv_ml": ecv,
        "compliance_ml": compliance,
        "pressure_dapa": pressure_value,
        "pressure_source": pressure_source,
        "gradient_dapa": gradient,
    }

    data["quality_flags"] = build_quality_flags(data)
    return data