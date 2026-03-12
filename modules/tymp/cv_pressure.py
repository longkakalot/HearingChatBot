# modules/tymp/cv_pressure.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, List

import numpy as np
import cv2
from PIL import Image
import pytesseract
import re


@dataclass
class TympCVResult:
    peak_pressure_dapa: Optional[float]
    quality: float  # 0..1
    debug: Dict[str, float]


def _pil_to_gray(img: Image.Image) -> np.ndarray:
    arr = np.array(img.convert("RGB"))
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return gray


def _map_x_to_pressure_dapa(x: float, plot_w: int) -> float:
    # -600..+300 => span 900
    return -600.0 + (x / max(1, plot_w)) * 900.0


# ----------------------------
# Plot detection using OCR axis tokens (-600 / -300 / 300)
# ----------------------------
def _find_plot_boxes_by_axis_ocr(page_img: Image.Image) -> List[Tuple[int, int, int, int]]:
    gray = _pil_to_gray(page_img)
    H, W = gray.shape[:2]

    config = r"--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789-"
    data = pytesseract.image_to_data(gray, lang="eng", config=config, output_type=pytesseract.Output.DICT)

    axis_tokens = []
    for i in range(len(data["text"])):
        t = (data["text"][i] or "").strip()
        if not t:
            continue
        conf = float(data["conf"][i]) if str(data["conf"][i]).strip() != "-1" else -1.0
        if conf != -1.0 and conf < 30:
            continue

        if re.fullmatch(r"-?\d{3}", t) is None:
            continue
        val = int(t)
        if val not in (-600, -300, 300, 600):
            continue

        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        if y > H * 0.60:
            continue

        axis_tokens.append({"x": x, "y": y, "w": w, "h": h, "cx": x + w / 2})

    if not axis_tokens:
        return []

    midx = W / 2
    left_tokens = [a for a in axis_tokens if a["cx"] < midx]
    right_tokens = [a for a in axis_tokens if a["cx"] >= midx]

    def build_box(tokens: List[dict]) -> Optional[Tuple[int, int, int, int]]:
        if not tokens:
            return None

        xs = [t["x"] for t in tokens]
        ys = [t["y"] for t in tokens]
        hs = [t["h"] for t in tokens]

        x_min = min(xs)
        x_max = max(t["x"] + t["w"] for t in tokens)

        y_axis = int(np.median(ys))
        h_med = int(np.median(hs))

        pad_x = int(W * 0.012)
        pad_up = int(H * 0.12)
        pad_down = int(H * 0.03)

        x1 = max(0, x_min - pad_x)
        x2 = min(W, x_max + pad_x)
        y1 = max(0, y_axis - pad_up)
        y2 = min(H, y_axis + pad_down + 2 * h_med)

        return (x1, y1, x2 - x1, y2 - y1)

    box_left = build_box(left_tokens)
    box_right = build_box(right_tokens)

    boxes = []
    if box_left:
        boxes.append(box_left)
    if box_right:
        boxes.append(box_right)

    boxes.sort(key=lambda b: b[0])
    return boxes[:2]


# ----------------------------
# Curve extraction by column profile (robust to broken curve)
# ----------------------------
def _curve_profile_peak_x(plot_gray: np.ndarray) -> Tuple[Optional[float], float, Dict[str, float]]:
    """
    Trả về (peak_x, quality, debug)
    peak_x tính theo hệ toạ độ plot sau khi cắt lề.
    """

    H, W = plot_gray.shape[:2]

    # 1) Cắt lề để tránh dính trục/viền (rất quan trọng)
    lmx = int(W * 0.07)   # bỏ 7% trái
    rmx = int(W * 0.04)   # bỏ 4% phải
    tmy = int(H * 0.05)   # bỏ 5% trên
    #bmy = int(H * 0.08)   # bỏ 8% dưới (hay dính số trục)
    bmy = int(H * 0.18)  # bỏ đáy nhiều hơn để tránh dính số trục/daPa
    roi = plot_gray[tmy:max(tmy + 10, H - bmy), lmx:max(lmx + 10, W - rmx)]
    Hr, Wr = roi.shape[:2]

    # 2) Binarize + remove grid lines
    bw = cv2.adaptiveThreshold(
        roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 7
    )

    # remove long lines (grid/axes) - vừa đủ, không quá mạnh
    horiz = cv2.morphologyEx(
        bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (45, 1))
    )
    vert = cv2.morphologyEx(
        bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 45))
    )
    lines = cv2.bitwise_or(horiz, vert)
    curve = cv2.bitwise_and(bw, cv2.bitwise_not(lines))

    # làm sạch nhẹ
    curve = cv2.morphologyEx(curve, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)

    ys, xs = np.where(curve > 0)
    if len(xs) < 200:
        return None, 0.0, {"pix": float(len(xs)), "roi_w": float(Wr), "roi_h": float(Hr)}

    # 3) profile theo cột x: lấy y nhỏ nhất (điểm cao nhất) của mỗi cột
    y_top = np.full((Wr,), np.nan, dtype=np.float32)

    # gom theo x
    for x in range(Wr):
        col = np.where(curve[:, x] > 0)[0]
        if col.size > 0:
            y_top[x] = float(col.min())

    valid = np.isfinite(y_top)
    valid_count = int(valid.sum())
    coverage = valid_count / max(1, Wr)

    # nếu coverage thấp quá -> curve đứt nhiều, vẫn cho nhưng quality thấp
    if valid_count < 40:
        return None, 0.0, {"coverage": float(coverage), "valid_cols": float(valid_count)}

    # 4) interpolate gaps + smooth (moving average)
    # fill gaps bằng nearest
    idx = np.arange(Wr)
    y_filled = y_top.copy()
    y_filled[~valid] = np.interp(idx[~valid], idx[valid], y_top[valid])

    # smooth
    win = max(7, int(Wr * 0.03) | 1)  # window lẻ
    kernel = np.ones((win,), dtype=np.float32) / win
    y_smooth = np.convolve(y_filled, kernel, mode="same")

    # 5) peak = min y (cao nhất)
    peak_x = float(np.argmin(y_smooth))

    # tránh peak sát biên (dễ nhầm trục)
    edge_bad = 0.0
    if peak_x < Wr * 0.08 or peak_x > Wr * 0.92:
        edge_bad = 0.6

    # quality: coverage + pixel density - edge penalty
    pix_density = min(1.0, len(xs) / (Wr * Hr * 0.08))
    q = max(0.0, min(1.0, 0.55 * coverage + 0.45 * pix_density - edge_bad))

    dbg = {
        "roi_w": float(Wr),
        "roi_h": float(Hr),
        "pix": float(len(xs)),
        "coverage": float(coverage),
        "valid_cols": float(valid_count),
        "win": float(win),
        "peak_x": float(peak_x),
        "edge_penalty": float(edge_bad),
    }

    # peak_x đang theo roi; trả peak_x theo plot gốc
    peak_x_in_plot = peak_x + lmx
    return float(peak_x_in_plot), float(q), dbg


def extract_peak_pressure_from_page(page_img: Image.Image) -> Tuple[TympCVResult, TympCVResult]:
    gray_page = _pil_to_gray(page_img)
    H, W = gray_page.shape[:2]

    boxes = _find_plot_boxes_by_axis_ocr(page_img)
    if len(boxes) != 2:
        empty = TympCVResult(None, 0.0, {
            "found_boxes": float(len(boxes)),
            "page_w": float(W),
            "page_h": float(H),
            "method": 0.0
        })
        return empty, empty

    results: List[TympCVResult] = []
    for (x, y, w, h) in boxes:
        pad = int(min(w, h) * 0.03)
        x1 = max(0, x + pad); y1 = max(0, y + pad)
        x2 = min(W, x + w - pad); y2 = min(H, y + h - pad)
        # plot = gray_page[y1:y2, x1:x2]
        plot_full = gray_page[y1:y2, x1:x2]

        # CHỈ LẤY VÙNG ĐỒ THỊ TYMP (PHẦN TRÊN), LOẠI REFLEX
        ph, pw = plot_full.shape[:2]
        cut_top = int(ph * 0.02)          # bỏ mép trên chút
        cut_bottom = int(ph * 0.55)       # chỉ lấy ~55% phía trên
        plot = plot_full[cut_top:cut_bottom, :]

        peak_x, q, dbg = _curve_profile_peak_x(plot)

        if peak_x is None:
            results.append(TympCVResult(
                peak_pressure_dapa=None,
                quality=q,
                debug={
                    "plot_w": float(plot.shape[1]),
                    "plot_h": float(plot.shape[0]),
                    "method": 1.0,
                    **dbg
                }
            ))
        else:
            pressure = _map_x_to_pressure_dapa(peak_x, plot.shape[1])
            results.append(TympCVResult(
                peak_pressure_dapa=pressure,
                quality=q,
                debug={
                    "plot_w": float(plot.shape[1]),
                    "plot_h": float(plot.shape[0]),
                    "method": 1.0,
                    **dbg
                }
            ))

    # results[0]=plot trái, results[1]=plot phải
    return results[0], results[1]