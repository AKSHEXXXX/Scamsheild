import logging
import warnings

logger = logging.getLogger("scamshield.ml.ensemble")
warnings.warn(
    "app.ml.ensemble is DEPRECATED. All callers must use agents.agent15_ensemble instead.",
    DeprecationWarning,
    stacklevel=2,
)

WEIGHT_TABLES = {
    "text": {"text_prob": 0.50, "url_prob": 0.10, "blacklist_hit_flat": 20,
             "brand_flag": 0.10, "upi_rule_score": 0.05, "upi_xgb_prob": 0.0,
             "deepfake_prob": 0.0, "malware_prob": 0.0, "call_fraud_prob": 0.0, "regex_score": 0.15},
    "url":  {"text_prob": 0.10, "url_prob": 0.55, "blacklist_hit_flat": 20,
             "brand_flag": 0.20, "upi_rule_score": 0.05, "upi_xgb_prob": 0.0,
             "deepfake_prob": 0.0, "malware_prob": 0.0, "call_fraud_prob": 0.0, "regex_score": 0.05},
    "qr":   {"text_prob": 0.10, "url_prob": 0.30, "blacklist_hit_flat": 20,
             "brand_flag": 0.15, "upi_rule_score": 0.10, "upi_xgb_prob": 0.05,
             "deepfake_prob": 0.0, "malware_prob": 0.0, "call_fraud_prob": 0.0, "regex_score": 0.10},
    "upi":  {"text_prob": 0.05, "url_prob": 0.05, "blacklist_hit_flat": 0,
             "brand_flag": 0.05, "upi_rule_score": 0.50, "upi_xgb_prob": 0.30,
             "deepfake_prob": 0.0, "malware_prob": 0.0, "call_fraud_prob": 0.0, "regex_score": 0.05},
    "image": {"text_prob": 0.10, "url_prob": 0.05, "blacklist_hit_flat": 0,
              "brand_flag": 0.05, "upi_rule_score": 0.05, "upi_xgb_prob": 0.0,
              "deepfake_prob": 0.60, "malware_prob": 0.15, "call_fraud_prob": 0.0, "regex_score": 0.05},
    "audio": {"text_prob": 0.40, "url_prob": 0.05, "blacklist_hit_flat": 0,
              "brand_flag": 0.05, "upi_rule_score": 0.05, "upi_xgb_prob": 0.0,
              "deepfake_prob": 0.0, "malware_prob": 0.0, "call_fraud_prob": 0.40, "regex_score": 0.05},
}

VERDICT_SAFE = 39
VERDICT_SUSPICIOUS = 69
VERDICT_SCAM = 70

def compute(signals: dict, scan_type: str = "text") -> dict:
    weights = WEIGHT_TABLES.get(scan_type, WEIGHT_TABLES["text"])
    weighted = 0.0
    contributions = {}

    text_prob = signals.get("text_prob", -1)
    if text_prob >= 0:
        weighted += text_prob * weights["text_prob"] * 100
    if text_prob >= 0:
        contributions["text_prob"] = round(text_prob, 4)

    url_prob = signals.get("url_prob", -1)
    if url_prob >= 0:
        weighted += url_prob * weights["url_prob"] * 100
    if url_prob >= 0:
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

    if signals.get("blacklist_hit"):
        score = max(score, 80)
    if upi_rule >= 70:
        score = max(score, 65)
    if signals.get("brand_flag"):
        score = max(score, 60)
    if deepfake and deepfake > 0.85:
        score = max(score, 70)
    if signals.get("regex_high"):
        score = max(score, 60)

    score = min(100, max(0, score))

    if score <= VERDICT_SAFE:
        verdict = "low_risk"
    elif score <= VERDICT_SUSPICIOUS:
        verdict = "suspicious"
    else:
        verdict = "high_risk"

    top_signal = max(contributions, key=contributions.get) if contributions else "none"
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
