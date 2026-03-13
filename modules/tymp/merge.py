# modules/tymp/merge.py
from __future__ import annotations

from typing import Optional, Tuple

from .constants import (
    MAX_PRESSURE_DAPA,
    MIN_PRESSURE_DAPA,
    PRESSURE_SOURCE_CV_FALLBACK,
    PRESSURE_SOURCE_CV_REJECTED_RANGE,
    PRESSURE_SOURCE_NO_RESULT,
    PRESSURE_SOURCE_OCR_OK,
)


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
    if ocr_pressure is not None and (MIN_PRESSURE_DAPA <= ocr_pressure <= MAX_PRESSURE_DAPA):
        return ocr_pressure, PRESSURE_SOURCE_OCR_OK

    # 2) OCR fail -> mới xét CV
    if cv_pressure is None:
        return None, PRESSURE_SOURCE_NO_RESULT

    if cv_quality is None or cv_quality < 0.70:
        return None, PRESSURE_SOURCE_NO_RESULT

    if not (MIN_PRESSURE_DAPA <= cv_pressure <= MAX_PRESSURE_DAPA):
        return None, PRESSURE_SOURCE_CV_REJECTED_RANGE

    return cv_pressure, PRESSURE_SOURCE_CV_FALLBACK