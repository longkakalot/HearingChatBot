# modules/tymp/merge.py
from __future__ import annotations

from typing import Optional, Tuple


def merge_pressure(
    ocr_pressure: Optional[float],
    cv_pressure: Optional[float],
    cv_quality: Optional[float],
) -> Tuple[Optional[float], str]:
    """
    Merge strategy: OCR-first, CV only as fallback.

    Returns:
        (final_pressure, pressure_source)

    pressure_source:
        - ocr_ok
        - cv_fallback
        - no_result
        - cv_rejected_range
    """
    # 1) OCR có số hợp lệ -> ưu tiên OCR luôn
    if ocr_pressure is not None and (-600.0 <= ocr_pressure <= 300.0):
        return ocr_pressure, "ocr_ok"

    # 2) OCR fail -> mới xét CV
    if cv_pressure is None:
        return None, "no_result"

    if cv_quality is None or cv_quality < 0.70:
        return None, "no_result"

    if not (-600.0 <= cv_pressure <= 300.0):
        return None, "cv_rejected_range"

    return cv_pressure, "cv_fallback"