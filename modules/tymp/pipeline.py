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


def _build_flags_from_extraction(side_obj) -> Dict[str, Any]:
    """
    Gắn cờ chất lượng cơ bản từ extraction raw.
    Giữ tương thích với logic cũ.
    """
    raw = (getattr(side_obj, "raw_text", None) or "").lower()
    has_volume = "vol" in raw
    has_compliance = "compl" in raw
    has_pressure = "press" in raw
    has_gradient = "grad" in raw

    missing = []

    volume_ml = getattr(side_obj, "volume_ml", None)
    compliance_ml = getattr(side_obj, "compliance_ml", None)
    pressure_dapa = getattr(side_obj, "pressure_dapa", None)
    gradient_dapa = getattr(side_obj, "gradient_dapa", None)

    if volume_ml is None:
        missing.append("volume_ml")
    if compliance_ml is None:
        missing.append("compliance_ml")
    if pressure_dapa is None:
        missing.append("pressure_dapa")
    if gradient_dapa is None:
        missing.append("gradient_dapa")

    return {
        "missing_fields": missing,
        "raw_has_labels": {
            "volume": has_volume,
            "compliance": has_compliance,
            "pressure": has_pressure,
            "gradient": has_gradient,
        },
        "raw_len": len(raw),
    }


def _map_side_obj_to_standard(
    side_obj,
    final_pressure: Optional[float],
    pressure_source: str,
    cv_result,
) -> Dict[str, Any]:
    """
    Map extraction object hiện tại sang schema chuẩn output của project.
    Chuẩn field name đầu ra:
      - ecv_ml
      - compliance_ml
      - pressure_dapa
      - pressure_source
      - gradient_dapa
    """
    ecv_ml = getattr(side_obj, "volume_ml", None)  # extraction raw vẫn giữ volume_ml
    compliance_ml = getattr(side_obj, "compliance_ml", None)
    gradient_dapa = getattr(side_obj, "gradient_dapa", None)
    raw_text = getattr(side_obj, "raw_text", None)

    return {
        "ecv_ml": ecv_ml,
        "compliance_ml": compliance_ml,
        "pressure_dapa": final_pressure,
        "pressure_source": pressure_source,
        "gradient_dapa": gradient_dapa,
        "raw_text": raw_text,
        "quality_flags": _build_flags_from_extraction(side_obj),
        "debug": {
            "pressure_ocr": getattr(side_obj, "pressure_dapa", None),
            "pressure_cv": getattr(cv_result, "peak_pressure_dapa", None),
            "cv_quality": getattr(cv_result, "quality", None),
        },
    }


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
    # 4) Map raw data -> standard schema
    # ----------------------------
    raw_r = _map_side_obj_to_standard(right_obj, final_pr, src_pr, cv_r)
    raw_l = _map_side_obj_to_standard(left_obj, final_pl, src_pl, cv_l)

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
        cv_quality=raw_r["debug"].get("cv_quality"),
        raw_text=raw_r["raw_text"],
        jerger_type=cls_r.jerger_type,
        rule_confidence=cls_r.confidence,
    )
    quality_l = compute_tymp_quality(
        ecv_ml=raw_l["ecv_ml"],
        compliance_ml=raw_l["compliance_ml"],
        pressure_dapa=raw_l["pressure_dapa"],
        gradient_dapa=raw_l["gradient_dapa"],
        pressure_source=raw_l["pressure_source"],
        cv_quality=raw_l["debug"].get("cv_quality"),
        raw_text=raw_l["raw_text"],
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
    result = {
        "meta": {
            "source_pdf": source_pdf,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "page_index_tymp": page_index,
            "zoom": zoom,
            "schema_version": "tymp_v1",
            "engine": {
                "ocr": "tesseract",
                "cv_pressure": "optional_fallback_only",
            },
            "active_cfg": cfg,
        },
        "right": {
            "ecv_ml": raw_r["ecv_ml"],
            "compliance_ml": raw_r["compliance_ml"],
            "pressure_dapa": raw_r["pressure_dapa"],
            "pressure_source": raw_r["pressure_source"],
            "gradient_dapa": raw_r["gradient_dapa"],
            "raw_text": raw_r["raw_text"],
            "quality_flags": raw_r["quality_flags"],
            "debug": raw_r["debug"],
            "tymp_classification": cls_to_dict(cls_r),
            "interpretation": interpretation_to_dict(interp_r),
            "quality": quality_to_dict(quality_r),
        },
        "left": {
            "ecv_ml": raw_l["ecv_ml"],
            "compliance_ml": raw_l["compliance_ml"],
            "pressure_dapa": raw_l["pressure_dapa"],
            "pressure_source": raw_l["pressure_source"],
            "gradient_dapa": raw_l["gradient_dapa"],
            "raw_text": raw_l["raw_text"],
            "quality_flags": raw_l["quality_flags"],
            "debug": raw_l["debug"],
            "tymp_classification": cls_to_dict(cls_l),
            "interpretation": interpretation_to_dict(interp_l),
            "quality": quality_to_dict(quality_l),
        },
        "bilateral_pattern": bilateral_to_dict(bilateral),
        "overall_summary": overall,
        # compatibility top-level keys theo app cũ
        "interpretation_right": interpretation_to_dict(interp_r),
        "interpretation_left": interpretation_to_dict(interp_l),
        # UI-only
        "_ui": {
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
        },
    }

    return result