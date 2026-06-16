import joblib
import numpy as np
import os
import logging
from app.ml.url_model import extract_url_features

logger = logging.getLogger("scamshield.ml.qr")

_model = None
_scaler = None
_cols = None

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


def _load():
    global _model, _scaler, _cols
    if _model is not None:
        return
    for name in ("qr_url_classifier.pkl", "qr_url_scaler.pkl", "qr_url_features.pkl"):
        if not os.path.exists(os.path.join(ARTIFACT_DIR, name)):
            logger.warning("QR model files not found — falling back")
            return
    _model = joblib.load(os.path.join(ARTIFACT_DIR, "qr_url_classifier.pkl"))
    _scaler = joblib.load(os.path.join(ARTIFACT_DIR, "qr_url_scaler.pkl"))
    _cols = joblib.load(os.path.join(ARTIFACT_DIR, "qr_url_features.pkl"))
    logger.info("QR URL classifier loaded (%d features)", len(_cols))


def predict_qr_url_risk(url: str) -> float:
    _load()
    if _model is None or _scaler is None or _cols is None:
        return -1.0
    feats = extract_url_features(url)
    X = np.array([[feats.get(c, 0) for c in _cols]])
    X_s = _scaler.transform(X)
    prob = float(_model.predict_proba(X_s)[0][1])
    return prob
