# modules/common/app_utils.py
from __future__ import annotations

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


def make_json_safe_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove UI-only objects before JSON dump.
    """
    return json.loads(json.dumps(
        {k: v for k, v in result.items() if k != "_ui"},
        ensure_ascii=False,
        default=str
    ))