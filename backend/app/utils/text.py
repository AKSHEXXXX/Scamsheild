import re

def preprocess_text(text: str) -> str:
    # ponytail: collapse spaced single chars before any ML sees them
    # "U R G E N T" -> "URGENT", defeats F-07 evasion
    text = re.sub(r'(\w)(?: \1)*(?: (\w))+', lambda m: re.sub(r' ', '', m.group(0)), text)
    text = re.sub(r'(?<!\w)(\w) (\w) (\w)', lambda m: m.group(0).replace(' ', ''), text)
    # general: collapse repeated single-letter-space sequences
    text = re.sub(r'([A-Za-z]) (?=[A-Za-z] )', lambda m: m.group(1), text)
    text = re.sub(r'\s+', ' ', text.strip().lower())
    return text
