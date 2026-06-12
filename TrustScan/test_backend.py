import base64
import requests
from PIL import Image, ImageDraw, ImageFont
import io

# Create an image with the text
text = """< Messages AMAZON.CON
ATTENTION: You have been fined $85.22 for failing to return Order No. #23442314. Please log in below within 48 hours to pay this fine or to apply for a waive.
https://shorturl.at/hlMNT
To opt out of future messages or to change your preferences, please click below.
https://shorturl.at/el148
Details"""

img = Image.new('RGB', (800, 600), color = (255, 255, 255))
d = ImageDraw.Draw(img)
# Using default font
d.text((10,10), text, fill=(0,0,0))

buffered = io.BytesIO()
img.save(buffered, format="PNG")
img_str = base64.b64encode(buffered.getvalue()).decode()

url = "https://scamsheild-production-2f8f.up.railway.app/api/v1/sandbox-image"
headers = {
    "Content-Type": "application/json",
    "X-Device-Id": "test-device",
    "Authorization": "Bearer fake_token" # Might be rejected if auth is strict, wait we'll see
}
payload = {
    "image_base64": img_str,
    "os": "iOS"
}

resp = requests.post(url, json=payload, headers=headers)
print("Status:", resp.status_code)
print("Response:", resp.text)
