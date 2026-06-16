import os
import re
import joblib
import logging

logger = logging.getLogger("scamshield.ml.text")

_vectorizer = None
_classifier = None
_label_encoder = None
_rules = None
_available = False

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


def _load():
    global _vectorizer, _classifier, _label_encoder, _rules, _available
    if _available:
        return
    required = ["scamshield_vectorizer.pkl", "scamshield_model.pkl",
                "scamshield_label_encoder.pkl", "scamshield_rules.pkl"]
    for name in required:
        if not os.path.exists(os.path.join(ARTIFACT_DIR, name)):
            logger.warning("Text model file %s not found — falling back to rule-based", name)
            _available = False
            return
    _vectorizer = joblib.load(os.path.join(ARTIFACT_DIR, "scamshield_vectorizer.pkl"))
    _classifier = joblib.load(os.path.join(ARTIFACT_DIR, "scamshield_model.pkl"))
    _label_encoder = joblib.load(os.path.join(ARTIFACT_DIR, "scamshield_label_encoder.pkl"))
    _rules = joblib.load(os.path.join(ARTIFACT_DIR, "scamshield_rules.pkl"))
    _available = True
    logger.info("Text model loaded (vocab=%d, classes=%s)",
                len(_vectorizer.vocabulary_), _label_encoder.classes_.tolist())


def predict_text_scam(text: str) -> float:
    _load()
    if not _available:
        return -1.0
    try:
        X = _vectorizer.transform([text])
        proba = _classifier.predict_proba(X)[0]
        classes = _label_encoder.classes_.tolist()
        scam_idx = classes.index("scam") if "scam" in classes else 1
        return float(proba[scam_idx])
    except Exception as e:
        logger.error("Text inference error: %s", e)
        return -1.0


def get_rules() -> dict:
    _load()
    return _rules if _available else {}


def match_rules(text: str) -> dict:
    _load()
    if not _available or _rules is None:
        return {"matches": [], "score": 0.0}

    low = text.lower()
    matches = []

    for key in ["upi_regex", "phone_regex", "url_regex", "otp_regex", "amount_regex"]:
        pattern = _rules.get(key)
        if pattern and re.search(pattern, text):
            matches.append(key)

    for kw in _rules.get("high_risk_keywords", []):
        if kw.lower() in low:
            matches.append(f"hr_kw:{kw}")

    for kw in _rules.get("safe_keywords", []):
        if kw.lower() in low:
            matches.append(f"safe_kw:{kw}")

    return {"matches": matches, "score": min(1.0, len(matches) * 0.1)}
