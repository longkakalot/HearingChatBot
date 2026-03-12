# modules/tymp/quality.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List


@dataclass
class TympQualityResult:
    score: float                 # 0..1
    reliability: str             # High / Acceptable / Review recommended / Low
    flags: List[str]
    notes: List[str]


def _safe_len(x: Optional[str]) -> int:
    return len(x or "")


def _has_labels(raw_text: Optional[str]) -> Dict[str, bool]:
    raw = (raw_text or "").lower()
    return {
        "volume": "vol" in raw,
        "compliance": "compl" in raw,
        "pressure": "press" in raw,
        "gradient": "grad" in raw,
    }


def _label_from_score(score: float) -> str:
    if score >= 0.90:
        return "High"
    if score >= 0.70:
        return "Acceptable"
    if score >= 0.50:
        return "Review recommended"
    return "Low"


def compute_tymp_quality(
    *,
    ecv_ml: Optional[float],
    compliance_ml: Optional[float],
    pressure_dapa: Optional[float],
    gradient_dapa: Optional[float],
    pressure_source: Optional[str],          # ocr_ok / cv_fallback / no_result / ...
    cv_quality: Optional[float] = None,      # 0..1
    raw_text: Optional[str] = None,
    jerger_type: Optional[str] = None,
    rule_confidence: Optional[float] = None,
) -> TympQualityResult:
    """
    Quality score for tympanometry extraction/classification reliability.
    Đây là độ tin cậy của pipeline dữ liệu, KHÔNG phải chẩn đoán.
    """
    score = 1.0
    flags: List[str] = []
    notes: List[str] = []

    # -------------------------
    # 1) Missing core fields
    # -------------------------
    missing = []
    if ecv_ml is None:
        missing.append("ecv_ml")
        score -= 0.15
    if compliance_ml is None:
        missing.append("compliance_ml")
        score -= 0.20
    if pressure_dapa is None:
        missing.append("pressure_dapa")
        score -= 0.20
    if gradient_dapa is None:
        missing.append("gradient_dapa")
        score -= 0.08

    if missing:
        flags.append(f"Thiếu dữ liệu: {', '.join(missing)}.")
        notes.append("Một hoặc nhiều chỉ số quan trọng không đọc được.")

    # -------------------------
    # 2) OCR raw text quality
    # -------------------------
    labels = _has_labels(raw_text)
    missing_labels = [k for k, v in labels.items() if not v]

    if _safe_len(raw_text) < 20:
        score -= 0.10
        flags.append("OCR raw quá ngắn, có thể nhận dạng chưa tốt.")
        notes.append("Raw OCR text length thấp.")
    elif _safe_len(raw_text) < 50:
        score -= 0.04
        notes.append("Raw OCR text tương đối ngắn.")

    if missing_labels:
        penalty = min(0.12, 0.03 * len(missing_labels))
        score -= penalty
        flags.append(f"OCR raw thiếu nhãn: {', '.join(missing_labels)}.")
        notes.append("Thiếu keyword trong OCR raw có thể làm giảm độ tin cậy.")

    # -------------------------
    # 3) Pressure source quality
    # -------------------------
    if pressure_source == "ocr_ok":
        notes.append("Pressure lấy từ OCR.")
    elif pressure_source == "cv_fallback":
        score -= 0.10
        flags.append("Pressure dùng CV fallback.")
        notes.append("Pressure không lấy trực tiếp từ OCR.")
    elif pressure_source in ("no_result", "cv_rejected_range"):
        score -= 0.18
        flags.append(f"Pressure source: {pressure_source}.")
        notes.append("Pressure không xác định chắc chắn.")
    elif pressure_source:
        score -= 0.05
        notes.append(f"Pressure source không chuẩn mặc định: {pressure_source}")

    # -------------------------
    # 4) CV quality (if used)
    # -------------------------
    if pressure_source == "cv_fallback":
        if cv_quality is None:
            score -= 0.05
            flags.append("Thiếu cv_quality trong khi pressure dùng CV fallback.")
        else:
            if cv_quality < 0.70:
                score -= 0.12
                flags.append("CV quality thấp.")
            elif cv_quality < 0.85:
                score -= 0.05
                notes.append("CV quality mức trung bình.")

    # -------------------------
    # 5) Sanity ranges (broad)
    # -------------------------
    if ecv_ml is not None and not (0.0 <= ecv_ml <= 5.0):
        score -= 0.10
        flags.append("Volume ngoài khoảng hợp lý.")
    if compliance_ml is not None and not (0.0 <= compliance_ml <= 5.0):
        score -= 0.12
        flags.append("Compliance ngoài khoảng hợp lý.")
    if pressure_dapa is not None and not (-600.0 <= pressure_dapa <= 300.0):
        score -= 0.12
        flags.append("Pressure ngoài khoảng hợp lý.")
    if gradient_dapa is not None and not (0.0 <= gradient_dapa <= 300.0):
        score -= 0.06
        flags.append("Gradient ngoài khoảng hợp lý.")

    # -------------------------
    # 6) Some suspicious patterns
    # -------------------------
    if ecv_ml is not None and ecv_ml < 0.30:
        score -= 0.08
        flags.append("ECV rất thấp, nghi tắc probe/đặt probe chưa đúng.")
    if compliance_ml is not None and compliance_ml == 0:
        score -= 0.06
        notes.append("Compliance = 0 có thể là flat thật hoặc lỗi đo.")
    if jerger_type == "Unknown":
        score -= 0.10
        flags.append("Phân loại Jerger chưa chắc chắn (Unknown).")

    # -------------------------
    # 7) Rule confidence
    # -------------------------
    if rule_confidence is not None:
        if rule_confidence < 0.40:
            score -= 0.15
            flags.append("Rule confidence thấp.")
        elif rule_confidence < 0.70:
            score -= 0.07
            notes.append("Rule confidence mức trung bình.")

    # Clamp
    score = max(0.0, min(1.0, round(score, 2)))
    reliability = _label_from_score(score)

    return TympQualityResult(
        score=score,
        reliability=reliability,
        flags=flags,
        notes=notes,
    )


def to_dict(result: TympQualityResult) -> Dict[str, Any]:
    return asdict(result)