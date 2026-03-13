# modules/tymp/output.py
from __future__ import annotations

from typing import Any, Dict, Optional

from .constants import DEFAULT_MODULE_NAME, DEFAULT_SCHEMA_VERSION


def build_tymp_side_output(
    *,
    normalized_metrics: Dict[str, Any],
    classification: Optional[Dict[str, Any]] = None,
    interpretation: Optional[Dict[str, Any]] = None,
    quality: Optional[Dict[str, Any]] = None,
    raw_text: Optional[str] = None,
    debug: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "ecv_ml": normalized_metrics.get("ecv_ml"),
        "compliance_ml": normalized_metrics.get("compliance_ml"),
        "pressure_dapa": normalized_metrics.get("pressure_dapa"),
        "pressure_source": normalized_metrics.get("pressure_source"),
        "gradient_dapa": normalized_metrics.get("gradient_dapa"),
        "raw_text": raw_text,
        "quality_flags": normalized_metrics.get("quality_flags", []),
        "debug": debug or {},
        "tymp_classification": classification,
        "interpretation": interpretation,
        "quality": quality,
    }


def build_tymp_result(
    *,
    meta: Optional[Dict[str, Any]] = None,
    right: Dict[str, Any],
    left: Dict[str, Any],
    bilateral_pattern: Optional[Dict[str, Any]] = None,
    overall_summary: Optional[str] = None,
    interpretation_right: Optional[Dict[str, Any]] = None,
    interpretation_left: Optional[Dict[str, Any]] = None,
    ui_artifacts: Optional[Dict[str, Any]] = None,
    warnings: Optional[list] = None,
) -> Dict[str, Any]:
    return {
        "meta": meta or {
            "module": DEFAULT_MODULE_NAME,
            "schema_version": DEFAULT_SCHEMA_VERSION,
        },
        "right": right,
        "left": left,
        "bilateral_pattern": bilateral_pattern,
        "overall_summary": overall_summary,
        "interpretation_right": interpretation_right,
        "interpretation_left": interpretation_left,
        "warnings": warnings or [],
        "_ui": ui_artifacts or {},
    }