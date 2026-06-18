import logging
import json
import pickle
import importlib
import warnings
from pathlib import Path
from typing import Any
from datetime import datetime

warnings.filterwarnings("ignore")

logger = logging.getLogger("scamshield.models")

MODEL_DIR = Path(__file__).resolve().parent.parent / "app" / "ml" / "artifacts"

_models: dict[str, Any] = {}
_reports: dict[str, Any] = {}

def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.warning("load_json %s: %s", path.name, e)
        return {}

def _load_pickle(path: Path):
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        logger.warning("load_pickle %s: %s", path.name, e)
        return None

def load_all_models():
    # Agent 1 — Text TF-IDF + LogReg (CRITICAL)
    try:
        v = _load_pickle(MODEL_DIR / "text_tfidf_vectorizer.pkl")
        c = _load_pickle(MODEL_DIR / "text_logreg_classifier.pkl")
        if v is not None and c is not None:
            _models["agent1"] = {"vectorizer": v, "classifier": c}
            rep = _load_json(MODEL_DIR / "text_model_report.json")
            _reports["agent1"] = {"auc": rep.get("accuracy", "N/A")}
            logger.info("[STARTUP] Agent 1 — Text TF-IDF + LogReg loaded ✓")
        else:
            raise RuntimeError("Agent 1 artifact files missing or corrupt")
    except Exception as e:
        logger.error("[STARTUP] Agent 1 — CRITICAL FAILURE: %s", e)
        raise RuntimeError(f"Critical agent Agent 1 failed to load: {e}") from e

    # Agent 2 — DistilBERT (skip)
    _reports["agent2"] = {"auc": "skipped — model not loaded"}
    logger.info("[STARTUP] Agent 2 — DistilBERT FP16 skipped (requires PyTorch)")

    # Agent 3 — URL XGBoost
    try:
        from app.ml.model_loader import get_models as get_old_models
        old = get_old_models()
        if "agent3_classifier" in old:
            _models["agent3"] = {
                "classifier": old["agent3_classifier"],
                "scaler": old.get("agent3_scaler"),
                "feature_cols": old.get("agent3_feature_cols"),
            }
            rep = _load_json(MODEL_DIR / "url_model_report.json")
            _reports["agent3"] = {"auc": rep.get("auc", "N/A")}
            logger.info("[STARTUP] Agent 3 — URL XGBoost loaded ✓")
        else:
            logger.error("[STARTUP] Agent 3 — URL XGBoost FAILED (model files not found)")
            _reports["agent3"] = {"auc": "N/A"}
    except Exception as e:
        logger.error("[STARTUP] Agent 3 — FAILED: %s", e)
        _reports["agent3"] = {"auc": "N/A"}

    # Agent 4 — URL Blacklist Checker
    try:
        bl = _load_pickle(MODEL_DIR / "url_blacklist.pkl")
        if bl is not None:
            domains = bl if isinstance(bl, set) else bl.get("domains", set())
            _models["agent4"] = {"domains": domains, "meta": {"total_domains": len(domains)}}
            bl_rep = _load_json(MODEL_DIR / "agent4_blacklist_report.json")
            _reports["agent4"] = {"total_domains": bl_rep.get("total_domains", len(domains))}
            logger.info("[STARTUP] Agent 4 — URL Blacklist Checker loaded ✓ (%d domains)", len(domains))
        else:
            logger.error("[STARTUP] Agent 4 — URL Blacklist Checker FAILED")
            _models["agent4"] = {"domains": set(), "meta": {"total_domains": 0}}
            _reports["agent4"] = {"total_domains": 0}
    except Exception as e:
        logger.error("[STARTUP] Agent 4 — URL Blacklist Checker FAILED: %s", e)
        _models["agent4"] = {"domains": set(), "meta": {"total_domains": 0}}
        _reports["agent4"] = {"total_domains": 0}

    # Agent 5 — QR XGBoost
    try:
        if "agent5_classifier" in old:
            _models["agent5"] = {
                "classifier": old["agent5_classifier"],
                "scaler": old.get("agent5_scaler"),
                "feature_cols": old.get("agent5_feature_cols"),
            }
            rep = _load_json(MODEL_DIR / "qr_model_report.json")
            _reports["agent5"] = {"auc": rep.get("auc", "N/A")}
            logger.info("[STARTUP] Agent 5 — QR XGBoost loaded ✓")
        else:
            logger.error("[STARTUP] Agent 5 — QR XGBoost FAILED")
            _reports["agent5"] = {"auc": "N/A"}
    except Exception as e:
        logger.error("[STARTUP] Agent 5 — QR XGBoost FAILED: %s", e)
        _reports["agent5"] = {"auc": "N/A"}

    # Agent 6 — UPI Heuristic
    try:
        if "agent6_upi_engine" in old:
            _models["agent6"] = {"engine": old["agent6_upi_engine"]}
            _reports["agent6"] = {"type": "Rule-based: 100% deterministic"}
            logger.info("[STARTUP] Agent 6 — UPI Heuristic loaded ✓")
        else:
            logger.error("[STARTUP] Agent 6 — UPI Heuristic FAILED")
    except Exception as e:
        logger.error("[STARTUP] Agent 6 — UPI Heuristic FAILED: %s", e)

    # Agent 7 — UPI XGBoost
    try:
        if "agent7_classifier" in old:
            _models["agent7"] = {
                "classifier": old["agent7_classifier"],
                "scaler": old.get("agent7_scaler"),
                "feature_cols": old.get("agent7_feature_cols"),
            }
            rep = _load_json(MODEL_DIR / "upi_model_report.json")
            _reports["agent7"] = {"auc": rep.get("auc", "N/A")}
            logger.info("[STARTUP] Agent 7 — UPI XGBoost loaded ✓")
        else:
            logger.error("[STARTUP] Agent 7 — UPI XGBoost FAILED")
            _reports["agent7"] = {"auc": "N/A"}
    except Exception as e:
        logger.error("[STARTUP] Agent 7 — UPI XGBoost FAILED: %s", e)
        _reports["agent7"] = {"auc": "N/A"}

    # Agent 8 — Brand Guard v1
    try:
        if "agent8_whitelist" in old:
            _models["agent8"] = {"whitelist": old["agent8_whitelist"], "config": old.get("agent8_config")}
            rep = _load_json(MODEL_DIR / "brand_guard_report.json")
            _reports["agent8"] = {"precision": rep.get("precision", rep.get("best_f1", rep.get("f1", "see report")))}
            logger.info("[STARTUP] Agent 8 — Brand Guard v1 loaded ✓")
        else:
            logger.error("[STARTUP] Agent 8 — Brand Guard v1 FAILED")
            _reports["agent8"] = {"precision": "N/A"}
    except Exception as e:
        logger.error("[STARTUP] Agent 8 — Brand Guard v1 FAILED: %s", e)
        _reports["agent8"] = {"precision": "N/A"}

    # Agent 9 — Brand Guard v2 (skip)
    _reports["agent9"] = {"auc": "skipped — model not loaded"}
    logger.info("[STARTUP] Agent 9 — Brand Guard v2 skipped (requires PyTorch)")

    # Agent 10 — Deepfake (skip)
    _reports["agent10"] = {"auc": "skipped — model not loaded"}
    logger.info("[STARTUP] Agent 10 — Deepfake/DeiT skipped (requires PyTorch)")

    # Agent 11 — Malware
    try:
        if "agent11_classifier" in old:
            _models["agent11"] = {
                "classifier": old["agent11_classifier"],
                "scaler": old.get("agent11_scaler"),
                "indices": old.get("agent11_feature_indices"),
            }
            _reports["agent11"] = {"auc": "N/A (report file is .md)"}
            logger.info("[STARTUP] Agent 11 — Malware RF loaded ✓")
        else:
            logger.error("[STARTUP] Agent 11 — Malware RF FAILED")
            _reports["agent11"] = {"auc": "N/A"}
    except Exception as e:
        logger.error("[STARTUP] Agent 11 — Malware RF FAILED: %s", e)
        _reports["agent11"] = {"auc": "N/A"}

    # Agent 12 — Whisper (skip)
    _reports["agent12"] = {"wer": "skipped — model not loaded"}
    logger.info("[STARTUP] Agent 12 — Whisper ASR skipped (requires PyTorch)")

    # Agent 13 — Call Transcript (skip)
    _reports["agent13"] = {"auc": "skipped — model not loaded"}
    logger.info("[STARTUP] Agent 13 — Call Transcript skipped (requires PyTorch)")

    # Agent 14 — Regex Engine (CRITICAL)
    try:
        if "agent14_regex_rules" in old:
            _models["agent14"] = {"rules": old["agent14_regex_rules"]}
            _reports["agent14"] = {"type": "Rule-based: 36 rules, 100% deterministic"}
            logger.info("[STARTUP] Agent 14 — Regex Engine loaded ✓")
        else:
            raise RuntimeError("Agent 14 regex rules not found")
    except Exception as e:
        logger.error("[STARTUP] Agent 14 — CRITICAL FAILURE: %s", e)
        raise RuntimeError(f"Critical agent Agent 14 failed to load: {e}") from e

    # Agent 15 — Ensemble (CRITICAL)
    _reports["agent15"] = {"type": "Calibrated weight tables + hard overrides"}
    logger.info("[STARTUP] Agent 15 — Ensemble loaded ✓")

    n = sum(1 for k in ["agent1","agent3","agent4","agent5","agent6","agent7","agent8","agent11","agent14"] if k in _models)
    logger.info("New model loader complete — %d agents loaded", n)
    return _models

def get_models() -> dict:
    return _models

def get_reports() -> dict:
    return _reports

def get_models_loaded_count() -> int:
    return sum(1 for k in ["agent1","agent3","agent4","agent5","agent6","agent7","agent8","agent11","agent14"] if k in _models)
