# modules/tymp/pipeline.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional

from .merge import merge_pressure
from .extraction import extract_tymp_values
from .cv_pressure import extract_peak_pressure_from_page
from .rules import classify_tymp, to_dict as cls_to_dict
from .interpretation import (
    TympEarValues,
    interpret_ear,
    interpretation_to_dict,
    overall_summary,
)
from .quality import compute_tymp_quality, to_dict as quality_to_dict
from .bilateral_rules import detect_bilateral_pattern, to_dict as bilateral_to_dict
from .normalize import normalize_side_data
from .output import build_tymp_side_output, build_tymp_result
from .constants import DEFAULT_SCHEMA_VERSION


def run_tymp_pipeline(
    page_img,
    cfg: Dict[str, Any],
    *,
    source_pdf: Optional[str] = None,
    page_index: int = 1,
    zoom: float = 3.0,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Tympanometry clinical pipeline:
      1) OCR extraction
      2) CV pressure extraction
      3) OCR/CV merge
      4) Jerger classification
      5) Clinical interpretation
      6) Quality scoring
      7) Bilateral pattern
      8) Build JSON-ready result
    """
    # ----------------------------
    # 1) OCR extraction
    # ----------------------------
    right_obj, left_obj, right_box, left_box = extract_tymp_values(page_img)

    # ----------------------------
    # 2) CV peak pressure
    # ----------------------------
    cv_r, cv_l = extract_peak_pressure_from_page(page_img)

    # ----------------------------
    # 3) Merge pressure (OCR-first)
    # ----------------------------
    final_pr, src_pr = merge_pressure(
        getattr(right_obj, "pressure_dapa", None),
        getattr(cv_r, "peak_pressure_dapa", None),
        getattr(cv_r, "quality", None),
    )
    final_pl, src_pl = merge_pressure(
        getattr(left_obj, "pressure_dapa", None),
        getattr(cv_l, "peak_pressure_dapa", None),
        getattr(cv_l, "quality", None),
    )

    # ----------------------------
    # 4) Normalize raw data -> standard metrics
    # ----------------------------
    raw_r = normalize_side_data(
        side_obj=right_obj,
        pressure_value=final_pr,
        pressure_source=src_pr,
    )
    raw_l = normalize_side_data(
        side_obj=left_obj,
        pressure_value=final_pl,
        pressure_source=src_pl,
    )

    raw_text_r = getattr(right_obj, "raw_text", None)
    raw_text_l = getattr(left_obj, "raw_text", None)

    debug_r = {
        "pressure_ocr": getattr(right_obj, "pressure_dapa", None),
        "pressure_cv": getattr(cv_r, "peak_pressure_dapa", None),
        "cv_quality": getattr(cv_r, "quality", None),
    }
    debug_l = {
        "pressure_ocr": getattr(left_obj, "pressure_dapa", None),
        "pressure_cv": getattr(cv_l, "peak_pressure_dapa", None),
        "cv_quality": getattr(cv_l, "quality", None),
    }

    # ----------------------------
    # 5) Rule classification
    # ----------------------------
    cls_r = classify_tymp(
        ecv_ml=raw_r["ecv_ml"],
        compliance_ml=raw_r["compliance_ml"],
        pressure_dapa=raw_r["pressure_dapa"],
        gradient_dapa=raw_r["gradient_dapa"],
        cfg=cfg,
    )
    cls_l = classify_tymp(
        ecv_ml=raw_l["ecv_ml"],
        compliance_ml=raw_l["compliance_ml"],
        pressure_dapa=raw_l["pressure_dapa"],
        gradient_dapa=raw_l["gradient_dapa"],
        cfg=cfg,
    )

    # ----------------------------
    # 6) Interpretation
    # ----------------------------
    ear_r = TympEarValues(
        ecv_ml=raw_r["ecv_ml"],
        compliance_ml=raw_r["compliance_ml"],
        pressure_dapa=raw_r["pressure_dapa"],
        gradient_dapa=raw_r["gradient_dapa"],
    )
    ear_l = TympEarValues(
        ecv_ml=raw_l["ecv_ml"],
        compliance_ml=raw_l["compliance_ml"],
        pressure_dapa=raw_l["pressure_dapa"],
        gradient_dapa=raw_l["gradient_dapa"],
    )

    interp_r = interpret_ear(ear_r, cls_r.jerger_type, cfg=cfg)
    interp_l = interpret_ear(ear_l, cls_l.jerger_type, cfg=cfg)
    overall = overall_summary(interp_r, interp_l)

    # ----------------------------
    # 7) Quality
    # ----------------------------
    quality_r = compute_tymp_quality(
        ecv_ml=raw_r["ecv_ml"],
        compliance_ml=raw_r["compliance_ml"],
        pressure_dapa=raw_r["pressure_dapa"],
        gradient_dapa=raw_r["gradient_dapa"],
        pressure_source=raw_r["pressure_source"],
        cv_quality=debug_r.get("cv_quality"),
        raw_text=raw_text_r,
        jerger_type=cls_r.jerger_type,
        rule_confidence=cls_r.confidence,
    )
    quality_l = compute_tymp_quality(
        ecv_ml=raw_l["ecv_ml"],
        compliance_ml=raw_l["compliance_ml"],
        pressure_dapa=raw_l["pressure_dapa"],
        gradient_dapa=raw_l["gradient_dapa"],
        pressure_source=raw_l["pressure_source"],
        cv_quality=debug_l.get("cv_quality"),
        raw_text=raw_text_l,
        jerger_type=cls_l.jerger_type,
        rule_confidence=cls_l.confidence,
    )

    # ----------------------------
    # 8) Bilateral pattern
    # ----------------------------
    bilateral = detect_bilateral_pattern(
        cls_r.jerger_type,
        cls_l.jerger_type,
    )

    # ----------------------------
    # 9) Build JSON-ready result
    # ----------------------------
    interp_r_dict = interpretation_to_dict(interp_r)
    interp_l_dict = interpretation_to_dict(interp_l)

    right_output = build_tymp_side_output(
        normalized_metrics=raw_r,
        classification=cls_to_dict(cls_r),
        interpretation=interp_r_dict,
        quality=quality_to_dict(quality_r),
        raw_text=raw_text_r,
        debug=debug_r,
    )
    left_output = build_tymp_side_output(
        normalized_metrics=raw_l,
        classification=cls_to_dict(cls_l),
        interpretation=interp_l_dict,
        quality=quality_to_dict(quality_l),
        raw_text=raw_text_l,
        debug=debug_l,
    )

    meta = {
        "source_pdf": source_pdf,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "page_index_tymp": page_index,
        "zoom": zoom,
        "schema_version": DEFAULT_SCHEMA_VERSION,
        "engine": {
            "ocr": "tesseract",
            "cv_pressure": "optional_fallback_only",
        },
        "active_cfg": cfg,
    }

    ui_artifacts = {
        "right_box": right_box,
        "left_box": left_box,
        "page_img": page_img,
        "cv_right": {
            "peak_pressure_dapa": getattr(cv_r, "peak_pressure_dapa", None),
            "quality": getattr(cv_r, "quality", None),
            "debug": getattr(cv_r, "debug", {}),
        },
        "cv_left": {
            "peak_pressure_dapa": getattr(cv_l, "peak_pressure_dapa", None),
            "quality": getattr(cv_l, "quality", None),
            "debug": getattr(cv_l, "debug", {}),
        },
    }

    result = build_tymp_result(
        meta=meta,
        right=right_output,
        left=left_output,
        bilateral_pattern=bilateral_to_dict(bilateral),
        overall_summary=overall,
        interpretation_right=interp_r_dict,
        interpretation_left=interp_l_dict,
        ui_artifacts=ui_artifacts,
        warnings=[],
    )

    return result