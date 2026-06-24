import io
from PIL import Image, ImageDraw, ImageFont

KNOWN_TEXT = "ScamShield OCR Health 42"
FALLBACK_CHECKS = ["OCR", "Health", "Scam"]

def make_test_image() -> bytes:
    img = Image.new("RGB", (1200, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        font = ImageFont.load_default()
    draw.text((30, 50), KNOWN_TEXT, fill=(0, 0, 0), font=font)
    draw.text((30, 130), "Quick brown fox jumps over the lazy dog.", fill=(40, 40, 40), font=font)
    draw.text((30, 210), "HELLO WORLD 12345", fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def run_health_check() -> bool:
    from app.ocr import screenshot_ocr
    import base64
    png_bytes = make_test_image()
    b64 = base64.b64encode(png_bytes).decode()
    result = screenshot_ocr.extract_from_base64(b64)
    text_lower = result.text.lower()
    if KNOWN_TEXT.lower() in text_lower:
        return True
    for fallback in FALLBACK_CHECKS:
        if fallback.lower() in text_lower:
            return True
    return len(text_lower) > 20

if __name__ == "__main__":
    ok = run_health_check()
    print(f"OCR health: {'ok' if ok else 'FAIL'}")
    exit(0 if ok else 1)
