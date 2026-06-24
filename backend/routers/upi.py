import logging
from typing import Literal, Optional
from fastapi import APIRouter, Header
from pydantic import BaseModel, Field
from app.auth import require_user
from app.helpers import persist_scan
from agents.agent15_ensemble import compute_ensemble_verdict

router = APIRouter(tags=["upi"])
logger = logging.getLogger("scamshield.upi")

class AnalyzeUPIIn(BaseModel):
    amount: float = 0.0
    note: str = Field(default="", max_length=512)
    vpa: str = Field(default="", max_length=128)
    channel: str = Field(default="", max_length=64)
    os: Literal["iOS", "Android"]

@router.post("/api/v1/analyze-upi")
async def analyze_upi(body: AnalyzeUPIIn,
                      authorization: str = Header(None),
                      x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)
    from app.preprocessing.text_normalizer import normalize
    from app.ml.agents.inference import agent6_scan_upi, agent7_predict_upi, agent1_predict_text, agent14_score_text

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
        "verdict": verdict,
        "warning_count": warning_count,
        "extracted_text": body.note,
        "findings": findings,
        "flagged_urls": [],
    }
    try:
        scan_id = persist_scan("upi", user_id, body.os, x_device_id, body.note, result, flagged)
    except Exception as e:
        logger.warning("Failed to persist scan (non-fatal): %s", e)
        scan_id = ""
    return {"scan_id": scan_id, "kind": "upi", "flagged": flagged, **result, "_meta": None}
