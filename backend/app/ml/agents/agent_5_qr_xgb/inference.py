import logging
import joblib
from pathlib import Path
from typing import Any

logger = logging.getLogger("scamshield.agent.5.qr.xgb")
HERE = Path(__file__).resolve().parent
_MODEL_DIR = HERE / "model"
_cache: dict[str, Any] = {}

def _load() -> bool:
    if "loaded" in _cache:
        return _cache["loaded"]
    try:
        import xgboost as xgb
        # Load UBJ model from artifacts if present, else fallback
        p_ubj = _MODEL_DIR.parent.parent.parent / "artifacts" / "qr_url_classifier.ubj"
        if not p_ubj.exists():
            p_ubj = _MODEL_DIR / "qr_url_classifier.ubj"
            
        if p_ubj.exists():
            clf = xgb.XGBClassifier()
            clf.load_model(str(p_ubj))
            
            # Load metrics to get feature order
            p_metrics = p_ubj.parent / "qr_model_report.json"
            cols = []
            if p_metrics.exists():
                import json
                with open(p_metrics) as f:
                    cols = json.load(f).get("feature_order", [])
            _cache["classifier"] = clf
            _cache["feature_cols"] = cols
            _cache["scaler"] = None
            _cache["loaded"] = True
            logger.info("[Agent 5] Native QR XGBoost loaded from %s", p_ubj)
            return True
        else:
            clf = joblib.load(_MODEL_DIR / "qr_url_classifier.pkl")
            sc = joblib.load(_MODEL_DIR / "qr_url_scaler.pkl")
            cols = joblib.load(_MODEL_DIR / "qr_url_features.pkl")
            _cache["classifier"] = clf
            _cache["scaler"] = sc
            _cache["feature_cols"] = cols
            _cache["loaded"] = True
            logger.info("[Agent 5] Legacy QR XGBoost loaded from %s", _MODEL_DIR)
            return True
    except Exception as e:
        logger.warning("[Agent 5] Could not load model: %s", e)
        _cache["loaded"] = False
        return False

def predict_qr(qr_string: str) -> dict:
    if not _load():
        return {"verdict": "error", "score": -1, "reasons": ["model not loaded"], "metadata": {}}
    try:
        import numpy as np
        clf = _cache["classifier"]
        sc = _cache["scaler"]
        cols = _cache["feature_cols"]
        
        if sc is None:
            # New 60-feature extractor
            from app.ml.agents.agent_5_qr_xgb.agent_05_feature_extractor import extract_features, triggered_features
            feats = extract_features(qr_string)
            row = np.array([[feats.get(c, 0.0) for c in cols]], dtype=np.float32)
            proba = clf.predict_proba(row)[0]
        else:
            # Legacy 13-feature extractor
            from app.ml.url_feature_extractor import extract_features
            from app.ml.agents.agent_5_qr_xgb.agent_05_feature_extractor import triggered_features
            feats = extract_features(qr_string)
            vec = np.array([[feats.get(c, 0) for c in cols]], dtype=np.float32)
            row_scaled = sc.transform(vec)
            proba = clf.predict_proba(row_scaled)[0]
            
        scam_idx = 1 if proba.shape[0] > 1 else 0
        prob = float(proba[scam_idx])
        score = int(round(prob * 100))
        
        # Load threshold from metrics if available
        threshold = 56.5
        p_metrics = (_MODEL_DIR.parent.parent.parent / "artifacts" / "qr_model_report.json")
        if p_metrics.exists():
            try:
                import json
                with open(p_metrics) as f:
                    threshold = float(json.load(f).get("selected_threshold", 0.565)) * 100
            except Exception:
                pass
                
        verdict = "high_risk" if score >= threshold else ("suspicious" if score >= (threshold / 2) else "safe")
        
        # Get triggered features
        from app.ml.agents.agent_5_qr_xgb.agent_05_feature_extractor import extract_features as raw_extractor
        raw_feats = raw_extractor(qr_string)
        trig = triggered_features(qr_string, raw_feats)
        
        return {
            "verdict": verdict,
            "score": score,
            "reasons": trig,
            "metadata": {"probability": prob, "triggered_features": trig}
        }
    except Exception as e:
        logger.warning("[Agent 5] predict_qr error: %s", e)
        return {"verdict": "error", "score": -1, "reasons": [str(e)], "metadata": {}}
