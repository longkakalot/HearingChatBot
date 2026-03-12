# modules/tymp_bilateral_rules.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class BilateralPattern:
    pattern: str
    clinical_suggestion: str
    notes: str


def detect_bilateral_pattern(type_r: str, type_l: str) -> BilateralPattern:

    pair = f"{type_r}-{type_l}"

    # Normalize order
    unordered = sorted([type_r, type_l])
    pair_sorted = "-".join(unordered)

    # ------------------------
    # Bilateral normal
    # ------------------------
    if type_r == "A" and type_l == "A":
        return BilateralPattern(
            pattern="Bilateral Type A",
            clinical_suggestion="Nhĩ lượng đồ hai tai trong giới hạn bình thường.",
            notes="Không gợi ý bệnh lý tai giữa rõ ràng.",
        )

    # ------------------------
    # Bilateral C
    # ------------------------
    if type_r == "C" and type_l == "C":
        return BilateralPattern(
            pattern="Bilateral Type C",
            clinical_suggestion="Gợi ý rối loạn chức năng vòi nhĩ hai bên.",
            notes="Thường gặp trong viêm mũi xoang, cảm lạnh hoặc giai đoạn sớm OME.",
        )

    # ------------------------
    # Bilateral B
    # ------------------------
    if type_r == "B" and type_l == "B":
        return BilateralPattern(
            pattern="Bilateral Type B",
            clinical_suggestion="Gợi ý dịch tai giữa hai bên (OME).",
            notes="Cần đối chiếu với soi tai và triệu chứng lâm sàng.",
        )

    # ------------------------
    # Unilateral B
    # ------------------------
    if "B" in [type_r, type_l] and "A" in [type_r, type_l]:
        return BilateralPattern(
            pattern="Unilateral Type B",
            clinical_suggestion="Gợi ý bất thường tai giữa một bên (OME hoặc thủng màng nhĩ).",
            notes="So sánh với tai đối diện bình thường.",
        )

    # ------------------------
    # Bilateral As
    # ------------------------
    if type_r == "As" and type_l == "As":
        return BilateralPattern(
            pattern="Bilateral Type As",
            clinical_suggestion="Giảm di động hệ thống tai giữa hai bên.",
            notes="Có thể gặp trong xơ nhĩ hoặc nghi otosclerosis.",
        )

    # ------------------------
    # Bilateral Ad
    # ------------------------
    if type_r == "Ad" and type_l == "Ad":
        return BilateralPattern(
            pattern="Bilateral Type Ad",
            clinical_suggestion="Tăng di động màng nhĩ hoặc chuỗi xương con hai bên.",
            notes="Cần đối chiếu với tiền sử chấn thương hoặc viêm tai.",
        )

    # ------------------------
    # Mixed pattern
    # ------------------------
    return BilateralPattern(
        pattern=f"Mixed pattern ({pair})",
        clinical_suggestion="Mẫu nhĩ lượng đồ hai tai không đối xứng.",
        notes="Cần đánh giá từng tai riêng biệt và đối chiếu lâm sàng.",
    )


def to_dict(obj: BilateralPattern) -> Dict[str, Any]:
    return asdict(obj)