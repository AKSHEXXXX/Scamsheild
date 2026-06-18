import logging
import re
from typing import Optional
from fastapi import APIRouter, Header
from pydantic import BaseModel
from app.auth import require_user
from app.helpers import persist_scan
from agents.agent1_text_tfidf import predict as agent1_predict
from agents.agent15_ensemble import compute
from models.loader import get_models
from schemas.scan_result import ScanResult, SignalsBlock
from utils.url import extract_domain

router = APIRouter(tags=["text"])
logger = logging.getLogger("scamshield.text")

class AnalyzeTextIn(BaseModel):
    text: str
    os: str

URL_RE = re.compile(r"https?://[^\s\)\"\'\>\<\]]+")

@router.post("/api/v1/analyze-text", response_model=ScanResult)
async def analyze_text(body: AnalyzeTextIn,
                       authorization: str = Header(None),
                       x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)
    text = body.text

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
    if text_tfidf_prob is not None and 0.15 <= text_tfidf_prob <= 0.85:
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
    }
    result = compute(signals, scan_type="text")

    scam_score = result["scam_score"]
    verdict = result["verdict"]
    confidence = result["confidence"]

    urls = URL_RE.findall(text)
    flagged_urls = [u.rstrip(".,;:!?") for u in urls]

    agents_used = ["agent14", "agent1"]
    if agent2_invoked:
        agents_used.append("agent2")
    agents_used.append("agent15")

    scan_result = ScanResult(
        scam_score=scam_score,
        verdict=verdict,
        signals=SignalsBlock(
            text_tfidf_prob=round(text_tfidf_prob, 4) if text_tfidf_prob is not None else None,
            text_distilbert_prob=round(text_distilbert_prob, 4) if text_distilbert_prob is not None else None,
            regex_score=regex_score,
            regex_severity=regex_severity,
            regex_triggered=regex_triggered if regex_triggered else None,
        ),
        top_signal=result["top_signal"],
        confidence=confidence,
        flagged_urls=flagged_urls,
        meta={"agents_used": agents_used, "agent2_invoked": agent2_invoked},
    )
    try:
        persist_scan("message", user_id, body.os, x_device_id, text,
                     {"risk_score": scam_score, "verdict": verdict, "warning_count": 0, "findings": [], "flagged_urls": flagged_urls},
                     verdict == "high_risk")
    except Exception as e:
        logger.warning("Failed to persist scan (non-fatal): %s", e)
    return scan_result
