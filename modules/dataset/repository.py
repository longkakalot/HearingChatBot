# modules/dataset/repository.py
from __future__ import annotations

import os
import json
from typing import Dict, Any, List, Optional

from modules.dataset.common import (
    safe_get,
    get_side_type,
    get_side_quality_score,
    get_side_reliability,
    get_pressure_source,
)


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


def load_json_file(full_path: str) -> Dict[str, Any]:
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def load_case_by_path(full_path: str) -> Optional[Dict[str, Any]]:
    try:
        return load_json_file(full_path)
    except Exception:
        return None