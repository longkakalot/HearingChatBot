# modules/common/json_utils.py
from __future__ import annotations

import os
import json
from typing import Any, Dict


def safe_filename(name: str) -> str:
    keep = []
    for ch in name:
        if ch.isalnum() or ch in (" ", "_", "-", ".", "(", ")", "[", "]"):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip()


def strip_ui_objects(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove UI-only objects like PIL images / ROI images before JSON dump.
    """
    clean = {k: v for k, v in result.items() if k != "_ui"}
    return json.loads(json.dumps(clean, ensure_ascii=False, default=str))


def save_json(filepath: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)