# modules/tymp.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Dict, Tuple, List

from PIL import Image, ImageOps
import pytesseract


@dataclass
class TympSide:
    volume_ml: Optional[float]
    compliance_ml: Optional[float]
    pressure_dapa: Optional[float]
    gradient_dapa: Optional[float]
    raw_text: str


# ---------------------------
# Utilities
# ---------------------------
def _to_float(s: str) -> Optional[float]:
    s = s.strip().replace(",", ".")
    if s in {"", "-", "—"}:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _norm_token(t: str) -> str:
    return re.sub(r"[^a-zA-Z]", "", t).lower()


def _is_number_token(t: str) -> bool:
    # chấp nhận -4, 0.55, 75
    return re.fullmatch(r"-?\d+(?:[.,]\d+)?", t.strip()) is not None


def _preprocess_table(img: Image.Image) -> Image.Image:
    # grayscale + autocontrast để tesseract thấy chữ rõ hơn
    g = ImageOps.grayscale(img)
    g = ImageOps.autocontrast(g)
    return g


# ---------------------------
# Cropping main table ROIs (Right/Left)
# ---------------------------
def crop_value_table_boxes(page_img: Image.Image) -> Tuple[Image.Image, Image.Image]:
    """
    Crop vùng chứa bảng thông số + một ít ngữ cảnh, nhưng hạn chế dính quá nhiều phần Reflex.
    Nếu anh thấy dính Reflex quá nhiều, có thể tăng y1 chút.
    """
    w, h = page_img.size

    # vùng dưới đồ thị, nơi có 2 dòng thông số
    y1 = int(h * 0.40)
    y2 = int(h * 0.60)

    # Right ear nằm bên trái trang, Left ear nằm bên phải trang
    right = page_img.crop((int(w * 0.05), y1, int(w * 0.50), y2))
    left  = page_img.crop((int(w * 0.50), y1, int(w * 0.97), y2))
    return right, left


# ---------------------------
# Core extraction using image_to_data
# ---------------------------
def _extract_from_table(table_img: Image.Image) -> Tuple[Dict[str, Optional[float]], str]:
    """
    Dò chữ 'Volume/Compliance/Pressure/Gradient' rồi lấy số gần nhất bên phải cùng hàng.
    """
    img = _preprocess_table(table_img)

    # data contains word-level boxes
    # psm 6: assume a block of text
    config = r"--oem 3 --psm 6"
    data = pytesseract.image_to_data(img, lang="eng", config=config, output_type=pytesseract.Output.DICT)

    n = len(data["text"])
    words: List[Dict] = []
    for i in range(n):
        txt = (data["text"][i] or "").strip()
        conf = float(data["conf"][i]) if str(data["conf"][i]).strip() != "-1" else -1.0
        if not txt:
            continue
        # lọc rác quá yếu
        if conf != -1.0 and conf < 30:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append(
            {"t": txt, "tn": _norm_token(txt), "conf": conf, "x": x, "y": y, "w": w, "h": h, "cx": x + w / 2, "cy": y + h / 2}
        )

    # build raw preview text
    raw_preview = " ".join([w["t"] for w in words])

    # find labels
    label_map = {
        "volume": "volume_ml",
        "compliance": "compliance_ml",
        "pressure": "pressure_dapa",
        "gradient": "gradient_dapa",
    }

    out: Dict[str, Optional[float]] = {v: None for v in label_map.values()}

    # helper: find nearest number token to the right in same row band
    def find_value_for_label(label_word) -> Optional[float]:
        lx = label_word["x"] + label_word["w"]  # right edge of label
        ly = label_word["cy"]
        # candidates: number tokens to the right, within a vertical tolerance
        cands = []
        for w in words:
            if not _is_number_token(w["t"]):
                continue
            if w["x"] <= lx:
                continue
            if abs(w["cy"] - ly) > max(12, label_word["h"] * 0.9):  # same row-ish
                continue
            # score: prefer closest on x
            dist = w["x"] - lx
            cands.append((dist, w["t"]))
        if not cands:
            return None
        cands.sort(key=lambda x: x[0])
        return _to_float(cands[0][1])

    # We might have OCR splitting "daPa" etc. Doesn’t matter; we only need label word itself.
    for lbl, key in label_map.items():
    # find label occurrences
        lbl_words = [w for w in words if w["tn"] == lbl]

        if not lbl_words:
            # sometimes OCR returns 'volum' or 'pressur'... allow prefix match
            lbl_words = [w for w in words if w["tn"].startswith(lbl[:5])]

        # ✅ FIX: riêng compliance hay bị mất chữ đầu ("mpliance")
        if not lbl_words and lbl == "compliance":
            lbl_words = [w for w in words if w["tn"] == "mpliance" or w["tn"].endswith("mpliance")]

        if not lbl_words:
            continue

        lbl_words.sort(key=lambda w: (-(w["conf"] if w["conf"] != -1 else 0), w["x"]))
        v = find_value_for_label(lbl_words[0])
        out[key] = v



    # for lbl, key in label_map.items():
    #     # find label occurrences; pick the one with best confidence / left-most (usually)
    #     lbl_words = [w for w in words if w["tn"] == lbl]
    #     if not lbl_words:
    #         # sometimes OCR returns 'volum' or 'pressur'... allow prefix match
    #         lbl_words = [w for w in words if w["tn"].startswith(lbl[:5])]
    #     if not lbl_words:
    #         continue

    #     # choose the best label instance: high conf, then smallest x
    #     lbl_words.sort(key=lambda w: (-(w["conf"] if w["conf"] != -1 else 0), w["x"]))
    #     v = find_value_for_label(lbl_words[0])
    #     out[key] = v

    # validation (range)
    def validate(d: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
        dd = dict(d)
        if dd["volume_ml"] is not None and not (0.0 <= dd["volume_ml"] <= 5.0):
            dd["volume_ml"] = None
        if dd["compliance_ml"] is not None and not (0.0 <= dd["compliance_ml"] <= 5.0):
            dd["compliance_ml"] = None
        if dd["pressure_dapa"] is not None and not (-600.0 <= dd["pressure_dapa"] <= 300.0):
            dd["pressure_dapa"] = None
        if dd["gradient_dapa"] is not None and not (0.0 <= dd["gradient_dapa"] <= 300.0):
            dd["gradient_dapa"] = None
        return dd

    out = validate(out)
    return out, raw_preview


def extract_tymp_values(page_img: Image.Image) -> Tuple[TympSide, TympSide, Image.Image, Image.Image]:
    """
    Main API:
      return (right, left, right_table_img, left_table_img)
    """
    right_tbl, left_tbl = crop_value_table_boxes(page_img)

    r_vals, r_raw = _extract_from_table(right_tbl)
    l_vals, l_raw = _extract_from_table(left_tbl)

    right = TympSide(
        volume_ml=r_vals["volume_ml"],
        compliance_ml=r_vals["compliance_ml"],
        pressure_dapa=r_vals["pressure_dapa"],
        gradient_dapa=r_vals["gradient_dapa"],
        raw_text=r_raw,
    )
    left = TympSide(
        volume_ml=l_vals["volume_ml"],
        compliance_ml=l_vals["compliance_ml"],
        pressure_dapa=l_vals["pressure_dapa"],
        gradient_dapa=l_vals["gradient_dapa"],
        raw_text=l_raw,
    )

    return right, left, right_tbl, left_tbl