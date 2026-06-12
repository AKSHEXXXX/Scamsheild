import base64
import urllib.request
import json
from PIL import Image, ImageDraw, ImageFont
import io

text = """< Messages AMAZON.CON
ATTENTION: You have been fined $85.22 for failing to return Order No. #23442314. Please log in below within 48 hours to pay this fine or to apply for a waive.
https://shorturl.at/hlMNT
To opt out of future messages or to change your preferences, please click below.
https://shorturl.at/el148
Details"""

img = Image.new('RGB', (800, 600), color = (255, 255, 255))
d = ImageDraw.Draw(img)
d.text((10,10), text, fill=(0,0,0))

buffered = io.BytesIO()
img.save(buffered, format="PNG")
img_str = base64.b64encode(buffered.getvalue()).decode()

url = "https://scamsheild-production-2f8f.up.railway.app/api/v1/sandbox-image"
payload = {
    "image_base64": img_str,
    "os": "iOS"
}
data = json.dumps(payload).encode('utf-8')

req = urllib.request.Request(url, data=data)
req.add_header('Content-Type', 'application/json')
req.add_header('X-Device-Id', 'test-device')

try:
    with urllib.request.urlopen(req) as response:
        result = response.read()
        print("Status:", response.status)
        print("Response:", result.decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code)
    print("Response:", e.read().decode('utf-8'))

