import json
import logging
from pathlib import Path

logger = logging.getLogger("scamshield.agents.ensemble")

_ARTIFACTS = Path(__file__).resolve().parent.parent / "app" / "ml" / "artifacts"

with open(_ARTIFACTS / "ensemble_weights.json") as f:
    WEIGHT_TABLES = json.load(f)

with open(_ARTIFACTS / "ensemble_overrides.json") as f:
    _overrides = json.load(f)

VERDICT_SAFE = _overrides.get("VERDICT_SAFE", 39)
VERDICT_SUSPICIOUS = _overrides.get("VERDICT_SUSPICIOUS", 69)
HARD_OVERRIDES = _overrides.get("hard_overrides", [])

def compute(signals: dict, scan_type: str = "text") -> dict:
    weights = WEIGHT_TABLES.get(scan_type, WEIGHT_TABLES["text"])
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

    score = int(round(weighted))

    for override in HARD_OVERRIDES:
        cond = override.get("condition", "")
        min_scr = override.get("min_score", 0)
        if cond == "blacklist_hit" and signals.get("blacklist_hit"):
            score = max(score, min_scr)
        elif cond == "upi_rule_gte_70" and upi_rule >= 70:
            score = max(score, min_scr)
        elif cond == "brand_flag" and signals.get("brand_flag"):
            score = max(score, min_scr)
        elif cond == "deepfake_prob_gt_0.85" and deepfake and deepfake > 0.85:
            score = max(score, min_scr)
        elif cond == "regex_high" and signals.get("regex_high"):
            score = max(score, min_scr)

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
                              regex_score=0, regex_high=False):
    signals = {
        "text_prob": ml_text_prob if ml_text_prob >= 0 else -1,
        "url_prob": ml_url_prob if ml_url_prob >= 0 else ml_qr_prob if ml_qr_prob >= 0 else -1,
        "blacklist_hit": has_blacklisted_domain or has_blacklisted_vpa or has_blacklisted_phone,
        "brand_flag": brand_flag,
        "upi_rule_score": upi_rule_score,
        "upi_xgb_prob": upi_xgb_prob,
        "deepfake_prob": deepfake_prob,
        "malware_prob": malware_prob,
        "call_fraud_prob": call_fraud_prob,
        "regex_score": regex_score,
        "regex_high": regex_high,
    }
    result = compute(signals, scan_type)
    ml_debug = {
        "ml_text_prob": round(ml_text_prob, 4) if ml_text_prob >= 0 else None,
        "ml_url_prob": round(ml_url_prob, 4) if ml_url_prob >= 0 else None,
        "rule_score_norm": round(rule_score / 100.0, 2),
        "blacklist_hit": has_blacklisted_domain or has_blacklisted_vpa or has_blacklisted_phone,
    }
    return result["scam_score"], result["verdict"], ml_debug
