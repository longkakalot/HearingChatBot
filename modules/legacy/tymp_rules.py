# modules/tymp_rules.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Tuple

from modules.tymp_config import DEFAULT_TYMP_CFG


@dataclass
class TympClassification:
    jerger_type: str                 # A / As / Ad / B / C / Unknown
    confidence: float                # 0..1
    reasons: Dict[str, Any]          # giải thích theo rule
    flags: Dict[str, Any]            # cảnh báo chất lượng / thiếu dữ liệu


def _is_num(x) -> bool:
    return x is not None


def classify_tymp(
    volume_ml: Optional[float],
    compliance_ml: Optional[float],
    pressure_dapa: Optional[float],
    gradient_dapa: Optional[float] = None,
    cfg: Optional[Dict[str, Any]] = None,
) -> TympClassification:
    """
    Rule-based tympanogram classification (Jerger-like), configurable via cfg.

    - A: pressure gần 0, compliance bình thường
    - As: pressure gần 0, compliance thấp
    - Ad: pressure gần 0, compliance cao
    - B: peak không rõ/pressure thiếu + compliance rất thấp (flat)
    - C: pressure âm đáng kể

    cfg (lookup table) cho phép chỉnh ngưỡng theo SOP/máy đo.
    """
    cfg = cfg or DEFAULT_TYMP_CFG

    ranges = cfg.get("ranges", {})
    pw = cfg.get("pressure_windows", {})
    cc = cfg.get("compliance_cutoffs", {})
    ecv = cfg.get("ecv_hints", {})
    gn = cfg.get("gradient_notes", {})

    # -------------------------
    # Thresholds from cfg
    # -------------------------
    A_PRESS_MIN = float(pw.get("A_PRESS_MIN", -100.0))
    A_PRESS_MAX = float(pw.get("A_PRESS_MAX", 50.0))
    C_PRESS_CUTOFF = float(pw.get("C_PRESS_CUTOFF", -100.0))
    C2_CUTOFF = float(pw.get("C2_CUTOFF", -200.0))

    AS_CUTOFF = float(cc.get("AS_CUTOFF", 0.30))
    AD_CUTOFF = float(cc.get("AD_CUTOFF", 1.60))
    B_COMP_CUTOFF = float(cc.get("B_COMP_CUTOFF", 0.20))

    HIGH_ECV_HINT = float(ecv.get("HIGH_ECV_HINT", 2.0))

    GRAD_LOW = float(gn.get("LOW", 30.0))
    GRAD_HIGH = float(gn.get("HIGH", 200.0))

    # -------------------------
    # flags + validation
    # -------------------------
    flags: Dict[str, Any] = {
        "missing": [],
        "out_of_range": [],
        "cfg_used": {
            "A_PRESS_MIN": A_PRESS_MIN,
            "A_PRESS_MAX": A_PRESS_MAX,
            "C_PRESS_CUTOFF": C_PRESS_CUTOFF,
            "C2_CUTOFF": C2_CUTOFF,
            "AS_CUTOFF": AS_CUTOFF,
            "AD_CUTOFF": AD_CUTOFF,
            "B_COMP_CUTOFF": B_COMP_CUTOFF,
            "HIGH_ECV_HINT": HIGH_ECV_HINT,
            "GRAD_LOW": GRAD_LOW,
            "GRAD_HIGH": GRAD_HIGH,
        }
    }

    def _check_range(name: str, value: Optional[float]):
        if not _is_num(value):
            return
        r = ranges.get(name)
        if not r:
            return
        lo, hi = float(r[0]), float(r[1])
        if not (lo <= float(value) <= hi):
            flags["out_of_range"].append({name: value})

    _check_range("volume_ml", volume_ml)
    _check_range("compliance_ml", compliance_ml)
    _check_range("pressure_dapa", pressure_dapa)
    _check_range("gradient_dapa", gradient_dapa)

    for k, v in [("volume_ml", volume_ml), ("compliance_ml", compliance_ml), ("pressure_dapa", pressure_dapa)]:
        if v is None:
            flags["missing"].append(k)

    # reasons
    reasons: Dict[str, Any] = {
        "inputs": {
            "volume_ml": volume_ml,
            "compliance_ml": compliance_ml,
            "pressure_dapa": pressure_dapa,
            "gradient_dapa": gradient_dapa,
        }
    }

    # Nếu thiếu compliance thì gần như không phân loại được
    if compliance_ml is None:
        return TympClassification(
            jerger_type="Unknown",
            confidence=0.2,
            reasons={"rule": "missing_compliance", **reasons},
            flags=flags,
        )

    # -------------------------
    # 1) Type B (flat)
    # -------------------------
    # Nếu compliance rất thấp -> ưu tiên B, đặc biệt khi pressure missing
    if float(compliance_ml) <= B_COMP_CUTOFF:
        conf = 0.85
        if pressure_dapa is None:
            conf = 0.90
            reasons["rule"] = "B_flat_compliance_and_missing_pressure"
        else:
            reasons["rule"] = "B_flat_compliance"

        # ECV hint: bình thường vs lớn (thủng màng nhĩ/ống dẫn)
        if volume_ml is not None:
            if float(volume_ml) >= HIGH_ECV_HINT:
                reasons["ecv_hint"] = "High ECV may suggest perforation/PE tube (clinical correlate)"
                conf = min(0.95, conf + 0.05)
            else:
                reasons["ecv_hint"] = "Normal/low ECV with flat may suggest effusion (clinical correlate)"
        return TympClassification("B", conf, reasons, flags)

    # -------------------------
    # 2) Need pressure for A/As/Ad/C
    # -------------------------
    if pressure_dapa is None:
        # Compliance không quá thấp nhưng pressure missing => unknown-ish
        return TympClassification(
            jerger_type="Unknown",
            confidence=0.35,
            reasons={"rule": "missing_pressure_but_compliance_not_flat", **reasons},
            flags=flags,
        )

    p = float(pressure_dapa)
    c = float(compliance_ml)

    # -------------------------
    # 3) Type C (negative pressure)
    # -------------------------
    if p <= C_PRESS_CUTOFF:
        subtype = "C2" if p <= C2_CUTOFF else "C1"
        reasons["rule"] = "C_negative_pressure"
        reasons["subtype"] = subtype

        # confidence increases when compliance is in normal-ish range (peak exists but shifted)
        conf = 0.75
        if AS_CUTOFF <= c <= AD_CUTOFF:
            conf = 0.85
        return TympClassification("C", conf, reasons, flags)

    # -------------------------
    # 4) A / As / Ad zone (near-normal pressure)
    # -------------------------
    if A_PRESS_MIN <= p <= A_PRESS_MAX:
        # As
        if c < AS_CUTOFF:
            reasons["rule"] = "As_low_compliance_near_normal_pressure"
            conf = 0.85
            return TympClassification("As", conf, reasons, flags)

        # Ad
        if c > AD_CUTOFF:
            reasons["rule"] = "Ad_high_compliance_near_normal_pressure"
            conf = 0.85
            return TympClassification("Ad", conf, reasons, flags)

        # A
        reasons["rule"] = "A_normal_pressure_and_compliance"
        conf = 0.80

        # Nếu gradient có và quá thấp/cao bất thường thì giảm nhẹ confidence
        if gradient_dapa is not None:
            g = float(gradient_dapa)
            if g < GRAD_LOW or g > GRAD_HIGH:
                reasons["gradient_note"] = "Gradient atypical; consider review"
                conf = 0.72

        return TympClassification("A", conf, reasons, flags)

    # -------------------------
    # 5) Borderline / Unknown
    # -------------------------
    reasons["rule"] = "borderline_pressure_outside_A_zone_but_not_C"
    conf = 0.55
    return TympClassification("Unknown", conf, reasons, flags)


def classify_both_ears(
    right: Dict[str, Optional[float]],
    left: Dict[str, Optional[float]],
    cfg: Optional[Dict[str, Any]] = None,
) -> Tuple[TympClassification, TympClassification]:
    r = classify_tymp(
        volume_ml=right.get("volume_ml"),
        compliance_ml=right.get("compliance_ml"),
        pressure_dapa=right.get("pressure_dapa"),
        gradient_dapa=right.get("gradient_dapa"),
        cfg=cfg,
    )
    l = classify_tymp(
        volume_ml=left.get("volume_ml"),
        compliance_ml=left.get("compliance_ml"),
        pressure_dapa=left.get("pressure_dapa"),
        gradient_dapa=left.get("gradient_dapa"),
        cfg=cfg,
    )
    return r, l


def to_dict(cls: TympClassification) -> Dict[str, Any]:
    return asdict(cls)