import joblib
import numpy as np
import os
import re
import math
import logging
from urllib.parse import urlparse

logger = logging.getLogger("scamshield.ml.qr")

_model = None
_scaler = None
_cols = None

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


def is_loaded() -> bool:
    return all(os.path.exists(os.path.join(ARTIFACT_DIR, n))
               for n in ("qr_url_classifier.pkl", "qr_url_scaler.pkl", "qr_url_features.pkl"))


SUSPICIOUS_TLDS = {"xyz", "top", "club", "online", "site", "live", "work",
                   "shop", "click", "loan", "download", "review", "bid", "trade"}
SHORTENER_DOMAINS = {"bit.ly", "tinyurl.com", "tiny.cc", "t.co", "goo.gl",
                     "ow.ly", "is.gd", "buff.ly", "shorturl.at", "rb.gy",
                     "cutt.ly", "rebrand.ly", "bl.ink",
                     "adf.ly", "bc.vc", "prettylinkpro.com"}


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    prob = [float(s.count(c)) / len(s) for c in set(s)]
    return -sum(p * math.log2(p) for p in prob)


def extract_qr_url_features(url: str, payload_text: str = "") -> dict:
    parsed = urlparse(url)
    scheme = parsed.scheme
    host = parsed.hostname or ""
    path = parsed.path
    query = parsed.query
    fragment = parsed.fragment
    full_lower = url.lower()

    def has_word(w):
        return 1 if re.search(r'\b' + w + r'\b', full_lower) else 0

    brand_keywords = ["amazon", "google", "paytm", "phonepe", "flipkart",
                      "sbi", "hdfc", "icici", "axis", "kotak", "yesbank"]
    risk_keywords = ["free", "win", "prize", "offer", "lucky", "gift",
                     "cashback", "discount", "reward", "claim"]

    digits = sum(c.isdigit() for c in url)
    letters = sum(c.isalpha() for c in url)
    special = len(url) - digits - letters
    tld = host.split(".")[-1] if "." in host else ""

    domain_tokens = host.replace("-", ".").split(".")
    domain_token_length = sum(len(t) for t in domain_tokens) / max(1, len(domain_tokens))

    features = {
        "url_length": len(url),
        "normalized_url_length": round(len(url) / max(1, len(host) + len(path)), 4),
        "host_length": len(host),
        "path_length": len(path),
        "query_length": len(query),
        "fragment_length": len(fragment),
        "num_dots": url.count("."),
        "num_hyphens": url.count("-"),
        "num_underscores": url.count("_"),
        "num_slashes": url.count("/"),
        "num_question_marks": url.count("?"),
        "num_equals": url.count("="),
        "num_ampersands": url.count("&"),
        "num_percent": url.count("%"),
        "num_at": url.count("@"),
        "digit_count": digits,
        "letter_count": letters,
        "digit_ratio": round(digits / max(1, len(url)), 4),
        "special_char_count": special,
        "special_char_ratio": round(special / max(1, len(url)), 4),
        "entropy": round(_entropy(url), 4),
        "host_entropy": round(_entropy(host), 4),
        "path_entropy": round(_entropy(path), 4),
        "has_https": 1 if scheme == "https" else 0,
        "has_http": 1 if scheme == "http" else 0,
        "missing_scheme": 1 if not scheme else 0,
        "is_ip_host": 1 if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host) else 0,
        "has_port": 1 if ":" in host or (parsed.port is not None) else 0,
        "subdomain_count": max(0, len(host.split(".")) - 2),
        "domain_token_length": round(domain_token_length, 4),
        "tld_length": len(tld),
        "is_suspicious_tld": 1 if tld in SUSPICIOUS_TLDS else 0,
        "is_shortener": 1 if host in SHORTENER_DOMAINS else 0,
        "has_punycode": 1 if "xn--" in host else 0,
        "has_url_encoding": 1 if "%" in url else 0,
        "has_base64_like": 1 if re.search(r"[A-Za-z0-9+/]{40,}={0,2}", url) else 0,
        "has_hex_like": 1 if re.search(r"(?:%[0-9a-fA-F]{2}){3,}", url) else 0,
        "query_param_count": len(query.split("&")) if query else 0,
        "has_redirect_param": 1 if re.search(r"(redirect|return|next|continue|url=)", full_lower) else 0,
        "has_login_word": has_word("login"),
        "has_verify_word": has_word("verify"),
        "has_kyc_word": has_word("kyc"),
        "has_otp_word": has_word("otp"),
        "has_bank_word": has_word("bank"),
        "has_upi_word": has_word("upi"),
        "brand_keyword_count": sum(1 for kw in brand_keywords if kw in full_lower),
        "risk_word_count": sum(1 for kw in risk_keywords if kw in full_lower),
        "contains_rupee": 1 if "\u20b9" in url or "rs." in full_lower or "rupee" in full_lower else 0,
        "payload_is_plain_text": 1 if payload_text else 0,
        "payload_has_upi": 1 if re.search(r"[\w.\-]+@[\w]+", payload_text) else 0,
        "payload_has_phone": 1 if re.search(r"(?:\+91|91|0)?[6-9]\d{9}", payload_text) else 0,
    }
    return features


def _load():
    global _model, _scaler, _cols
    if _model is not None:
        return
    for name in ("qr_url_classifier.pkl", "qr_url_scaler.pkl", "qr_url_features.pkl"):
        if not os.path.exists(os.path.join(ARTIFACT_DIR, name)):
            logger.warning("QR model files not found ΓÇö falling back")
            return
    _model = joblib.load(os.path.join(ARTIFACT_DIR, "qr_url_classifier.pkl"))
    _scaler = joblib.load(os.path.join(ARTIFACT_DIR, "qr_url_scaler.pkl"))
    _cols = joblib.load(os.path.join(ARTIFACT_DIR, "qr_url_features.pkl"))
    logger.info("QR URL classifier loaded (%d features)", len(_cols))


def predict_qr_url_risk(url: str, payload_text: str = "") -> float:
    _load()
    if _model is None or _scaler is None or _cols is None:
        return -1.0
    feats = extract_qr_url_features(url, payload_text)
    X = np.array([[feats.get(c, 0) for c in _cols]])
    X_s = _scaler.transform(X)
    prob = float(_model.predict_proba(X_s)[0][1])
    return prob
