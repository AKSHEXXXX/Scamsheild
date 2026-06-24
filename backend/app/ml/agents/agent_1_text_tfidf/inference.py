import logging
import joblib
from pathlib import Path
from typing import Any

logger = logging.getLogger("scamshield.agent.1.text.tfidf")
HERE = Path(__file__).resolve().parent
_MODEL_DIR = HERE / "model"
_cache: dict[str, Any] = {}

def _load() -> bool:
    if "loaded" in _cache:
        return _cache["loaded"]
    try:
        vec = joblib.load(_MODEL_DIR / "scamshield_vectorizer.pkl")
        clf = joblib.load(_MODEL_DIR / "scamshield_model.pkl")
        _cache["vectorizer"] = vec
        _cache["classifier"] = clf
        _cache["loaded"] = True
        logger.info("[Agent 1] TF-IDF + LogReg loaded from %s", _MODEL_DIR)
        return True
    except Exception as e:
        logger.warning("[Agent 1] Could not load model: %s", e)
        _cache["loaded"] = False
        return False

def predict_text(text: str) -> dict:
    if not _load():
        return {"verdict": "error", "score": -1, "reasons": ["model not loaded"], "metadata": {}}
    try:
        from app.utils.text import preprocess_text
        vec = _cache["vectorizer"]
        clf = _cache["classifier"]
        clean = preprocess_text(text)
        x = vec.transform([clean])
        proba = clf.predict_proba(x)[0]
        scam_idx = 1 if proba.shape[0] > 1 else 0
        score = int(round(proba[scam_idx] * 100))
        verdict = "high_risk" if score >= 70 else ("suspicious" if score >= 35 else "safe")
        return {"verdict": verdict, "score": score, "reasons": [], "metadata": {"probability": float(proba[scam_idx])}}
    except Exception as e:
        logger.warning("[Agent 1] predict_text error: %s", e)
        return {"verdict": "error", "score": -1, "reasons": [str(e)], "metadata": {}}
