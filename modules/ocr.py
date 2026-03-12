import pytesseract
import cv2
import numpy as np
from PIL import Image

def set_tesseract_path(tesseract_exe: str):
    pytesseract.pytesseract.tesseract_cmd = tesseract_exe

def preprocess_for_ocr(pil_img: Image.Image) -> np.ndarray:
    # PIL -> OpenCV (BGR)
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    # grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # tăng tương phản + khử nhiễu nhẹ
    gray = cv2.bilateralFilter(gray, 7, 50, 50)

    # adaptive threshold để bắt chữ trên scan tốt hơn
    th = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )

    return th

def ocr_text(pil_img: Image.Image, lang: str = "vie+eng") -> str:
    th = preprocess_for_ocr(pil_img)
    config = r"--oem 3 --psm 6"
    text = pytesseract.image_to_string(th, lang=lang, config=config)
    return text