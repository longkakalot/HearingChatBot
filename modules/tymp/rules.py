from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Tuple

from .config import DEFAULT_TYMP_CFG


@dataclass
class TympClassification:
    jerger_type: str
    confidence: float
    reasons: Dict[str, Any]
    flags: Dict[str, Any]


def _is_num(x) -> bool:
    return x is not None


def _get_cfg(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if cfg is None:
        return DEFAULT_TYMP_CFG
    return cfg


def _check_range(name: str, value: Optional[float], lo: float, hi: float, flags: Dict[str, Any]):
    if value is None:
        return
    if not (lo <= value <= hi):
        flags["out_of_range"].append({name: value})


def classify_tymp(
    ecv_ml: Optional[float],
    compliance_ml: Optional[float],
    pressure_dapa: Optional[float],
    gradient_dapa: Optional[float] = None,
    cfg: Optional[Dict[str, Any]] = None,
) -> TympClassification:

    cfg = _get_cfg(cfg)

    flags: Dict[str, Any] = {
        "missing": [],
        "out_of_range": [],
    }

    ranges = cfg["ranges"]
    pressure_windows = cfg["pressure_windows"]
    compliance_cutoffs = cfg["compliance_cutoffs"]
    ecv_hints = cfg["ecv_hints"]
    gradient_notes = cfg.get("gradient_notes", {"LOW": 30.0, "HIGH": 200.0})

    # -------------------------
    # Validate ranges
    # -------------------------

    _check_range("ecv_ml", ecv_ml, ranges["ecv_ml"][0], ranges["ecv_ml"][1], flags)
    _check_range("compliance_ml", compliance_ml, ranges["compliance_ml"][0], ranges["compliance_ml"][1], flags)
    _check_range("pressure_dapa", pressure_dapa, ranges["pressure_dapa"][0], ranges["pressure_dapa"][1], flags)
    _check_range("gradient_dapa", gradient_dapa, ranges["gradient_dapa"][0], ranges["gradient_dapa"][1], flags)

    for k, v in [
        ("ecv_ml", ecv_ml),
        ("compliance_ml", compliance_ml),
        ("pressure_dapa", pressure_dapa),
    ]:
        if v is None:
            flags["missing"].append(k)

    if compliance_ml is None:
        return TympClassification(
            jerger_type="Unknown",
            confidence=0.2,
            reasons={"rule": "missing_compliance"},
            flags=flags,
        )

    # -------------------------
    # Load thresholds
    # -------------------------

    A_PRESS_MIN = pressure_windows["A_PRESS_MIN"]
    A_PRESS_MAX = pressure_windows["A_PRESS_MAX"]
    C_PRESS_CUTOFF = pressure_windows["C_PRESS_CUTOFF"]
    C2_CUTOFF = pressure_windows["C2_CUTOFF"]

    AS_CUTOFF = compliance_cutoffs["AS_CUTOFF"]
    AD_CUTOFF = compliance_cutoffs["AD_CUTOFF"]
    B_COMP_CUTOFF = compliance_cutoffs["B_COMP_CUTOFF"]

    HIGH_ECV_HINT = ecv_hints["HIGH_ECV_HINT"]

    GRAD_LOW = gradient_notes["LOW"]
    GRAD_HIGH = gradient_notes["HIGH"]

    reasons: Dict[str, Any] = {
        "inputs": {
            "ecv_ml": ecv_ml,
            "compliance_ml": compliance_ml,
            "pressure_dapa": pressure_dapa,
            "gradient_dapa": gradient_dapa,
        }
    }

    # -------------------------
    # TYPE B (flat)
    # -------------------------

    if compliance_ml <= B_COMP_CUTOFF:

        conf = 0.85

        if pressure_dapa is None:
            conf = 0.90
            reasons["rule"] = "B_flat_missing_pressure"
        else:
            reasons["rule"] = "B_flat_compliance"

        if ecv_ml is not None:

            if ecv_ml >= HIGH_ECV_HINT:
                reasons["ecv_hint"] = "High ECV may suggest TM perforation / ventilation tube"
                conf = min(conf + 0.05, 0.95)

            else:
                reasons["ecv_hint"] = "Normal ECV with flat tymp may suggest middle ear effusion"

        return TympClassification("B", conf, reasons, flags)

    # -------------------------
    # Missing pressure
    # -------------------------

    if pressure_dapa is None:
        return TympClassification(
            jerger_type="Unknown",
            confidence=0.35,
            reasons={
                "rule": "missing_pressure",
                **reasons,
            },
            flags=flags,
        )

    # -------------------------
    # TYPE C
    # -------------------------

    if pressure_dapa <= C_PRESS_CUTOFF:

        subtype = "C2" if pressure_dapa <= C2_CUTOFF else "C1"

        conf = 0.75

        if 0.3 <= compliance_ml <= 1.6:
            conf = 0.85

        reasons["rule"] = "C_negative_pressure"
        reasons["subtype"] = subtype

        return TympClassification("C", conf, reasons, flags)

    # -------------------------
    # TYPE A zone
    # -------------------------

    if A_PRESS_MIN <= pressure_dapa <= A_PRESS_MAX:

        # As
        if compliance_ml < AS_CUTOFF:

            reasons["rule"] = "As_low_compliance"
            return TympClassification("As", 0.85, reasons, flags)

        # Ad
        if compliance_ml > AD_CUTOFF:

            reasons["rule"] = "Ad_high_compliance"
            return TympClassification("Ad", 0.85, reasons, flags)

        # Normal A
        conf = 0.80
        reasons["rule"] = "A_normal"

        if gradient_dapa is not None:
            if gradient_dapa < GRAD_LOW or gradient_dapa > GRAD_HIGH:
                conf = 0.72
                reasons["gradient_note"] = "Gradient atypical"

        return TympClassification("A", conf, reasons, flags)

    # -------------------------
    # Borderline
    # -------------------------

    reasons["rule"] = "borderline_pressure"

    return TympClassification(
        jerger_type="Unknown",
        confidence=0.55,
        reasons=reasons,
        flags=flags,
    )


def classify_both_ears(
    right: Dict[str, Optional[float]],
    left: Dict[str, Optional[float]],
    cfg: Optional[Dict[str, Any]] = None,
) -> Tuple[TympClassification, TympClassification]:

    r = classify_tymp(
        ecv_ml=right.get("ecv_ml"),
        compliance_ml=right.get("compliance_ml"),
        pressure_dapa=right.get("pressure_dapa"),
        gradient_dapa=right.get("gradient_dapa"),
        cfg=cfg,
    )

    l = classify_tymp(
        ecv_ml=left.get("ecv_ml"),
        compliance_ml=left.get("compliance_ml"),
        pressure_dapa=left.get("pressure_dapa"),
        gradient_dapa=left.get("gradient_dapa"),
        cfg=cfg,
    )

    return r, l


def to_dict(cls: TympClassification) -> Dict[str, Any]:
    return asdict(cls)