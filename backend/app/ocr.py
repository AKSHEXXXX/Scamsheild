import base64
import io
import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class OCROutput:
    text: str
    confidence: float
    method: str
    char_count: int
    fallback_used: bool


class ScreenshotOCR:
    """
    Tesseract OCR optimized for Indian mobile app screenshots.
    Pipeline: denoise -> upscale -> binarize -> deskew -> Tesseract.
    """

    TESS_CONFIG_PRIMARY = r'--oem 3 --psm 6 -l eng+hin'
    TESS_CONFIG_FALLBACK = r'--oem 3 --psm 11 -l eng+hin'
    MIN_TEXT_LENGTH = 10

    def extract_from_base64(self, image_b64: str, fallback_reason: Optional[str] = None) -> OCROutput:
        if fallback_reason:
            logger.info(f"Backend OCR. Client fallback reason: {fallback_reason}")
        try:
            image_bytes = base64.b64decode(image_b64)
            pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as e:
            logger.error(f"Image decode failed: {e}")
            return OCROutput(text="", confidence=0.0, method="decode_failed", char_count=0, fallback_used=False)
        return self._run_ocr_pipeline(pil_image)

    def _run_ocr_pipeline(self, pil_image: Image.Image) -> OCROutput:
        preprocessed = self._preprocess(pil_image)

        text = self._run_tesseract(preprocessed, self.TESS_CONFIG_PRIMARY)
        if len(text.strip()) >= self.MIN_TEXT_LENGTH:
            confidence = self._estimate_confidence(preprocessed, self.TESS_CONFIG_PRIMARY)
            return OCROutput(text=text, confidence=confidence, method="tesseract_preprocessed",
                             char_count=len(text), fallback_used=False)

        logger.warning("Preprocessed OCR returned insufficient text. Trying raw + psm 11.")
        text_raw = self._run_tesseract(pil_image, self.TESS_CONFIG_FALLBACK)
        if len(text_raw.strip()) >= self.MIN_TEXT_LENGTH:
            return OCROutput(text=text_raw, confidence=0.5, method="tesseract_raw_psm11",
                             char_count=len(text_raw), fallback_used=True)

        text_nolang = self._run_tesseract(pil_image, r'--oem 3 --psm 6')
        return OCROutput(text=text_nolang, confidence=0.3, method="tesseract_nolang_fallback",
                         char_count=len(text_nolang), fallback_used=True)

    def _preprocess(self, pil_image: Image.Image) -> Image.Image:
        img = np.array(pil_image)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape
        if max(h, w) < 1000:
            scale = 1000 / max(h, w)
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        gray = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, blockSize=15, C=8)
        binary = self._deskew(binary)
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        binary = cv2.filter2D(binary, -1, kernel)
        return Image.fromarray(binary)

    def _deskew(self, image: np.ndarray) -> np.ndarray:
        coords = np.column_stack(np.where(image > 0))
        if len(coords) < 10:
            return image
        angle = cv2.minAreaRect(coords)[-1]
        if abs(angle) > 45:
            angle = -(90 + angle)
        if abs(angle) < 0.5:
            return image
        (h, w) = image.shape
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    def _run_tesseract(self, image: Image.Image, config: str) -> str:
        try:
            return pytesseract.image_to_string(image, config=config)
        except Exception as e:
            logger.error(f"Tesseract error: {e}")
            return ""

    def _estimate_confidence(self, image: Image.Image, config: str) -> float:
        try:
            data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
            confs = [int(c) for c in data['conf'] if str(c).lstrip('-').isdigit() and int(c) >= 0]
            return sum(confs) / len(confs) / 100.0 if confs else 0.5
        except Exception:
            return 0.5


screenshot_ocr = ScreenshotOCR()
