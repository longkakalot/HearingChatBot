from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List, Tuple

from .config import DEFAULT_TYMP_CFG


@dataclass
class TympEarValues:
    ecv_ml: Optional[float] = None
    compliance_ml: Optional[float] = None
    pressure_dapa: Optional[float] = None
    gradient_dapa: Optional[float] = None


@dataclass
class TympInterpretation:
    summary_vi: str
    possible_causes: List[str]
    suggest_next_steps: List[str]
    red_flags: List[str]
    confidence: float
    notes: List[str]


def _is_missing(x: Optional[float]) -> bool:
    return x is None


def _in_range(x: Optional[float], r: Tuple[float, float]) -> bool:
    if x is None:
        return True
    return r[0] <= x <= r[1]


def _fmt(x: Optional[float], unit: str = "") -> str:
    if x is None:
        return "N/A"
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return f"{s}{unit}"


def _normalize_type(t: Optional[str]) -> str:
    if not t:
        return "Unknown"
    return t.strip()


def _pressure_severity(pressure: Optional[float], cfg: Dict[str, Any]) -> str:
    if pressure is None:
        return "unknown"

    c2_cutoff = cfg["pressure_windows"]["C2_CUTOFF"]
    c_cutoff = cfg["pressure_windows"]["C_PRESS_CUTOFF"]

    if pressure <= c2_cutoff:
        return "C2"
    if pressure <= c_cutoff:
        return "C1"
    return "mild_or_normal"


def _build_flags(values: TympEarValues, cfg: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    red_flags: List[str] = []
    notes: List[str] = []

    ranges = cfg["ranges"]

    missing = []
    for k, v in asdict(values).items():
        if v is None:
            missing.append(k)

    if missing:
        red_flags.append(f"Thiếu dữ liệu: {', '.join(missing)}.")
        notes.append("Một hoặc nhiều chỉ số không đọc được; độ tin cậy diễn giải giảm.")

    if not _in_range(values.ecv_ml, ranges["ecv_ml"]):
        red_flags.append("ECV ngoài khoảng hợp lý → cân nhắc lỗi đo/không đúng lứa tuổi/đọc sai.")
        notes.append(f"ECV={_fmt(values.ecv_ml)}; range_sanity={ranges['ecv_ml']}")

    if not _in_range(values.compliance_ml, ranges["compliance_ml"]):
        red_flags.append("Compliance ngoài khoảng hợp lý → cân nhắc lỗi đo/đọc sai.")
        notes.append(f"Compliance={_fmt(values.compliance_ml)}; range_sanity={ranges['compliance_ml']}")

    if not _in_range(values.pressure_dapa, ranges["pressure_dapa"]):
        red_flags.append("Pressure ngoài khoảng hợp lý → cân nhắc lỗi đo/đọc sai.")
        notes.append(f"Pressure={_fmt(values.pressure_dapa)}; range_sanity={ranges['pressure_dapa']}")

    if not _in_range(values.gradient_dapa, ranges["gradient_dapa"]):
        red_flags.append("Gradient ngoài khoảng hợp lý → cân nhắc lỗi đo/đọc sai.")
        notes.append(f"Gradient={_fmt(values.gradient_dapa)}; range_sanity={ranges['gradient_dapa']}")

    low_ecv_hint = 0.3
    if values.ecv_ml is not None and values.ecv_ml < low_ecv_hint:
        red_flags.append("ECV rất thấp → nghi tắc probe/đặt probe chưa kín/đặt sai.")
        notes.append("ECV thấp thường do kỹ thuật đo; nên đo lại trước khi kết luận.")

    return red_flags, notes


def interpret_ear(
    values: TympEarValues,
    tymp_type: Optional[str],
    cfg: Optional[Dict[str, Any]] = None,
) -> TympInterpretation:
    cfg = cfg or DEFAULT_TYMP_CFG
    t = _normalize_type(tymp_type)

    red_flags, notes = _build_flags(values, cfg)

    possible_causes: List[str] = []
    suggest_next_steps: List[str] = []
    summary_parts: List[str] = []

    suggest_next_steps.extend([
        "Đối chiếu triệu chứng (đau tai, nghẹt tai, nghe kém) và soi tai.",
        "Kết hợp thính lực đồ/nhĩ lượng đồ bên đối diện và phản xạ cơ bàn đạp nếu có."
    ])

    high_ecv_hint = cfg["ecv_hints"]["HIGH_ECV_HINT"]

    if t == "A":
        summary_parts.append("Nhĩ lượng đồ type A gợi ý chức năng tai giữa trong giới hạn bình thường.")
        possible_causes.append("Không gợi ý bất thường tai giữa rõ trên nhĩ lượng đồ.")
        suggest_next_steps.append("Nếu vẫn có triệu chứng: cân nhắc bệnh lý khác và đánh giá thêm.")

    elif t == "As":
        summary_parts.append("Nhĩ lượng đồ type As gợi ý giảm di động hệ thống tai giữa.")
        possible_causes.extend([
            "Xơ nhĩ (tympanosclerosis) / dày màng nhĩ.",
            "Nghi otosclerosis nếu lâm sàng phù hợp."
        ])
        suggest_next_steps.append("Cân nhắc đo lại/đối chiếu với thính lực đồ và soi tai.")

    elif t == "Ad":
        summary_parts.append("Nhĩ lượng đồ type Ad gợi ý tăng di động hệ thống tai giữa.")
        possible_causes.extend([
            "Gián đoạn chuỗi xương con nếu có tiền sử phù hợp.",
            "Màng nhĩ mỏng/teo."
        ])
        suggest_next_steps.append("Soi tai kỹ; cân nhắc đánh giá chuyên khoa.")

    elif t.startswith("B"):
        ecv = values.ecv_ml
        if ecv is None:
            summary_parts.append("Nhĩ lượng đồ type B (đường cong phẳng). Cần ECV để định hướng nguyên nhân.")
            possible_causes.append("Có thể gặp trong OME hoặc thủng màng nhĩ/ống thông khí; cũng có thể do kỹ thuật đo.")
            suggest_next_steps.insert(0, "Khuyến nghị đo lại để có ECV và xác nhận type B.")
            red_flags.append("Type B nhưng thiếu ECV → không đủ dữ liệu để phân nhánh nguyên nhân.")
        else:
            if ecv < 0.3:
                summary_parts.append("Type B kèm ECV thấp gợi ý tắc probe/đặt probe chưa đúng hoặc ống tai bị bít.")
                possible_causes.extend([
                    "Tắc probe do ráy tai/đặt probe không kín.",
                    "Lỗi kỹ thuật đo."
                ])
                suggest_next_steps.insert(0, "Đo lại nhĩ lượng đồ sau khi kiểm tra probe và ống tai.")
                red_flags.append("Ưu tiên kiểm tra kỹ thuật đo trước khi diễn giải bệnh lý.")
            elif ecv >= high_ecv_hint:
                summary_parts.append("Type B kèm ECV cao gợi ý thủng màng nhĩ hoặc có ống thông khí.")
                possible_causes.extend([
                    "Thủng màng nhĩ.",
                    "Có ống thông khí (grommet) / lỗ thông."
                ])
                suggest_next_steps.insert(0, "Soi tai để xác định thủng màng nhĩ/ống thông khí.")
                red_flags.append("Nếu kèm chảy tai/đau/sốt → cần đánh giá sớm.")
            else:
                summary_parts.append("Type B kèm ECV trong giới hạn hợp lý gợi ý có dịch tai giữa (OME).")
                possible_causes.extend([
                    "Viêm tai giữa thanh dịch (OME).",
                    "Rối loạn thông khí tai giữa do rối loạn vòi nhĩ."
                ])
                suggest_next_steps.insert(0, "Theo dõi/điều trị theo phác đồ và đánh giá lại.")

    elif t.startswith("C"):
        sev = _pressure_severity(values.pressure_dapa, cfg)
        if sev == "C2":
            summary_parts.append("Type C (áp lực âm rõ/C2) gợi ý rối loạn vòi nhĩ và áp lực tai giữa âm nhiều.")
            possible_causes.extend([
                "Rối loạn vòi nhĩ (ETD).",
                "Giai đoạn sớm hoặc hồi phục của OME/viêm tai giữa."
            ])
            suggest_next_steps.insert(0, "Theo dõi sát và điều trị theo lâm sàng; cân nhắc tái khám/đo lại.")
            red_flags.append("Áp lực âm nhiều (≈ C2) → nếu triệu chứng nặng hoặc kéo dài, cân nhắc đánh giá chuyên khoa.")
        elif sev == "C1":
            summary_parts.append("Type C (C1) gợi ý áp lực tai giữa âm mức vừa, thường liên quan rối loạn vòi nhĩ.")
            possible_causes.extend([
                "Rối loạn vòi nhĩ (ETD).",
                "Sau viêm đường hô hấp trên/viêm mũi xoang."
            ])
            suggest_next_steps.insert(0, "Theo dõi và điều trị tùy triệu chứng; đo lại để đánh giá xu hướng.")
        else:
            summary_parts.append("Type C gợi ý áp lực tai giữa âm; cần đối chiếu pressure để phân mức.")
            possible_causes.append("Rối loạn vòi nhĩ (ETD) là khả năng thường gặp.")
            suggest_next_steps.insert(0, "Đo lại/đối chiếu pressure để phân mức C1/C2 và theo dõi.")

    else:
        summary_parts.append("Không xác định được Jerger type đáng tin cậy để diễn giải.")
        possible_causes.append("Dữ liệu/đường cong không đủ hoặc phân loại không chắc chắn.")
        suggest_next_steps.insert(0, "Khuyến nghị đo lại nhĩ lượng đồ hoặc kiểm tra chất lượng ảnh/OCR.")

    metrics = (
        f"ECV={_fmt(values.ecv_ml, ' ml')}, "
        f"Compliance={_fmt(values.compliance_ml, ' ml')}, "
        f"Pressure={_fmt(values.pressure_dapa, ' daPa')}, "
        f"Gradient={_fmt(values.gradient_dapa)}"
    )
    notes.append(f"Chỉ số: {metrics}")
    notes.append(f"Jerger type: {t}")

    conf = 1.0
    missing_count = sum(
        1 for v in [values.ecv_ml, values.compliance_ml, values.pressure_dapa, values.gradient_dapa]
        if v is None
    )
    conf -= 0.12 * missing_count

    ranges = cfg["ranges"]
    if not _in_range(values.ecv_ml, ranges["ecv_ml"]):
        conf -= 0.15
    if not _in_range(values.compliance_ml, ranges["compliance_ml"]):
        conf -= 0.15
    if not _in_range(values.pressure_dapa, ranges["pressure_dapa"]):
        conf -= 0.15
    if not _in_range(values.gradient_dapa, ranges["gradient_dapa"]):
        conf -= 0.08

    if values.ecv_ml is not None and values.ecv_ml < 0.3:
        conf -= 0.10

    conf = max(0.05, min(1.0, conf))

    def dedup(xs: List[str]) -> List[str]:
        seen = set()
        out = []
        for x in xs:
            if x and x not in seen:
                out.append(x)
                seen.add(x)
        return out

    return TympInterpretation(
        summary_vi=" ".join(summary_parts).strip(),
        possible_causes=dedup(possible_causes),
        suggest_next_steps=dedup(suggest_next_steps),
        red_flags=dedup(red_flags),
        confidence=float(f"{conf:.2f}"),
        notes=dedup(notes),
    )


def overall_summary(
    right: Optional[TympInterpretation],
    left: Optional[TympInterpretation],
) -> str:
    parts: List[str] = []

    if right:
        parts.append(f"Tai phải: {right.summary_vi}")
    if left:
        parts.append(f"Tai trái: {left.summary_vi}")

    rf = []
    if right and right.red_flags:
        rf.extend([f"Tai phải: {x}" for x in right.red_flags])
    if left and left.red_flags:
        rf.extend([f"Tai trái: {x}" for x in left.red_flags])

    if rf:
        parts.append("Cảnh báo: " + " | ".join(rf))

    return "\n".join(parts).strip()


def interpretation_to_dict(it: TympInterpretation) -> Dict[str, Any]:
    return asdict(it)