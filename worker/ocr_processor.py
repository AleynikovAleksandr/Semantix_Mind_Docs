import os

import cv2
import numpy as np
import pytesseract
from PIL import Image
from loguru import logger
from pdf2image import convert_from_path

# ==========================
# АБСОЛЮТНЫЕ ПУТИ
# ==========================
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

TESSERACT_CMD = os.getenv(
    "TESSERACT_CMD",
    os.path.join(BASE_DIR, "worker", "model", "tesseract", "tesseract"),
)

TESSDATA_PREFIX = os.getenv(
    "TESSDATA_PREFIX",
    os.path.join(BASE_DIR, "worker", "model", "tesseract", "tessdata"),
)

TESS_LANG = os.getenv("TESSERACT_LANG", "rus+eng")

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
os.environ["TESSDATA_PREFIX"] = TESSDATA_PREFIX

logger.info(f"Tesseract: {TESSERACT_CMD}")
logger.info(f"Tessdata: {TESSDATA_PREFIX}")


def _deskew(image: np.ndarray) -> np.ndarray:
    """Выравнивание наклона страницы."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    coords = np.column_stack(np.where(gray < 127))
    if len(coords) < 10:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.5:
        return image
    h, w = image.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(
        image,
        M,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def preprocess(img: np.ndarray) -> np.ndarray:
    """
    Полная предобработка для OCR:
    1. Оттенки серого
    2. Денойзинг
    3. Адаптивная бинаризация
    4. Выравнивание наклона
    """
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    binary = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2,
    )

    binary = _deskew(binary)

    return binary


def _ocr_single(img_array: np.ndarray) -> tuple[str, float]:
    """OCR одного изображения → (текст, уверенность)."""
    preprocessed = preprocess(img_array)
    pil_img = Image.fromarray(preprocessed)
    config = f"--oem 3 --psm 3 -l {TESS_LANG}"

    data = pytesseract.image_to_data(
        pil_img,
        config=config,
        output_type=pytesseract.Output.DICT,
    )
    text = pytesseract.image_to_string(pil_img, config=config)

    confidences = [int(c) for c in data["conf"] if str(c).lstrip("-").isdigit() and int(c) >= 0]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    return text, avg_conf


def process_file(file_path: str, mime_type: str) -> tuple[str, float, int]:
    """
    Главная функция OCR.
    Возвращает (full_text, avg_confidence_0_100, page_count).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    texts: list[str] = []
    confidences: list[float] = []

    if mime_type == "application/pdf":
        pages = convert_from_path(file_path, dpi=200)
        for i, page in enumerate(pages):
            img_array = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)
            t, c = _ocr_single(img_array)
            texts.append(t)
            confidences.append(c)
            logger.debug(f"  Страница {i + 1}: confidence={c:.1f}%")
        page_count = len(pages)
    else:
        img = cv2.imread(file_path)
        if img is None:
            raise ValueError(f"Не удалось прочитать изображение: {file_path}")
        t, c = _ocr_single(img)
        texts.append(t)
        confidences.append(c)
        page_count = 1

    full_text = "\n\n--- Страница ---\n\n".join(texts)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    logger.info(f"OCR завершён: {page_count} стр., уверенность={avg_conf:.1f}%")
    return full_text, avg_conf, page_count
