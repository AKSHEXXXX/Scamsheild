import joblib
import numpy as np
import os
import re
import logging
from urllib.parse import urlparse

from app.ml.url_features import extract_url_features

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
