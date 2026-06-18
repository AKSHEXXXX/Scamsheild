import logging
from typing import Optional
from fastapi import APIRouter, Header
from pydantic import BaseModel
from app.auth import require_user
from app.helpers import persist_scan
from agents.agent4_blacklist import check as blacklist_check
from agents.agent15_ensemble import compute_ensemble_verdict
from models.loader import get_models

router = APIRouter(tags=["qr"])
logger = logging.getLogger("scamshield.qr")

class CheckQRIn(BaseModel):
    payload: str
    os: str

@router.post("/api/v1/check-qr")
async def check_qr(body: CheckQRIn,
                   authorization: str = Header(None),
                   x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)
    payload = body.payload

    from app.ml.agents.inference import agent5_predict_qr_payload, agent1_predict_text, agent8_check_brand, agent14_score_text
    qr_prob = agent5_predict_qr_payload(payload)
    text_prob = agent1_predict_text(payload)

    bl_models = get_models().get("agent4")
    bl_hit, bl_domain = False, None
    if bl_models:
        bl_result = blacklist_check(payload, bl_models)
        bl_hit, bl_domain = bl_result["blacklist_hit"], bl_result["blacklist_domain"]
    else:
        from app.ml.agents.inference import agent4_check_blacklist
        bl_hit, bl_domain = agent4_check_blacklist(payload)

    brand_flag, matched_brand, _ = agent8_check_brand(payload)
    regex_result = agent14_score_text(payload)

    score, verdict, ml_debug = compute_ensemble_verdict(
        ml_text_prob=text_prob,
        ml_qr_prob=qr_prob,
        rule_score=regex_result["score"],
        has_blacklisted_domain=bl_hit,
        brand_flag=brand_flag,
        regex_score=regex_result["score"],
        regex_high=regex_result["severity"] == "HIGH",
        scan_type="qr",
    )

    findings = [{"type": "ml_ensemble", "severity": "info", "title": "ML scores",
                 "detail": str(ml_debug)}]
    warning_count = sum(1 for f in findings if f["severity"] in ("high", "medium"))
    result = {
        "scam_score": min(100, score),
        "verdict": verdict,
        "warning_count": warning_count,
        "extracted_text": payload,
        "findings": findings,
        "flagged_urls": [],
    }
    try:
        scan_id = persist_scan("qr", user_id, body.os, x_device_id, payload, result, verdict == "high_risk")
    except Exception as e:
        logger.warning("Failed to persist scan (non-fatal): %s", e)
        scan_id = ""
    return {"scan_id": scan_id, "kind": "qr", **result, "_meta": None}
