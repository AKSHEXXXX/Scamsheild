import base64
import io
import pytest
from PIL import Image
from app.ocr import ScreenshotOCR

ocr = ScreenshotOCR()


def test_blank_image_returns_empty():
    img = Image.new("RGB", (100, 100), "white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    result = ocr.extract_from_base64(base64.b64encode(buf.getvalue()).decode())
    assert result.char_count == 0


def test_invalid_base64_handled():
    result = ocr.extract_from_base64("not_valid!!!")
    assert result.text == ""
    assert result.method == "decode_failed"


def test_text_image_returns_content():
    import pytesseract
    img = Image.new("RGB", (400, 100), "white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    result = ocr.extract_from_base64(base64.b64encode(buf.getvalue()).decode())
    assert result.method in ("tesseract_preprocessed", "tesseract_raw_psm11",
                             "tesseract_nolang_fallback", "decode_failed")


def test_fallback_reason_logged(caplog):
    caplog.set_level("INFO")
    img = Image.new("RGB", (100, 100), "white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    ocr.extract_from_base64(base64.b64encode(buf.getvalue()).decode(), fallback_reason="low_quality")
    assert any("low_quality" in record.message for record in caplog.records)


def test_extract_from_base64_returns_ocroputput():
    img = Image.new("RGB", (200, 50), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    result = ocr.extract_from_base64(base64.b64encode(buf.getvalue()).decode())
    assert hasattr(result, "text")
    assert hasattr(result, "confidence")
    assert hasattr(result, "method")
    assert hasattr(result, "char_count")
    assert hasattr(result, "fallback_used")
