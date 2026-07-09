import logging
import time
from typing import Literal, Optional
from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field
from app.auth import require_user
from app.helpers import persist_scan
from schemas.scan_result import verdict_label as _verdict_label
from agents.agent15_ensemble import compute_ensemble_verdict
from app.analytics.posthog_client import get_posthog_client

router = APIRouter(tags=["upi"])
logger = logging.getLogger("scamshield.upi")

class AnalyzeUPIIn(BaseModel):
    amount: float = 0.0
    note: str = Field(default="", max_length=512)
    vpa: str = Field(default="", max_length=128)
    channel: str = Field(default="", max_length=64)
    os: Literal["iOS", "Android"]

@router.post("/api/v1/analyze-upi")
async def analyze_upi(request: Request,
                      body: AnalyzeUPIIn,
                      authorization: str = Header(None),
                      x_device_id: Optional[str] = Header(None)):
    t0 = time.time()
    user_id = require_user(authorization)
    request.state.user_id = user_id
    request.state.platform = body.os
    endpoint = request.url.path
    request_id = getattr(request.state, "request_id", "")
    posthog = get_posthog_client()

    posthog.capture_event("scan_received", user_id, properties={"channel": "upi"},
                          request_id=request_id, endpoint=endpoint, platform=body.os)

    try:
        from app.preprocessing.text_normalizer import normalize
        from app.ml.agents.inference import agent6_scan_upi, agent7_predict_upi, agent1_predict_text, agent14_score_text

        posthog.capture_event("analysis_started", user_id, properties={"channel": "upi"},
                              request_id=request_id, endpoint=endpoint, platform=body.os)

        txn = {"amount": body.amount, "note": normalize(body.note), "vpa": body.vpa, "channel": body.channel}
        heuristic = agent6_scan_upi(txn)
        upi_rule_score = heuristic["score"]
        upi_xgb_prob = agent7_predict_upi(txn) if heuristic["severity"] != "HIGH" else -1.0
        text_prob = agent1_predict_text(f"{body.note} {body.vpa}")
        regex_result = agent14_score_text(body.note)

        score, verdict, ml_debug = compute_ensemble_verdict(
            ml_text_prob=text_prob,
            upi_rule_score=upi_rule_score,
            upi_xgb_prob=upi_xgb_prob if upi_xgb_prob >= 0 else -1.0,
            rule_score=regex_result["score"],
            regex_score=regex_result["score"],
            regex_high=regex_result["severity"] == "HIGH",
            regex_triggered=regex_result.get("triggered", []),
            scan_type="upi",
        )

        findings = [{"type": "upi_heuristic", "severity": heuristic["severity"],
                     "title": "UPI Rule Engine", "detail": heuristic["explanation"]}]
        warning_count = 1 if heuristic["severity"] in ("HIGH", "MEDIUM") else 0
        flagged = verdict == "high_risk"
        result = {
            "scam_score": min(100, score),
            "verdict": verdict, "verdict_label": _verdict_label(verdict),
            "warning_count": warning_count,
            "extracted_text": body.note,
            "findings": findings,
            "flagged_urls": [],
        }
        try:
            scan_id = await persist_scan("upi", user_id, body.os, x_device_id, body.note, result, flagged)
        except Exception as e:
            logger.warning("Failed to persist scan (non-fatal): %s", e)
            scan_id = ""

        elapsed = int(round((time.time() - t0) * 1000))
        posthog.capture_scan_event(
            event="analysis_completed", user_id=user_id,
            channel="upi", verdict=verdict, score=result["scam_score"],
            latency_ms=elapsed, request_id=request_id, endpoint=endpoint, platform=body.os,
            agents_used=["agent6", "agent7", "agent1", "agent14", "agent15"],
            extra_properties={"top_signal": result.get("top_signal", ""), "input_type": "upi"},
        )
        return {"scan_id": scan_id, "kind": "upi", "flagged": flagged, **result, "_meta": None}
    except Exception as exc:
        elapsed = int(round((time.time() - t0) * 1000))
        posthog.capture_scan_event(
            event="analysis_failed", user_id=user_id,
            channel="upi", verdict="error", score=0,
            latency_ms=elapsed, request_id=request_id, endpoint=endpoint, platform=body.os,
            error_type=type(exc).__name__, error_message=str(exc),
            extra_properties={"input_type": "upi"},
        )
        raise
