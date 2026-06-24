import re
import unicodedata

LEETMAP = {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "$": "s", "@": "a"}
PHONE_RE = re.compile(r"^\+?\d[\d\s\-\(\)]{6,}\d$")
UPI_RE = re.compile(r"^[\w\.\-]+@[\w\.\-]+$")
AMOUNT_RE = re.compile(r"^(?:Rs\.?|₹|INR)?\s*\d+\.?\d*\s*(?:/?-?\s*\d+\.?\d*)?$", re.IGNORECASE)
URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _is_vpa(token: str) -> bool:
    return bool(UPI_RE.match(token)) and "@" in token


def _is_phone(token: str) -> bool:
    return bool(PHONE_RE.match(token))


def _is_amount(token: str) -> bool:
    return bool(AMOUNT_RE.match(token.strip()))


def _is_url(token: str) -> bool:
    return bool(URL_RE.match(token))


def _is_wordlike(token: str) -> bool:
    if len(token) < 3:
        return False
    has_alpha = any(c.isalpha() for c in token)
    return has_alpha


def _apply_leetspeak(token: str) -> str:
    result = []
    for ch in token:
        result.append(LEETMAP.get(ch, ch))
    return "".join(result)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    tokens = text.split()
    normalized = []
    for token in tokens:
        if _is_vpa(token) or _is_phone(token) or _is_amount(token) or _is_url(token):
            normalized.append(token)
            continue
        if _is_wordlike(token):
            token = _apply_leetspeak(token)
        normalized.append(token)
    return " ".join(normalized)
