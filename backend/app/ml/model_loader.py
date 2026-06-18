import logging
import json
import importlib.util
import warnings
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore")

logger = logging.getLogger("scamshield.ml")

MODEL_DIR = Path(__file__).resolve().parent / "artifacts"

_models: dict[str, Any] = {}
_accuracy: dict[str, Any] = {}

def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.warning("Could not load %s: %s", path.name, e)
        return {}

def _load_pickle(path: Path):
    import joblib
    try:
        return joblib.load(path)
    except Exception as e:
        logger.warning("Could not load %s: %s", path.name, e)
        return None

def _load_agent14_regex():
    p = MODEL_DIR / "scamshield_rules_v2.pkl"
    if not p.exists():
        p = MODEL_DIR / "scamshield_rules.pkl"
    obj = _load_pickle(p)
    if obj is not None:
        _models["agent14_regex_rules"] = obj
        logger.info("[STARTUP] Agent 14 — Regex Rule Engine loaded ✓")
    else:
        logger.error("[STARTUP] Agent 14 — Regex Rule Engine FAILED (no rules file)")

def _load_agent1_text():
    vec = _load_pickle(MODEL_DIR / "scamshield_vectorizer.pkl")
    clf = _load_pickle(MODEL_DIR / "scamshield_model.pkl")
    enc = _load_pickle(MODEL_DIR / "scamshield_label_encoder.pkl")
    if vec is not None and clf is not None:
        _models["agent1_vectorizer"] = vec
        _models["agent1_classifier"] = clf
        _models["agent1_label_encoder"] = enc
        try:
            rep = _load_json(MODEL_DIR / "scamshield_model_report.json")
            if not rep:
                rep = _load_json(MODEL_DIR / "eval_report.json")
            _accuracy["agent1"] = {"metric": "AUC", "value": rep.get("auc", rep.get("roc_auc", "N/A"))}
        except Exception:
            _accuracy["agent1"] = {"metric": "AUC", "value": "N/A"}
        logger.info("[STARTUP] Agent 1 — Text Scam Classifier (TF-IDF + LogReg) loaded ✓")
    else:
        logger.error("[STARTUP] Agent 1 — Text Scam Classifier FAILED")

def _load_agent2_distilbert():
    _accuracy["agent2"] = {"metric": "AUC", "value": "N/A (PyTorch model — not loaded)"}
    _models["agent2_available"] = False
    logger.info("[STARTUP] Agent 2 — DistilBERT FP16 skipped (requires PyTorch)")

def _load_agent3_url():
    clf = _load_pickle(MODEL_DIR / "url_xgb_classifier.pkl")
    sc = _load_pickle(MODEL_DIR / "url_xgb_scaler.pkl")
    cols = _load_pickle(MODEL_DIR / "url_xgb_feature_cols.pkl")
    if clf is not None and sc is not None and cols is not None:
        _models["agent3_classifier"] = clf
        _models["agent3_scaler"] = sc
        _models["agent3_feature_cols"] = cols
        rep = _load_json(MODEL_DIR / "url_model_report.json")
        _accuracy["agent3"] = {"metric": "AUC", "value": rep.get("auc", "N/A")}
        logger.info("[STARTUP] Agent 3 — URL Phishing Classifier (XGBoost) loaded ✓")
    else:
        logger.error("[STARTUP] Agent 3 — URL Phishing Classifier FAILED")
        _accuracy["agent3"] = {"metric": "AUC", "value": "N/A"}

def _load_agent4_blacklist():
    p = _load_pickle(MODEL_DIR / "phishing_domains.pkl")
    if p is not None:
        domains = p if isinstance(p, set) else p.get("domains", set())
        _models["agent4_blacklist"] = domains
        total = len(domains)
        _accuracy["agent4"] = {"metric": "Coverage", "value": f"{total} domains"}
        logger.info("[STARTUP] Agent 4 — URL Blacklist Checker loaded ✓ (%d domains)", total)
    else:
        logger.warning("[STARTUP] Agent 4 — URL Blacklist Checker FAILED, using Supabase blacklist only")
        _models["agent4_blacklist"] = set()
        _accuracy["agent4"] = {"metric": "Coverage", "value": "Supabase only"}

def _load_agent5_qr():
    clf = _load_pickle(MODEL_DIR / "qr_xgb_classifier.pkl")
    sc = _load_pickle(MODEL_DIR / "qr_xgb_scaler.pkl")
    cols = _load_pickle(MODEL_DIR / "qr_xgb_feature_cols.pkl")
    if clf is not None and sc is not None and cols is not None:
        _models["agent5_classifier"] = clf
        _models["agent5_scaler"] = sc
        _models["agent5_feature_cols"] = cols
        rep = _load_json(MODEL_DIR / "qr_model_report.json")
        _accuracy["agent5"] = {"metric": "AUC", "value": rep.get("auc", "N/A")}
        logger.info("[STARTUP] Agent 5 — QR Threat Classifier (XGBoost) loaded ✓")
    else:
        logger.error("[STARTUP] Agent 5 — QR Threat Classifier FAILED")
        _accuracy["agent5"] = {"metric": "AUC", "value": "N/A"}

def _load_agent6_upi_heuristic():
    try:
        spec = importlib.util.spec_from_file_location(
            "upi_heuristic_engine",
            Path(__file__).resolve().parent / "upi_heuristic_engine.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rules_path = MODEL_DIR / "upi_heuristic_rules.yaml"
        if rules_path.exists():
            engine = mod.UPIHeuristicEngine(str(rules_path))
            _models["agent6_upi_engine"] = engine
            _accuracy["agent6"] = {"metric": "Type", "value": "Rule-based: 100% deterministic"}
            logger.info("[STARTUP] Agent 6 — UPI Heuristic Rule Engine loaded ✓")
        else:
            logger.warning("[STARTUP] Agent 6 — UPI Heuristic rules YAML not found, skipping")
    except Exception as e:
        logger.warning("[STARTUP] Agent 6 — UPI Heuristic Rule Engine FAILED: %s", e)

def _load_agent7_upi_xgb():
    clf = _load_pickle(MODEL_DIR / "upi_xgb_classifier.pkl")
    sc = _load_pickle(MODEL_DIR / "upi_xgb_scaler.pkl")
    cols = _load_pickle(MODEL_DIR / "upi_xgb_feature_cols.pkl")
    if clf is not None and sc is not None and cols is not None:
        _models["agent7_classifier"] = clf
        _models["agent7_scaler"] = sc
        _models["agent7_feature_cols"] = cols
        rep = _load_json(MODEL_DIR / "upi_model_report.json")
        _accuracy["agent7"] = {"metric": "AUC", "value": rep.get("auc", "N/A")}
        logger.info("[STARTUP] Agent 7 — UPI Meta Classifier (XGBoost) loaded ✓")
    else:
        logger.warning("[STARTUP] Agent 7 — UPI Meta Classifier FAILED, skipping")
        _accuracy["agent7"] = {"metric": "AUC", "value": "N/A"}

def _load_agent8_brand_v1():
    whitelist = _load_pickle(MODEL_DIR / "brand_whitelist.pkl")
    config = _load_pickle(MODEL_DIR / "brand_guard_config.pkl")
    if whitelist is not None and config is not None:
        _models["agent8_whitelist"] = whitelist
        _models["agent8_config"] = config
        rep = _load_json(MODEL_DIR / "brand_guard_report.json")
        _accuracy["agent8"] = {"metric": "Precision", "value": rep.get("precision", rep.get("Precision", "N/A"))}
        logger.info("[STARTUP] Agent 8 — Brand Guard v1 (Edit-Distance) loaded ✓")
    else:
        logger.warning("[STARTUP] Agent 8 — Brand Guard v1 FAILED, skipping")
        _accuracy["agent8"] = {"metric": "Precision", "value": "N/A"}

def _load_agent9_brand_v2():
    _models["agent9_available"] = False
    _accuracy["agent9"] = {"metric": "AUC", "value": "N/A (PyTorch model — not loaded)"}
    logger.info("[STARTUP] Agent 9 — Brand Guard v2 (Siamese BiLSTM) skipped (requires PyTorch)")

def _load_agent10_deepfake():
    _models["agent10_available"] = False
    _accuracy["agent10"] = {"metric": "AUC", "value": "N/A (PyTorch model — not loaded)"}
    logger.info("[STARTUP] Agent 10 — Deepfake/DeiT skipped (requires PyTorch)")

def _load_agent11_malware():
    clf = _load_pickle(MODEL_DIR / "malware_rf.pkl")
    sc = _load_pickle(MODEL_DIR / "malware_scaler.pkl")
    indices = _load_pickle(MODEL_DIR / "malware_feature_indices.pkl")
    if clf is not None:
        _models["agent11_classifier"] = clf
        _models["agent11_scaler"] = sc
        _models["agent11_feature_indices"] = indices
        _accuracy["agent11"] = {"metric": "AUC", "value": "N/A (report file is .md)"}
        logger.info("[STARTUP] Agent 11 — Malware File Analyzer (Random Forest) loaded ✓")
    else:
        logger.warning("[STARTUP] Agent 11 — Malware File Analyzer FAILED, skipping")
        _accuracy["agent11"] = {"metric": "AUC", "value": "N/A"}

def _load_agent12_whisper():
    _models["agent12_available"] = False
    _accuracy["agent12"] = {"metric": "WER", "value": "N/A (PyTorch model — not loaded)"}
    logger.info("[STARTUP] Agent 12 — Whisper ASR skipped (requires PyTorch)")

def _load_agent13_call_transcript():
    _models["agent13_available"] = False
    _accuracy["agent13"] = {"metric": "AUC", "value": "N/A (PyTorch model — not loaded)"}
    logger.info("[STARTUP] Agent 13 — Call Transcript Detector skipped (requires PyTorch)")

def _load_agent15_ensemble():
    weights = _load_json(MODEL_DIR / "ensemble_weights.json")
    overrides = _load_json(MODEL_DIR / "ensemble_overrides.json")
    _models["agent15_weights"] = weights if weights else {}
    _models["agent15_overrides"] = overrides if overrides else {}
    _accuracy["agent15"] = {"metric": "Type", "value": "Calibrated weight tables + hard overrides"}
    logger.info("[STARTUP] Agent 15 — Ensemble Scorer & Overrides loaded ✓")

def load_all():
    _load_agent14_regex()
    _load_agent1_text()
    _load_agent2_distilbert()
    _load_agent3_url()
    _load_agent4_blacklist()
    _load_agent5_qr()
    _load_agent6_upi_heuristic()
    _load_agent7_upi_xgb()
    _load_agent8_brand_v1()
    _load_agent9_brand_v2()
    _load_agent10_deepfake()
    _load_agent11_malware()
    _load_agent12_whisper()
    _load_agent13_call_transcript()
    _load_agent15_ensemble()
    logger.info("Model loading complete — %d/%d agents loaded", 
                sum(1 for k in _models if not k.endswith("_available")), 15)
    return _models

def get_models() -> dict:
    return _models

def get_accuracy() -> dict:
    return _accuracy

def get_models_loaded_count() -> int:
    count = 0
    for k in _models:
        if k in ("agent1_vectorizer", "agent1_classifier", "agent1_label_encoder"):
            count = count + 1 if k == "agent1_classifier" else count
    if "agent1_classifier" in _models:
        count += 1
    if "agent3_classifier" in _models:
        count += 1
    if "agent4_blacklist" in _models:
        count += 1
    if "agent5_classifier" in _models:
        count += 1
    if "agent6_upi_engine" in _models:
        count += 1
    if "agent11_classifier" in _models:
        count += 1
    if "agent14_regex_rules" in _models:
        count += 1
    if "agent15_weights" in _models:
        count += 1
    return count
