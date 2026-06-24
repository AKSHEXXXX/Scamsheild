import json
import logging
from pathlib import Path

logger = logging.getLogger("scamshield.agents.ensemble")

_ARTIFACTS = Path(__file__).resolve().parent.parent / "app" / "ml" / "artifacts"

_WEIGHT_TABLES = None
_OVERRIDES = None

VERDICT_SAFE = 35
VERDICT_SUSPICIOUS = 62

def _load_artifacts():
    global _WEIGHT_TABLES, _OVERRIDES
    if _WEIGHT_TABLES is not None:
        return
    weights_path = _ARTIFACTS / "ensemble_weights.json"
    overrides_path = _ARTIFACTS / "ensemble_overrides.json"
    if weights_path.exists():
        with open(weights_path) as f:
            _WEIGHT_TABLES = json.load(f)
    else:
        logger.warning("ensemble_weights.json not found, using fallback weights")
        _WEIGHT_TABLES = {
            "text": {"text_prob": 0.65, "url_prob": 0.10, "blacklist_hit_flat": 20,
                     "brand_flag": 0.10, "upi_rule_score": 0.05, "upi_xgb_prob": 0.0,
                     "deepfake_prob": 0.0, "malware_prob": 0.0, "call_fraud_prob": 0.0, "regex_score": 0.15},
            "url":  {"text_prob": 0.10, "url_prob": 0.60, "blacklist_hit_flat": 20,
                     "brand_flag": 0.20, "upi_rule_score": 0.05, "upi_xgb_prob": 0.0,
                     "deepfake_prob": 0.0, "malware_prob": 0.0, "call_fraud_prob": 0.0, "regex_score": 0.05},
            "qr":   {"text_prob": 0.10, "url_prob": 0.35, "blacklist_hit_flat": 20,
                     "brand_flag": 0.15, "upi_rule_score": 0.15, "upi_xgb_prob": 0.0,
                     "deepfake_prob": 0.0, "malware_prob": 0.0, "call_fraud_prob": 0.0, "regex_score": 0.10},
            "upi":  {"text_prob": 0.05, "url_prob": 0.05, "blacklist_hit_flat": 0,
                     "brand_flag": 0.05, "upi_rule_score": 0.80, "upi_xgb_prob": 0.0,
                     "deepfake_prob": 0.0, "malware_prob": 0.0, "call_fraud_prob": 0.0, "regex_score": 0.10},
            "image": {"text_prob": 0.20, "url_prob": 0.05, "blacklist_hit_flat": 0,
                      "brand_flag": 0.05, "upi_rule_score": 0.05, "upi_xgb_prob": 0.0,
                      "deepfake_prob": 0.05, "malware_prob": 0.35, "call_fraud_prob": 0.0, "regex_score": 0.25},
            "file":  {"text_prob": 0.10, "url_prob": 0.05, "blacklist_hit_flat": 0,
                      "brand_flag": 0.05, "upi_rule_score": 0.05, "upi_xgb_prob": 0.0,
                      "deepfake_prob": 0.05, "malware_prob": 0.45, "call_fraud_prob": 0.0, "regex_score": 0.25},
            "audio": {"text_prob": 0.40, "url_prob": 0.05, "blacklist_hit_flat": 0,
                      "brand_flag": 0.05, "upi_rule_score": 0.05, "upi_xgb_prob": 0.0,
                      "deepfake_prob": 0.0, "malware_prob": 0.0, "call_fraud_prob": 0.40, "regex_score": 0.05},
        }
    if overrides_path.exists():
        with open(overrides_path) as f:
            _OVERRIDES = json.load(f)
    else:
        _OVERRIDES = {"hard_overrides": []}

def _get_weights():
    _load_artifacts()
    return _WEIGHT_TABLES

def _get_overrides():
    _load_artifacts()
    return _OVERRIDES

def _check_triggered(triggered: list, prefix: str) -> bool:
    return any(t.startswith(prefix) for t in triggered) if triggered else False


def compute(signals: dict, scan_type: str = "text") -> dict:
    weights = _get_weights().get(scan_type, _get_weights()["text"])
    weighted = 0.0
    contributions = {}

    text_prob = signals.get("text_prob", -1)
    if text_prob >= 0:
        weighted += text_prob * weights["text_prob"] * 100
    contributions["text_prob"] = round(text_prob, 4) if text_prob >= 0 else None

    url_prob = signals.get("url_prob", -1)
    if url_prob >= 0:
        weighted += url_prob * weights["url_prob"] * 100
        contributions["url_prob"] = round(url_prob, 4)

    if weights["blacklist_hit_flat"] and signals.get("blacklist_hit"):
        weighted += weights["blacklist_hit_flat"]

    upi_rule = signals.get("upi_rule_score", 0)
    weighted += (upi_rule / 100.0) * weights["upi_rule_score"] * 100
    contributions["upi_rule_score"] = round(upi_rule / 100.0, 4)

    upi_xgb = signals.get("upi_xgb_prob", -1)
    if upi_xgb >= 0:
        weighted += upi_xgb * weights["upi_xgb_prob"] * 100
        contributions["upi_xgb_prob"] = round(upi_xgb, 4)

    deepfake = signals.get("deepfake_prob", -1)
    if deepfake >= 0:
        weighted += deepfake * weights["deepfake_prob"] * 100
        contributions["deepfake_prob"] = round(deepfake, 4)

    malware = signals.get("malware_prob", -1)
    if malware >= 0:
        weighted += malware * weights["malware_prob"] * 100
        contributions["malware_prob"] = round(malware, 4)

    call_fraud = signals.get("call_fraud_prob", -1)
    if call_fraud >= 0:
        weighted += call_fraud * weights["call_fraud_prob"] * 100
        contributions["call_fraud_prob"] = round(call_fraud, 4)

    regex_score = signals.get("regex_score", 0)
    weighted += (regex_score / 100.0) * weights["regex_score"] * 100
    contributions["regex_score"] = round(regex_score / 100.0, 4)

    url_risk_boost = signals.get("url_risk_boost", 0)
    if url_risk_boost:
        weighted += url_risk_boost
        contributions["url_risk_boost"] = url_risk_boost

    score = int(round(weighted))

    multi_signal_boost = 0
    signals_fired = 0
    if text_prob >= 0:
        signals_fired += 1
    if url_prob >= 0 and url_prob > 0.3:
        signals_fired += 1
    if signals.get("blacklist_hit"):
        signals_fired += 1
    if signals.get("brand_flag"):
        signals_fired += 1
    if regex_score > 50:
        signals_fired += 1
    if signals.get("deepfake_prob", -1) >= 0 and deepfake and deepfake > 0.5:
        signals_fired += 1
    if upi_rule >= 70:
        signals_fired += 1
    if upi_xgb >= 0 and upi_xgb > 0.5:
        signals_fired += 1
    if signals_fired >= 3:
        multi_signal_boost = 15
    elif signals_fired >= 2:
        multi_signal_boost = 8
    score += multi_signal_boost

    triggered = signals.get("regex_triggered", [])

    # Safety override: if ALL triggered rules are NONE severity, cap at low_risk
    regex_safe = signals.get("regex_safe", False)
    if regex_safe and score > VERDICT_SAFE:
        has_other_signal = any([signals.get("blacklist_hit"), signals.get("brand_flag"),
                                signals.get("upi_rule_score", 0) >= 70,
                                malware is not None and malware > 0.5,
                                deepfake is not None and deepfake > 0.5])
        if not has_other_signal:
            score = VERDICT_SAFE

    for override in _get_overrides().get("hard_overrides", []):
        cond = override.get("condition", "")
        min_scr = override.get("min_score", 0)
        boost = override.get("boost", 0)
        matched = False
        if cond == "blacklist_hit" and signals.get("blacklist_hit"):
            matched = True
        elif cond == "upi_rule_gte_70" and upi_rule >= 70:
            matched = True
        elif cond == "brand_flag" and signals.get("brand_flag"):
            matched = True
        elif cond == "deepfake_prob_gt_0.85" and deepfake and deepfake > 0.85:
            matched = True
        elif cond == "malware_prob_gt_0.7" and malware and malware > 0.7:
            matched = True
        elif cond == "regex_high" and signals.get("regex_high"):
            matched = True
        elif cond == "digital_arrest_rule" and _check_triggered(triggered, "DIGITAL_ARREST"):
            matched = True
        elif cond == "upi_double_money_rule" and _check_triggered(triggered, "UPI_DOUBLE_MONEY"):
            matched = True
        elif cond == "fake_job_rule" and _check_triggered(triggered, "FAKE_JOB"):
            matched = True
        if matched:
            score = max(score, min_scr)
            score = score + boost

    score = min(100, max(0, score))

    if score <= VERDICT_SAFE:
        verdict = "low_risk"
    elif score <= VERDICT_SUSPICIOUS:
        verdict = "suspicious"
    else:
        verdict = "high_risk"

    top_signal = max((k for k, v in contributions.items() if v is not None), key=lambda k: contributions[k] or 0) if any(v is not None for v in contributions.values()) else "none"
    confidence = round(score / 100.0, 2)

    return {
        "scam_score": score,
        "verdict": verdict,
        "signals": contributions,
        "top_signal": top_signal,
        "confidence": confidence,
    }

def compute_ensemble_verdict(ml_text_prob=-1.0, ml_url_prob=-1.0, ml_qr_prob=-1.0,
                              rule_score=0, has_blacklisted_domain=False,
                              has_blacklisted_vpa=False, has_blacklisted_phone=False,
                              impersonation_boost=0, scan_type="text",
                              deepfake_prob=-1.0, malware_prob=-1.0,
                              call_fraud_prob=-1.0, brand_flag=False,
                              upi_rule_score=0, upi_xgb_prob=-1.0,
                              regex_score=0, regex_high=False,
                              regex_triggered=None, regex_safe=False):
    signals = {
        "text_prob": ml_text_prob if ml_text_prob >= 0 else -1,
        "url_prob": ml_url_prob if ml_url_prob >= 0 else ml_qr_prob if ml_qr_prob >= 0 else -1,
        "blacklist_hit": has_blacklisted_domain or has_blacklisted_vpa or has_blacklisted_phone,
        "brand_flag": brand_flag,
        "upi_rule_score": upi_rule_score,
        "upi_xgb_prob": -1,  # Agent 7 disabled (AUC 0.47 — worse than random)
        "deepfake_prob": deepfake_prob,
        "malware_prob": malware_prob,
        "call_fraud_prob": call_fraud_prob,
        "regex_score": regex_score,
        "regex_high": regex_high,
        "regex_triggered": regex_triggered or [],
        "regex_safe": regex_safe,
    }
    result = compute(signals, scan_type)
    ml_debug = {
        "ml_text_prob": round(ml_text_prob, 4) if ml_text_prob >= 0 else None,
        "ml_url_prob": round(ml_url_prob, 4) if ml_url_prob >= 0 else None,
        "rule_score_norm": round(rule_score / 100.0, 2),
        "blacklist_hit": has_blacklisted_domain or has_blacklisted_vpa or has_blacklisted_phone,
    }
    return result["scam_score"], result["verdict"], ml_debug
