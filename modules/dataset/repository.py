# modules/dataset/repository.py
from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from modules.dataset.common import (
    safe_get,
    get_side_type,
    get_side_quality_score,
    get_side_reliability,
    get_pressure_source,
    get_side_rule_confidence,
)


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def list_json_files(out_dir: str) -> List[str]:
    if not os.path.isdir(out_dir):
        return []

    files: List[str] = []
    for fn in sorted(os.listdir(out_dir), reverse=True):
        full_path = os.path.join(out_dir, fn)

        if os.path.isdir(full_path):
            continue
        if not fn.lower().endswith(".json"):
            continue

        files.append(full_path)

    return files


def list_reviewed_json_files(reviewed_dir: str) -> List[str]:
    if not os.path.isdir(reviewed_dir):
        return []

    return sorted(
        [x for x in os.listdir(reviewed_dir) if x.lower().endswith(".json")],
        reverse=True
    )


def load_json_file(full_path: str) -> Dict[str, Any]:
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_case_by_path(full_path: str) -> Optional[Dict[str, Any]]:
    try:
        return load_json_file(full_path)
    except Exception:
        return None


def build_case_summary_row(full_path: str) -> Dict[str, Any]:
    fn = os.path.basename(full_path)

    try:
        obj = load_json_file(full_path)

        right = safe_get(obj, "right", default={}) or {}
        left = safe_get(obj, "left", default={}) or {}

        return {
            "file_name": fn,
            "full_path": full_path,
            "created_at": safe_get(obj, "meta", "created_at"),
            "source_pdf": safe_get(obj, "meta", "source_pdf"),
            "right_type": get_side_type(right),
            "left_type": get_side_type(left),
            "right_quality_score": get_side_quality_score(right),
            "left_quality_score": get_side_quality_score(left),
            "right_reliability": get_side_reliability(right),
            "left_reliability": get_side_reliability(left),
            "right_pressure_source": get_pressure_source(right),
            "left_pressure_source": get_pressure_source(left),
            "overall_summary": safe_get(obj, "overall_summary"),
            "bilateral_pattern": safe_get(obj, "bilateral_pattern", "pattern"),
        }

    except Exception as e:
        return {
            "file_name": fn,
            "full_path": full_path,
            "created_at": None,
            "source_pdf": None,
            "right_type": "ERROR",
            "left_type": "ERROR",
            "right_quality_score": None,
            "left_quality_score": None,
            "right_reliability": None,
            "left_reliability": None,
            "right_pressure_source": None,
            "left_pressure_source": None,
            "overall_summary": f"JSON parse error: {e}",
            "bilateral_pattern": None,
        }


def load_tymp_case_rows(out_dir: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for full_path in list_json_files(out_dir):
        rows.append(build_case_summary_row(full_path))
    return rows


def build_review_case_row(full_path: str) -> Dict[str, Any]:
    row = build_case_summary_row(full_path)
    return {
        "file_name": row.get("file_name"),
        "full_path": row.get("full_path"),
        "created_at": row.get("created_at"),
        "source_pdf": row.get("source_pdf"),
        "right_type": row.get("right_type"),
        "left_type": row.get("left_type"),
        "right_quality": row.get("right_quality_score"),
        "left_quality": row.get("left_quality_score"),
    }


def load_review_case_rows(out_dir: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for full_path in list_json_files(out_dir):
        rows.append(build_review_case_row(full_path))
    return rows


def save_reviewed_case(case_obj: Dict[str, Any], reviewed_dir: str, original_file_name: str) -> str:
    ensure_dir(reviewed_dir)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = original_file_name.rsplit(".", 1)[0]
    out_name = f"{base_name}_reviewed_{ts}.json"
    out_path = os.path.join(reviewed_dir, out_name)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(case_obj, f, ensure_ascii=False, indent=2)

    return out_path


def load_reviewed_case_rows(reviewed_dir: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    if not os.path.isdir(reviewed_dir):
        return rows

    for fn in list_reviewed_json_files(reviewed_dir):
        full_path = os.path.join(reviewed_dir, fn)

        try:
            obj = load_json_file(full_path)

            right = safe_get(obj, "right", default={}) or {}
            left = safe_get(obj, "left", default={}) or {}

            rows.append({
                "file_name": fn,
                "full_path": full_path,
                "side": "Right",
                "engine_label": safe_get(obj, "review", "right", "engine_label"),
                "reviewed_label": safe_get(obj, "review", "right", "reviewed_label"),
                "label_changed": safe_get(obj, "review", "right", "label_changed"),
                "doctor_confirmed": safe_get(obj, "review", "doctor_confirmed"),
                "reviewer_name": safe_get(obj, "review", "reviewer_name"),
                "reviewed_at": safe_get(obj, "review", "reviewed_at"),
                "quality_score": get_side_quality_score(right),
                "quality_reliability": get_side_reliability(right),
                "rule_confidence": get_side_rule_confidence(right),
                "source_json": safe_get(obj, "review", "source_json"),
                "source_pdf": safe_get(obj, "meta", "source_pdf"),
            })

            rows.append({
                "file_name": fn,
                "full_path": full_path,
                "side": "Left",
                "engine_label": safe_get(obj, "review", "left", "engine_label"),
                "reviewed_label": safe_get(obj, "review", "left", "reviewed_label"),
                "label_changed": safe_get(obj, "review", "left", "label_changed"),
                "doctor_confirmed": safe_get(obj, "review", "doctor_confirmed"),
                "reviewer_name": safe_get(obj, "review", "reviewer_name"),
                "reviewed_at": safe_get(obj, "review", "reviewed_at"),
                "quality_score": get_side_quality_score(left),
                "quality_reliability": get_side_reliability(left),
                "rule_confidence": get_side_rule_confidence(left),
                "source_json": safe_get(obj, "review", "source_json"),
                "source_pdf": safe_get(obj, "meta", "source_pdf"),
            })

        except Exception as e:
            rows.append({
                "file_name": fn,
                "full_path": full_path,
                "side": "ERROR",
                "engine_label": "ERROR",
                "reviewed_label": "ERROR",
                "label_changed": None,
                "doctor_confirmed": None,
                "reviewer_name": None,
                "reviewed_at": None,
                "quality_score": None,
                "quality_reliability": None,
                "rule_confidence": None,
                "source_json": None,
                "source_pdf": f"JSON parse error: {e}",
            })

    return rows