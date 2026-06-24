import re

def preprocess_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text.strip().lower())
