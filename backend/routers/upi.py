import logging
from typing import Optional
from fastapi import APIRouter, Header
from pydantic import BaseModel
from app.auth import require_user
from app.helpers import persist_scan
from agents.agent15_ensemble import compute_ensemble_verdict

router = APIRouter(tags=["upi"])
logger = logging.getLogger("scamshield.upi")

class AnalyzeUPIIn(BaseModel):
    amount: float = 0.0
    note: str = ""
    vpa: str = ""
    channel: str = ""
    os: str

@router.post("/api/v1/analyze-upi")
async def analyze_upi(body: AnalyzeUPIIn,
                      authorization: str = Header(None),
                      x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)
    from app.ml.agents.inference import agent6_scan_upi, agent7_predict_upi, agent1_predict_text, agent14_score_text

    txn = {"amount": body.amount, "note": body.note, "vpa": body.vpa, "channel": body.channel}
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
        scan_type="upi",
    )

    findings = [{"type": "upi_heuristic", "severity": heuristic["severity"],
                 "title": "UPI Rule Engine", "detail": heuristic["explanation"]}]
    warning_count = 1 if heuristic["severity"] in ("HIGH", "MEDIUM") else 0
    result = {
        "risk_score": min(100, score),
        "verdict": verdict,
        "warning_count": warning_count,
        "extracted_text": body.note,
        "findings": findings,
        "flagged_urls": [],
    }
    scan_id = persist_scan("upi", user_id, body.os, x_device_id, body.note, result, verdict == "high_risk")
    return {"scan_id": scan_id, "kind": "upi", **result, "_meta": None}
