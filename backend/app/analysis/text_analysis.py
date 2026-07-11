"""
Shared text analysis logic used by both /api/v1/analyze-text and /api/v1/scan endpoints.
Eliminates code duplication between routers/text.py and routers/scan.py.
"""
import re
import time
import logging
from typing import Optional

from app.ml.model_loader import get_models
from app.ml.agents.inference import (
    agent1_predict_text,
    agent2_predict_text,
    agent14_score_text,
    agent1_predict_text as _a1_predict,
)
from app.ml.url_features import extract_url_signals, compute_url_risk_boost
from agents.agent15_ensemble import compute as ensemble_compute
from app.preprocessing.multilingual import detect_language, extract_multilingual_keywords
from app.preprocessing.text_normalizer import normalize as normalize_text

logger = logging.getLogger("scamshield.text_analysis")

# URL extraction regex (shared)
URL_RE = re.compile(r"https?://[^\s\)\"\'\>\<\]]+")


async def analyze_text_message(
    text: str,
    os_platform: str,
    user_id: str,
    request_id: str = "",
    endpoint: str = "/api/v1/analyze-text",
    x_device_id: Optional[str] = None,
) -> dict:
    """
    Analyze a text/SMS message for scam signals.
    
    Returns the complete analysis result including verdict, score, and per-agent signals.
    """
    t0 = time.time()
    
    # Normalize text (handles leetspeak, Unicode, multilingual)
    text = normalize_text(text)
    
    # Gate empty/very-short text — no ML needed
    stripped = text.strip()
    has_content = any(c.isalnum() for c in stripped)
    if not stripped or not has_content or (len(stripped) < 4 and not any(k in stripped for k in ("@", "http", "www"))):
        return {
            "scam_score": 0,
            "verdict": "low_risk",
            "verdict_label": "Low Risk",
            "top_signal": "empty_or_very_short_input",
            "confidence": 1.0,
            "flagged_urls": [],
            "findings": [],
            "warning_count": 0,
            "extracted_text": text,
            "kind": "message",
            "flagged": False,
            "signals": {},
            "meta": {"agents_used": [], "agent2_invoked": False},
        }

    # Agent 14: Regex rule engine
    regex_result = agent14_score_text(text)
    regex_score = regex_result["score"]
    regex_severity = regex_result["severity"]
    regex_triggered = regex_result["triggered"]
    regex_high = regex_severity == "HIGH"
    regex_safe = regex_result.get("regex_safe", False)

    # Agent 1: TF-IDF + LogReg
    models = get_models()
    text_tfidf_prob = None
    raw_a1 = agent1_predict_text(text)
    if raw_a1 >= 0:
        text_tfidf_prob = raw_a1

    # Agent 2: DistilBERT (extended gate 0.35-0.85)
    text_distilbert_prob = None
    agent2_invoked = False
    agent2_label = None
    
    if text_tfidf_prob is not None and 0.35 <= text_tfidf_prob <= 0.85:
        # Agent 2 is available if model is loaded
        models = get_models()
        agent2_available = models.get("agent2") is not None
        if agent2_available:
            try:
                from app.ml.agents.inference import agent2_predict_text_full
                a2_full = agent2_predict_text_full(text)
                if a2_full.get("model_loaded", False):
                    agent2_label = a2_full.get("label", "SAFE").upper()
                    a2_raw = agent2_predict_text(text)
                    if a2_raw >= 0:
                        text_distilbert_prob = a2_raw
                        agent2_invoked = True
            except Exception as e:
                logger.warning("Agent 2 predict error: %s", e)

    # Fuse Agent 1 + Agent 2
    if agent2_invoked and text_distilbert_prob is not None and text_tfidf_prob is not None:
        blended_text_prob = text_tfidf_prob * 0.55 + text_distilbert_prob * 0.45
    else:
        blended_text_prob = text_tfidf_prob if text_tfidf_prob is not None else -1.0

    # URL extraction and risk boost
    urls = URL_RE.findall(text)
    flagged_urls = [u.rstrip(".,;:!?") for u in urls]
    url_signals_list = [extract_url_signals(u) for u in flagged_urls]
    url_risk_boost = compute_url_risk_boost(url_signals_list)

    # Prepare signals for ensemble
    signals = {
        "text_prob": blended_text_prob if blended_text_prob >= 0 else -1,
        "blacklist_hit": False,
        "brand_flag": False,
        "upi_rule_score": 0,
        "upi_xgb_prob": -1,
        "deepfake_prob": -1,
        "malware_prob": -1,
        "call_fraud_prob": -1,
        "regex_score": regex_score,
        "regex_high": regex_high,
        "regex_triggered": regex_triggered,
        "regex_safe": regex_safe,
        "url_risk_boost": url_risk_boost,
    }

    result = ensemble_compute(signals, scan_type="text")
    scam_score = result["scam_score"]
    verdict = result["verdict"]
    confidence = result["confidence"]

    # Build agents_used list
    agents_used = ["agent14", "agent1"]
    if agent2_invoked:
        agents_used.append("agent2")
    agents_used.append("agent15")

    # Build findings from triggered regex rules
    findings = []
    if regex_triggered:
        for rule in regex_triggered:
            findings.append({
                "type": "regex_rule",
                "severity": regex_severity.lower() if regex_severity else "medium",
                "title": rule.replace("_", " ").title(),
                "detail": f"Pattern '{rule}' matched in message content."
            })

    return {
        "scam_score": scam_score,
        "verdict": verdict,
        "verdict_label": verdict.replace("_", " ").title(),
        "top_signal": result["top_signal"],
        "confidence": confidence,
        "flagged_urls": flagged_urls,
        "findings": findings,
        "warning_count": len(findings),
        "extracted_text": text,
        "kind": "message",
        "flagged": verdict == "high_risk",
        "signals": {
            "text_tfidf_prob": round(text_tfidf_prob, 4) if text_tfidf_prob is not None else None,
            "text_distilbert_prob": round(text_distilbert_prob, 4) if text_distilbert_prob is not None else None,
            "regex_score": regex_score,
            "regex_severity": regex_severity,
            "regex_triggered": regex_triggered if regex_triggered else None,
        },
        "meta": {"agents_used": agents_used, "agent2_invoked": agent2_invoked},
    }


async def analyze_url(
    url: str,
    user_id: str,
    request_id: str = "",
    endpoint: str = "/api/v1/analyze-url",
) -> dict:
    """Analyze a URL for phishing/malicious signals."""
    from app.ml.agents.inference import agent3_predict_url, agent4_check_blacklist, agent8_check_brand
    
    # Agent 4: Blacklist
    blacklisted, domain = agent4_check_blacklist(url)
    
    # Agent 8: Brand impersonation
    brand_flag, brand_name, _ = agent8_check_brand(url)
    
    # Agent 3: URL XGBoost
    url_prob = agent3_predict_url(url)
    
    signals = {
        "url_prob": url_prob if url_prob >= 0 else -1,
        "blacklist_hit": blacklisted,
        "brand_flag": brand_flag,
        "regex_score": 0,
        "regex_high": False,
        "regex_triggered": [],
        "text_prob": -1,
        "upi_rule_score": 0,
        "upi_xgb_prob": -1,
        "deepfake_prob": -1,
        "malware_prob": -1,
        "call_fraud_prob": -1,
    }
    
    result = ensemble_compute(signals, scan_type="url")
    
    return {
        "scam_score": result["scam_score"],
        "verdict": result["verdict"],
        "confidence": result["confidence"],
        "domain": domain,
        "brand_flag": brand_flag,
        "brand_name": brand_name,
        "url_prob": url_prob,
    }


async def analyze_upi_module():
    """Lazy import UPI analysis modules."""
    from app.ml.agents.inference import agent6_scan_upi, agent7_predict_upi, agent1_predict_text, agent14_score_text
    from agents.agent15_ensemble import compute as ensemble_compute
    return agent6_scan_upi, agent7_predict_upi, agent1_predict_text, agent14_score_text, ensemble_compute


async def analyze_upi_transaction(
    txn: dict,
    user_id: str,
    request_id: str = "",
) -> dict:
    """Analyze a UPI transaction for fraud signals."""
    agent6_scan_upi, agent7_predict_upi, agent1_predict_text, agent14_score_text, ensemble_compute = await import_upi_module()
    
    # Agent 6: Heuristic rules
    upi_rule = agent6_scan_upi(txn)
    
    # Agent 7: XGBoost (only if heuristic not HIGH)
    upi_xgb = agent7_predict_upi(txn) if upi_rule.get("severity") != "HIGH" else -1
    
    # Agent 1: TF-IDF on note
    tfidf = agent1_predict_text(txn.get("note", "")) if txn.get("note") else -1
    
    # Agent 14: Regex on note
    regex = agent14_score_text(txn.get("note", "")) if txn.get("note") else {"score": 0, "severity": "SAFE", "triggered": []}
    
    signals = {
        "upi_rule_score": upi_rule.get("score", 0),
        "upi_xgb_prob": upi_xgb if upi_xgb >= 0 else -1,
        "text_prob": tfidf if tfidf >= 0 else -1,
        "regex_score": regex.get("score", 0),
        "regex_high": regex.get("severity") == "HIGH",
        "regex_triggered": regex.get("triggered", []),
        "blacklist_hit": False,
        "brand_flag": False,
        "url_prob": -1,
        "deepfake_prob": -1,
        "malware_prob": -1,
        "call_fraud_prob": -1,
    }
    
    result = ensemble_compute(signals, scan_type="upi")
    
    return {
        "scam_score": result["scam_score"],
        "verdict": result["verdict"],
        "confidence": result["confidence"],
        "upi_rule": upi_rule,
        "upi_xgb": upi_xgb,
    }


import time