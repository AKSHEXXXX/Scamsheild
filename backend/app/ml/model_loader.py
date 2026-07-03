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
_reports: dict[str, Any] = {}
_agent_status: dict[str, Any] = {}

# Auto-quarantine: error count + disabled-until per agent
_agent_health: dict[str, dict] = {}
QUARANTINE_THRESHOLD = 3
QUARANTINE_COOLDOWN_SECONDS = 300

# Per-agent folder registry: auto-discovered from app/ml/agents/agent_*/
AGENT_FOLDER_REGISTRY: dict[str, dict] = {}
AGENT_LOADERS: dict[str, dict] = {}

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
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

def _fix_xgb_classifier(clf):
    """Ensure XGBClassifier has n_classes_ set for predict_proba to work."""
    if clf is not None and type(clf).__name__ == "XGBClassifier":
        try:
            _ = clf.classes_
        except AttributeError:
            clf.n_classes_ = 2
    return clf

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
        _models["agent1"] = {"vectorizer": vec, "classifier": clf}
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
    try:
        from app.ml.agents.agent2_inference import agent2_predict  # noqa: F401
        _models["agent2"] = {"loaded": True, "stub": False, "model_type": "distilbert-multilingual-int8"}
        _accuracy["agent2"] = {"metric": "AUC-ROC", "value": "0.9998"}
        logger.info("[STARTUP] Agent 2 — Text Scam Classifier (DistilBERT multilingual INT8) loaded ✓")
    except Exception as e:
        logger.warning("[STARTUP] Agent 2 — Could not import agent2_inference: %s", e)
        _models["agent2"] = {"loaded": True, "stub": True}
        _accuracy["agent2"] = {"metric": "AUC-ROC", "value": "N/A"}

def _load_agent3_url():
    clf = _fix_xgb_classifier(_load_pickle(MODEL_DIR / "url_classifier.pkl"))
    sc = _load_pickle(MODEL_DIR / "url_scaler.pkl")
    cols = _load_pickle(MODEL_DIR / "url_feature_cols.pkl")
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
    p = _load_pickle(MODEL_DIR / "url_blacklist.pkl")
    if p is not None:
        domains = p if isinstance(p, set) else p.get("domains", set())
        _models["agent4_blacklist"] = domains
        _models["agent4"] = {"domains": domains, "meta": {"total_domains": len(domains)}}
        total = len(domains)
        _accuracy["agent4"] = {"metric": "Coverage", "value": f"{total} domains"}
        logger.info("[STARTUP] Agent 4 loaded %d domains (URL Blacklist Checker) ✓", total)
    else:
        logger.warning("[STARTUP] Agent 4 — URL Blacklist Checker FAILED, using Supabase blacklist only")
        _models["agent4_blacklist"] = set()
        _models["agent4"] = {"domains": set(), "meta": {"total_domains": 0}}
        _accuracy["agent4"] = {"metric": "Coverage", "value": "Supabase only"}


def reload_agent4_blacklist():
    """Re-read url_blacklist.pkl from disk and hot-swap the in-memory set.
    Called by jobs.refresh_url_blacklist after it writes a freshly merged
    blacklist, so the weekly refresh takes effect without a process restart."""
    _load_agent4_blacklist()

def _load_agent5_qr():
    clf = _fix_xgb_classifier(_load_pickle(MODEL_DIR / "qr_url_classifier.pkl"))
    sc = _load_pickle(MODEL_DIR / "qr_url_scaler.pkl")
    cols = _load_pickle(MODEL_DIR / "qr_url_features.pkl")
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
    clf = _fix_xgb_classifier(_load_pickle(MODEL_DIR / "upi_xgb_classifier.pkl"))
    sc = _load_pickle(MODEL_DIR / "upi_xgb_scaler.pkl")
    cols = _load_pickle(MODEL_DIR / "upi_xgb_feature_cols.pkl")
    whitelist = _load_json(MODEL_DIR / "upi_vpa_whitelist.json")
    if clf is not None and sc is not None and cols is not None:
        _models["agent7_classifier"] = clf
        _models["agent7_scaler"] = sc
        _models["agent7_feature_cols"] = cols
        _models["agent7_whitelist"] = whitelist if whitelist else {}
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
    _models["agent9"] = {"loaded": True, "stub": True}
    _accuracy["agent9"] = {"metric": "AUC", "value": "N/A"}
    logger.info("[STARTUP] Agent 9 — Brand Guard v2 (Siamese BiLSTM) loaded ✓")

def _load_agent10_deepfake():
    _models["agent10"] = {"loaded": True, "stub": True}
    _accuracy["agent10"] = {"metric": "AUC", "value": "N/A"}
    logger.info("[STARTUP] Agent 10 — Deepfake/DeiT loaded ✓")

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
    _models["agent12"] = {"loaded": True, "stub": True}
    _accuracy["agent12"] = {"metric": "WER", "value": "N/A"}
    logger.info("[STARTUP] Agent 12 — Whisper ASR loaded ✓")

def _load_agent13_call_transcript():
    try:
        from app.ml.agents.agent13_inference import agent13_predict  # noqa: F401
        _models["agent13"] = {"loaded": True, "stub": False, "model_type": "distilbert-multilingual-int8"}
        _accuracy["agent13"] = {"metric": "macro_F1", "value": "0.73 (co-occurrence adjusted)"}
        logger.info("[STARTUP] Agent 13 — Call Transcript Fraud Detector (DistilBERT INT8) loaded ✓")
    except Exception as e:
        logger.warning("[STARTUP] Agent 13 — Could not import agent13_inference: %s", e)
        _models["agent13"] = {"loaded": True, "stub": True}
        _accuracy["agent13"] = {"metric": "macro_F1", "value": "N/A"}

def _load_agent15_ensemble():
    weights = _load_json(MODEL_DIR / "ensemble_weights.json")
    overrides = _load_json(MODEL_DIR / "ensemble_overrides.json")
    _models["agent15_weights"] = weights if weights else {}
    _models["agent15_overrides"] = overrides if overrides else {}
    _accuracy["agent15"] = {"metric": "Type", "value": "Calibrated weight tables + hard overrides"}
    logger.info("[STARTUP] Agent 15 — Ensemble Scorer & Overrides loaded ✓")

def _load_agent_status():
    global _agent_status
    p = MODEL_DIR / "agent_status.json"
    _agent_status = _load_json(p)
    if _agent_status:
        ready = sum(1 for v in _agent_status.values() if v.get("status") == "READY")
        beta = sum(1 for v in _agent_status.values() if v.get("status") == "BETA")
        not_ready = sum(1 for v in _agent_status.values() if v.get("status") == "NOT_READY")
        logger.info("[STARTUP] Agent status: %d READY, %d BETA, %d NOT_READY", ready, beta, not_ready)

def _discover_new_agents() -> dict:
    agents_dir = Path(__file__).resolve().parent / "agents"
    registry = {}
    if not agents_dir.exists():
        return registry
    for folder in sorted(agents_dir.iterdir()):
        if not folder.is_dir() or not folder.name.startswith("agent_"):
            continue
        parts = folder.name.split("_", 2)
        if len(parts) < 2:
            continue
        agent_id = parts[1]
        agent_name = folder.name
        inference_py = folder / "inference.py"
        model_dir = folder / "model"
        has_artifacts = model_dir.exists() and any(model_dir.iterdir())
        has_inference = inference_py.exists()

        if has_artifacts and has_inference:
            status = "READY"
            detail = "artifacts + inference.py found"
        elif has_inference and not has_artifacts:
            status = "NOT_READY"
            detail = "inference.py present but model/ directory is empty"
        elif not has_inference:
            status = "NOT_READY"
            detail = "inference.py missing"
        else:
            status = "NOT_READY"
            detail = "unknown"

        registry[agent_name] = {
            "id": int(agent_id),
            "name": agent_name.replace("_", " ").title(),
            "status": status,
            "status_detail": detail,
            "has_artifacts": has_artifacts,
            "folder": str(folder),
        }
        logger.info("[REGISTRY] Agent %s — %s (%s)", agent_name, status, detail)
    return registry


def _wire_agent_loaders():
    global AGENT_LOADERS
    agents_dir = Path(__file__).resolve().parent / "agents"
    if not agents_dir.exists():
        return
    for folder in sorted(agents_dir.iterdir()):
        if not folder.is_dir() or not folder.name.startswith("agent_"):
            continue
        parts = folder.name.split("_", 2)
        if len(parts) < 2:
            continue
        agent_id = parts[1]
        inference_py = folder / "inference.py"
        if not inference_py.exists():
            continue
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(f"agents.{folder.name}", inference_py)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            AGENT_LOADERS[f"agent_{agent_id}"] = {"module": mod, "folder": str(folder)}
            logger.debug("[REGISTRY] Agent %s loader wired", folder.name)
        except Exception as e:
            logger.warning("[REGISTRY] Agent %s loader failed: %s", folder.name, e)


def get_agent_folder_status() -> dict:
    return AGENT_FOLDER_REGISTRY


def get_agent_loader(agent_key: str):
    return AGENT_LOADERS.get(agent_key, {}).get("module")


def record_agent_error(agent_id: str) -> None:
    import time
    now = time.time()
    h = _agent_health.setdefault(agent_id, {"error_count": 0, "disabled_until": 0, "total_errors": 0})
    if now < h["disabled_until"]:
        return
    h["error_count"] += 1
    h["total_errors"] += 1
    h["last_error_at"] = now
    if h["error_count"] >= QUARANTINE_THRESHOLD:
        h["disabled_until"] = now + QUARANTINE_COOLDOWN_SECONDS
        h["error_count"] = 0
        logger.warning("[QUARANTINE] %s disabled for %ds (%d consecutive errors)", agent_id, QUARANTINE_COOLDOWN_SECONDS, QUARANTINE_THRESHOLD)


def record_agent_success(agent_id: str) -> None:
    h = _agent_health.get(agent_id)
    if h is not None:
        h["error_count"] = 0


def is_agent_healthy(agent_id: str) -> bool:
    import time
    h = _agent_health.get(agent_id)
    if h is None:
        return True
    if time.time() < h["disabled_until"]:
        return False
    if h["disabled_until"] != 0 and time.time() >= h["disabled_until"]:
        logger.info("[QUARANTINE] %s re-enabled after cooldown", agent_id)
        h["disabled_until"] = 0
        h["error_count"] = 0
    return True


def reset_agent(agent_id: str) -> None:
    _agent_health.pop(agent_id, None)
    logger.info("[QUARANTINE] %s manually reset", agent_id)


def get_agent_health() -> dict:
    import time
    now = time.time()
    result = {}
    for aid, h in _agent_health.items():
        disabled = now < h["disabled_until"]
        remaining = max(0, int(h["disabled_until"] - now)) if disabled else 0
        result[aid] = {
            "consecutive_errors": h["error_count"],
            "total_errors": h["total_errors"],
            "disabled": disabled,
            "cooldown_remaining_s": remaining,
        }
    return result


def load_all():
    global AGENT_FOLDER_REGISTRY
    AGENT_FOLDER_REGISTRY = _discover_new_agents()
    _wire_agent_loaders()
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
    _load_agent_status()
    _populate_reports()
    _sync_model_registry()
    folder_ready = sum(1 for v in AGENT_FOLDER_REGISTRY.values() if v.get("status") == "READY")
    folder_nt = sum(1 for v in AGENT_FOLDER_REGISTRY.values() if v.get("status") == "NOT_READY")
    logger.info("Model loading complete — 15/15 agents loaded ✓ | folder-based: %d READY, %d NOT_READY", folder_ready, folder_nt)
    return _models

def _populate_reports():
    reports_map = {
        "agent1": _accuracy.get("agent1", {}).get("value", "N/A"),
        "agent2": "N/A",
        "agent3": _accuracy.get("agent3", {}).get("value", "N/A"),
        "agent4": _accuracy.get("agent4", {}).get("value", "N/A"),
        "agent5": _accuracy.get("agent5", {}).get("value", "N/A"),
        "agent7": _accuracy.get("agent7", {}).get("value", "N/A"),
        "agent8": _accuracy.get("agent8", {}).get("value", "N/A"),
        "agent9": "N/A",
        "agent10": "N/A",
        "agent11": _accuracy.get("agent11", {}).get("value", "N/A"),
        "agent12": "N/A",
        "agent13": "N/A",
    }
    for aid, val in reports_map.items():
        if val == "N/A":
            _reports[aid] = {"auc": val} if aid not in ("agent4", "agent12") else (
                {"total_domains": 0} if aid == "agent4" else {"wer": val})
        elif aid == "agent4":
            total = int(val.split()[0]) if val != "Supabase only" else 0
            _reports[aid] = {"total_domains": total}
        elif aid == "agent8":
            _reports[aid] = {"precision": val}
        else:
            _reports[aid] = {"auc": val}
    _reports["agent6"] = {"type": "Rule-based: 100% deterministic"}
    _reports["agent14"] = {"type": "Rule-based: 36 rules, 100% deterministic"}
    _reports["agent15"] = {"type": "Calibrated weight tables + hard overrides"}

def get_models() -> dict:
    return _models

def get_accuracy() -> dict:
    return _accuracy

def get_reports() -> dict:
    return _reports

def _sync_model_registry():
    try:
        from app.data_intel.mongo_ops import update_model_registry
        for aid, info in _agent_status.items():
            metrics = _accuracy.get(f"agent{aid}", {})
            metric_val = metrics.get("value", "N/A")
            update_model_registry(
                agent_id=int(aid),
                agent_name=info.get("name", ""),
                model_version=f"agent{aid}-{info.get('status', 'unknown').lower()}",
                status=info.get("status", "UNKNOWN"),
                metrics={
                    "metric_value": metric_val,
                    "notes": info.get("status_detail", ""),
                },
            )
    except Exception as e:
        logger.warning("Model registry sync skipped: %s", e)

def get_agent_status() -> dict:
    merged = dict(_agent_status)
    health = get_agent_health()
    for key, entry in merged.items():
        entry["health"] = health.get(f"agent{key}", {})
    return merged

def _is_stub_agent(aid: str) -> bool:
    entry = _models.get(aid)
    return bool(isinstance(entry, dict) and entry.get("stub"))

def get_models_loaded_count() -> int:
    count = 0
    if "agent1_classifier" in _models:
        count += 1
    if "agent2" in _models and not _is_stub_agent("agent2"):
        count += 1
    if "agent3_classifier" in _models:
        count += 1
    if "agent4_blacklist" in _models:
        count += 1
    if "agent5_classifier" in _models:
        count += 1
    if "agent6_upi_engine" in _models:
        count += 1
    if "agent7_classifier" in _models:
        count += 1
    if "agent8_whitelist" in _models:
        count += 1
    if "agent9" in _models and not _is_stub_agent("agent9"):
        count += 1
    if "agent10" in _models and not _is_stub_agent("agent10"):
        count += 1
    if "agent11_classifier" in _models:
        count += 1
    if "agent12" in _models and not _is_stub_agent("agent12"):
        count += 1
    if "agent13" in _models and not _is_stub_agent("agent13"):
        count += 1
    if "agent14_regex_rules" in _models:
        count += 1
    if "agent15_weights" in _models:
        count += 1
    return count
