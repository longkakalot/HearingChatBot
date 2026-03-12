# modules/dataset/common.py
from __future__ import annotations

from typing import Any, Dict


def safe_get(d: Dict[str, Any], *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def get_ecv(side_obj: Dict[str, Any]):
    """
    Compatibility:
    - JSON mới: ecv_ml
    - JSON cũ: volume_ml
    """
    if not isinstance(side_obj, dict):
        return None
    return side_obj.get("ecv_ml", side_obj.get("volume_ml"))


def get_classification(side_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compatibility:
    - JSON hiện tại: tymp_classification
    - tương lai: classification
    """
    if not isinstance(side_obj, dict):
        return {}
    return side_obj.get("tymp_classification", side_obj.get("classification", {})) or {}


def get_interpretation(side_obj: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(side_obj, dict):
        return {}
    return side_obj.get("interpretation", {}) or {}


def get_quality(side_obj: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(side_obj, dict):
        return {}
    return side_obj.get("quality", {}) or {}


def get_pressure_source(side_obj: Dict[str, Any]):
    if not isinstance(side_obj, dict):
        return None
    return side_obj.get("pressure_source")


def get_side_type(side_obj: Dict[str, Any]):
    cls = get_classification(side_obj)
    return cls.get("jerger_type")


def get_side_rule_confidence(side_obj: Dict[str, Any]):
    cls = get_classification(side_obj)
    return cls.get("confidence")


def get_side_quality_score(side_obj: Dict[str, Any]):
    q = get_quality(side_obj)
    return q.get("score")


def get_side_reliability(side_obj: Dict[str, Any]):
    q = get_quality(side_obj)
    return q.get("reliability")