import logging
import re
import time
from datetime import datetime, timezone
from typing import Literal, Optional
from fastapi import APIRouter, Header, Request
from pydantic import BaseModel
from app.auth import require_user, enforce_credit_cap, calculate_effective_cap, record_bonus_consumption
from app.database import supabase
from app.helpers import get_config_dict, persist_scan
from schemas.scan_result import verdict_label as _verdict_label
from app.ml.agents.inference import agent1_predict_text
from agents.agent15_ensemble import compute
from app.ml.model_loader import get_models
from app.analytics.posthog_client import get_posthog_client
from app.analytics.error_tracker import track_db_error

router = APIRouter(tags=["text"])
logger = logging.getLogger("scamshield.text")

class AnalyzeTextIn(BaseModel):
    text: str
    os: Literal["iOS", "Android"]

URL_RE = re.compile(r"https?://[^\s\)\"\'\>\<\]]+")

@router.post("/api/v1/analyze-text")
async def analyze_text(request: Request,
                       body: AnalyzeTextIn,
                       authorization: str = Header(None),
                       x_device_id: Optional[str] = Header(None)):
    t0 = time.time()
    user_id = require_user(authorization)
    request.state.user_id = user_id
    request.state.platform = body.os
    endpoint = request.url.path
    request_id = getattr(request.state, "request_id", "")

    posthog = get_posthog_client()
    posthog.capture_event("scan_received", user_id, properties={"channel": "text"},
                          request_id=request_id, endpoint=endpoint, platform=body.os)

    try:
        try:
            config = get_config_dict()
            base_cap = config.get("scan_credit_cap", 50)
        except Exception as e:
            logger.warning("get_config_dict failed (is migration applied?): %s", e)
            track_db_error("get_config_dict", e, user_id, request_id, endpoint, body.os)
            base_cap = 50
    today_start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    count_result = supabase.table("scans") \
        .select("id", count="exact") \
        .eq("user_id", user_id) \
        .gte("created_at", today_start) \
        .execute()
    scan_count = count_result.count if count_result.count is not None else 0
    effective_cap = calculate_effective_cap(user_id, base_cap)
    enforce_credit_cap(user_id, effective_cap, scan_count)

    from app.preprocessing.text_normalizer import normalize
    text = normalize(body.text)

    # Gate empty/very-short text — no ML needed
    stripped = text.strip()
    has_content = any(c.isalnum() for c in stripped)
    if not stripped or not has_content or (len(stripped) < 4 and not any(k in stripped for k in ("@", "http", "www"))):
        scan_id = ""
        try:
            scan_id = await persist_scan("message", user_id, body.os, x_device_id, text,
                                   {"risk_score": 0, "verdict": "low_risk", "verdict_label": "Low Risk",
                                    "warning_count": 0, "findings": [],
                                    "flagged_urls": []}, False)
            if scan_id and scan_count >= base_cap:
                record_bonus_consumption(user_id, scan_id)
        except Exception:
            pass
        return {
            "scan_id": scan_id, "scam_score": 0, "verdict": "low_risk", "verdict_label": "Low Risk",
            "top_signal": "empty_or_very_short_input", "confidence": 1.0,
            "flagged_urls": [], "findings": [], "warning_count": 0,
            "extracted_text": text, "kind": "message", "flagged": False,
            "signals": {}, "meta": {"agents_used": [], "agent2_invoked": False},
        }

    posthog.capture_event("analysis_started", user_id, properties={"channel": "text"},
                          request_id=request_id, endpoint=endpoint, platform=body.os)

    from app.ml.agents.inference import agent14_score_text
    regex_result = agent14_score_text(text)
    regex_score = regex_result["score"]
    regex_severity = regex_result["severity"]
    regex_triggered = regex_result["triggered"]
    regex_high = regex_severity == "HIGH"

    models = get_models()
    text_tfidf_prob = None
    raw_a1 = agent1_predict_text(text)
    if raw_a1 >= 0:
        text_tfidf_prob = raw_a1

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
        scan_id = await persist_scan("message", user_id, body.os, x_device_id, text,
                               {"risk_score": scam_score, "verdict": verdict, "verdict_label": _verdict_label(verdict),
                                "warning_count": len(findings), "findings": findings,
                                "flagged_urls": flagged_urls},
                               verdict == "high_risk")
        if scan_id and scan_count >= base_cap:
            record_bonus_consumption(user_id, scan_id)
    except Exception as e:
        logger.warning("Failed to persist scan (non-fatal): %s", e)
        track_db_error("persist_scan", e, user_id, request_id, endpoint, body.os)

    elapsed = int(round((time.time() - t0) * 1000))
    posthog.capture_scan_event(
        event="analysis_completed",
        user_id=user_id,
        channel="text",
        verdict=verdict,
        score=scam_score,
        latency_ms=elapsed,
        request_id=request_id,
        endpoint=endpoint,
        platform=body.os,
        agents_used=agents_used,
    )

    return {
        "scan_id": scan_id,
        "scam_score": scam_score,
        "verdict": verdict, "verdict_label": _verdict_label(verdict),
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
    except Exception as exc:
        elapsed = int(round((time.time() - t0) * 1000))
        posthog.capture_scan_event(
            event="analysis_failed",
            user_id=user_id,
            channel="text",
            verdict="error",
            score=0,
            latency_ms=elapsed,
            request_id=request_id,
            endpoint=endpoint,
            platform=body.os,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise
