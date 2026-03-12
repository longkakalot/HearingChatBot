# modules/tymp/schema.py
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List


@dataclass
class TympMeta:
    source_pdf: Optional[str] = None
    created_at: Optional[str] = None
    page_index_tymp: int = 1
    zoom: float = 3.0
    engine: Dict[str, Any] = field(default_factory=dict)
    active_cfg: Optional[Dict[str, Any]] = None


@dataclass
class TympRawEarData:
    ecv_ml: Optional[float] = None
    compliance_ml: Optional[float] = None
    pressure_dapa: Optional[float] = None
    pressure_source: Optional[str] = None
    gradient_dapa: Optional[float] = None
    raw_text: Optional[str] = None
    quality_flags: Dict[str, Any] = field(default_factory=dict)
    debug: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TympEarBundle:
    raw: TympRawEarData
    classification: Dict[str, Any]
    interpretation: Dict[str, Any]
    quality: Dict[str, Any]


@dataclass
class TympCaseBundle:
    meta: TympMeta
    right: TympEarBundle
    left: TympEarBundle
    bilateral_pattern: Dict[str, Any]
    overall_summary: str
    images: Dict[str, Any] = field(default_factory=dict)  # right_box / left_box / page_img if needed for UI


def to_dict(obj: Any) -> Dict[str, Any]:
    return asdict(obj)