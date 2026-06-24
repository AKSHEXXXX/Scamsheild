import joblib
import numpy as np
import os
import re
import logging
from urllib.parse import urlparse

logger = logging.getLogger("scamshield.ml.url")

_model = None
_scaler = None
_cols = None

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


def is_loaded() -> bool:
    return all(os.path.exists(os.path.join(ARTIFACT_DIR, n))
               for n in ("url_classifier.pkl", "url_scaler.pkl", "url_feature_cols.pkl"))


def _load():
    global _model, _scaler, _cols
    if _model is not None:
        return
    for name in ("url_classifier.pkl", "url_scaler.pkl", "url_feature_cols.pkl"):
        if not os.path.exists(os.path.join(ARTIFACT_DIR, name)):
            logger.warning("URL model files not found in %s — falling back", ARTIFACT_DIR)
            return
    _model = joblib.load(os.path.join(ARTIFACT_DIR, "url_classifier.pkl"))
    _scaler = joblib.load(os.path.join(ARTIFACT_DIR, "url_scaler.pkl"))
    _cols = joblib.load(os.path.join(ARTIFACT_DIR, "url_feature_cols.pkl"))
    logger.info("URL classifier loaded (%d features)", len(_cols))


def extract_url_features(url: str) -> dict:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    path = parsed.path
    query = parsed.query

    def count_nums(s):
        return sum(c.isdigit() for c in s)

    def char_cont_rate(s):
        if len(s) <= 1:
            return 0.0
        alpha = sum(c.isalpha() for c in s)
        return round(alpha / len(s), 4)

    def url_char_prob(s):
        if not s:
            return 0.0
        ref_freq = {
            'a':0.082, 'b':0.015, 'c':0.028, 'd':0.043, 'e':0.127, 'f':0.022,
            'g':0.020, 'h':0.061, 'i':0.070, 'j':0.002, 'k':0.008, 'l':0.040,
            'm':0.024, 'n':0.067, 'o':0.075, 'p':0.019, 'q':0.001, 'r':0.060,
            's':0.063, 't':0.091, 'u':0.028, 'v':0.010, 'w':0.024, 'x':0.002,
            'y':0.020, 'z':0.001,
        }
        total = 0.0
        for ch in s.lower():
            if ch in ref_freq:
                total += ref_freq[ch]
            elif ch.isdigit():
                total += 0.005
            elif ch in ".-_/:":
                total += 0.002
            elif ch in "?=&%#@!$'()*+,;":
                total += 0.001
        return round(total / len(s), 4)

    parts = host.split(".")

    features = {
        "URLLength": len(url),
        "DomainLength": len(host),
        "TLDLength": len(parts[-1]) if len(parts) > 1 else 0,
        "NoOfSubDomain": max(0, len(parts) - 2),
        "NoOfEqualsInURL": url.count("="),
        "NoOfQMarkInURL": url.count("?"),
        "NoOfAmpersandInURL": url.count("&"),
        "CharContinuationRate": char_cont_rate(url),
        "URLCharProb": url_char_prob(url),
        "TLDLegitimateProb": 0.5,
        "IsHTTPS": 1 if url.startswith("https") else 0,
    }
    return features


def predict_url_risk(url: str) -> float:
    _load()
    if _model is None or _scaler is None or _cols is None:
        return -1.0
    feats = extract_url_features(url)
    X = np.array([[feats.get(c, 0) for c in _cols]])
    X_s = _scaler.transform(X)
    prob = float(_model.predict_proba(X_s)[0][1])
    return prob


def heuristic_url_score(url: str) -> float:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    path = parsed.path
    score = 0.0
    if not url.startswith("https"):
        score += 0.15
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host):
        score += 0.30
    subdomain_count = max(0, len(host.split(".")) - 2)
    if subdomain_count >= 3:
        score += 0.10
    if len(url) > 200:
        score += 0.10
    sensitive_keywords = ["login", "verify", "update", "secure", "account",
                          "confirm", "signin", "password", "otp", "auth"]
    for kw in sensitive_keywords:
        if kw in url.lower():
            score += 0.04
    return min(1.0, score)
