import logging
import joblib
from pathlib import Path
from typing import Any

logger = logging.getLogger("scamshield.agent.7.upi.meta.xgb")
HERE = Path(__file__).resolve().parent
_MODEL_DIR = HERE / "model"
_cache: dict[str, Any] = {}

def _load() -> bool:
    if "loaded" in _cache:
        return _cache["loaded"]
    try:
        clf = joblib.load(_MODEL_DIR / "upi_xgb_classifier.pkl")
        sc = joblib.load(_MODEL_DIR / "upi_xgb_scaler.pkl")
        cols = joblib.load(_MODEL_DIR / "upi_xgb_feature_cols.pkl")
        _cache["classifier"] = clf
        _cache["scaler"] = sc
        _cache["feature_cols"] = cols
        _cache["loaded"] = True
        logger.info("[Agent 7] UPI Meta XGBoost loaded from %s", _MODEL_DIR)
        return True
    except Exception as e:
        logger.warning("[Agent 7] Could not load model: %s", e)
        _cache["loaded"] = False
        return False

def predict_upi(transaction: dict) -> dict:
    if not _load():
        return {"verdict": "error", "score": -1, "reasons": ["model not loaded"], "metadata": {}}
    try:
        import numpy as np
        clf = _cache["classifier"]
        sc = _cache["scaler"]
        cols = _cache["feature_cols"]
        feats = {
            "amount": float(transaction.get("amount", 0)),
            "has_note": 1 if transaction.get("note", "") else 0,
            "note_len": len(transaction.get("note", "")),
            "vpa_len": len(transaction.get("vpa", "")),
        }
        vec = np.array([[feats.get(c, 0) for c in cols]], dtype=np.float32)
        vec_scaled = sc.transform(vec)
        proba = clf.predict_proba(vec_scaled)[0]
        scam_idx = 1 if proba.shape[0] > 1 else 0
        score = int(round(proba[scam_idx] * 100))
        verdict = "high_risk" if score >= 70 else ("suspicious" if score >= 35 else "safe")
        return {"verdict": verdict, "score": score, "reasons": [], "metadata": {"probability": float(proba[scam_idx])}}
    except Exception as e:
        logger.warning("[Agent 7] predict_upi error: %s", e)
        return {"verdict": "error", "score": -1, "reasons": [str(e)], "metadata": {}}
