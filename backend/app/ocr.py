import base64
import io
from PIL import Image
import pytesseract

def run_ocr(image_b64: str) -> str:
    image_data = base64.b64decode(image_b64)
    img = Image.open(io.BytesIO(image_data))
    if img.mode != "RGB":
        img = img.convert("RGB")
    text = pytesseract.image_to_string(img)
    return text.strip()