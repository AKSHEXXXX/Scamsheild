import logging
import re
from typing import Literal, Optional
from fastapi import APIRouter, Header
from pydantic import BaseModel
from app.auth import require_user
from app.helpers import persist_scan
from agents.agent1_text_tfidf import predict as agent1_predict
from agents.agent15_ensemble import compute
from app.ml.model_loader import get_models
from schemas.scan_result import SignalsBlock

router = APIRouter(tags=["text"])
logger = logging.getLogger("scamshield.text")

class AnalyzeTextIn(BaseModel):
    text: str
    os: Literal["iOS", "Android"]

URL_RE = re.compile(r"https?://[^\s\)\"\'\>\<\]]+")

@router.post("/api/v1/analyze-text")
async def analyze_text(body: AnalyzeTextIn,
                       authorization: str = Header(None),
                       x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)
    from app.preprocessing.text_normalizer import normalize
    text = normalize(body.text)

    # Gate empty/very-short text — no ML needed
    stripped = text.strip()
    has_content = any(c.isalnum() for c in stripped)
    if not stripped or not has_content or (len(stripped) < 4 and not any(k in stripped for k in ("@", "http", "www"))):
        scan_id = ""
        try:
            scan_id = persist_scan("message", user_id, body.os, x_device_id, text,
                                   {"risk_score": 0, "verdict": "low_risk",
                                    "warning_count": 0, "findings": [],
                                    "flagged_urls": []}, False)
        except Exception:
            pass
        return {
            "scan_id": scan_id, "scam_score": 0, "verdict": "low_risk",
            "top_signal": "empty_or_very_short_input", "confidence": 1.0,
            "flagged_urls": [], "findings": [], "warning_count": 0,
            "extracted_text": text, "kind": "message", "flagged": False,
            "signals": {}, "meta": {"agents_used": [], "agent2_invoked": False},
        }

    from app.ml.agents.inference import agent14_score_text
    regex_result = agent14_score_text(text)
    regex_score = regex_result["score"]
    regex_severity = regex_result["severity"]
    regex_triggered = regex_result["triggered"]
    regex_high = regex_severity == "HIGH"

    models = get_models()
    text_tfidf_prob = None
    if "agent1" in models:
        try:
            text_tfidf_prob = agent1_predict(text, models["agent1"])
        except Exception as e:
            logger.warning("Agent 1 predict error: %s", e)

    text_distilbert_prob = None
    agent2_invoked = False
    if text_tfidf_prob is not None and 0.35 <= text_tfidf_prob <= 0.65:
        agent2_available = models.get("agent2") is not None
        if agent2_available:
            try:
                from app.ml.agents.inference import agent2_predict_text
                d = agent2_predict_text(text)
                if d >= 0:
                    text_distilbert_prob = d
                    agent2_invoked = True
            except Exception as e:
                logger.warning("Agent 2 predict error: %s", e)

    from app.ml.url_features import extract_url_signals, compute_url_risk_boost
    urls = URL_RE.findall(text)
    flagged_urls = [u.rstrip(".,;:!?") for u in urls]
    url_signals_list = [extract_url_signals(u) for u in flagged_urls]
    url_risk_boost = compute_url_risk_boost(url_signals_list)

    signals = {
        "text_prob": text_tfidf_prob if text_tfidf_prob is not None else -1,
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
        "regex_safe": regex_result.get("regex_safe", False),
        "url_risk_boost": url_risk_boost,
    }
    result = compute(signals, scan_type="text")

    scam_score = result["scam_score"]
    verdict = result["verdict"]
    confidence = result["confidence"]

    agents_used = ["agent14", "agent1"]
    if agent2_invoked:
        agents_used.append("agent2")
    agents_used.append("agent15")

    # Build findings from triggered signals
    findings = []
    if regex_triggered:
        for rule in regex_triggered:
            findings.append({
                "type": "regex_rule",
                "severity": regex_severity.lower() if regex_severity else "medium",
                "title": rule.replace("_", " ").title(),
                "detail": f"Pattern '{rule}' matched in message content."
            })

    scan_id = ""
    try:
        scan_id = persist_scan("message", user_id, body.os, x_device_id, text,
                               {"risk_score": scam_score, "verdict": verdict,
                                "warning_count": len(findings), "findings": findings,
                                "flagged_urls": flagged_urls},
                               verdict == "high_risk")
    except Exception as e:
        logger.warning("Failed to persist scan (non-fatal): %s", e)

    return {
        "scan_id": scan_id,
        "scam_score": scam_score,
        "verdict": verdict,
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
