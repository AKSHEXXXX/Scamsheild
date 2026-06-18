import base64
import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from app.models import AnalyzeOut, OcrMeta, SandboxImageRequest
from app.database import supabase
from app.auth import require_user, enforce_credit_cap
from app.ocr import screenshot_ocr
from app.analyzer import analyze
from app.helpers import get_config_dict, persist_scan

router = APIRouter(tags=["image"])
logger = logging.getLogger("scamshield.image")

class SandboxFileIn(BaseModel):
    filename: str = ""
    file_bytes_b64: str
    os: str

@router.post("/api/v1/sandbox-image", response_model=AnalyzeOut)
async def sandbox_image(body: SandboxImageRequest,
                        authorization: str = Header(None),
                        x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)
    config = get_config_dict()
    cap = config["scan_credit_cap"]
    today_start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    count_result = supabase.table("scans") \
        .select("id", count="exact") \
        .eq("user_id", user_id) \
        .gte("created_at", today_start) \
        .execute()
    scan_count = count_result.count if count_result.count is not None else 0
    enforce_credit_cap(user_id, cap, scan_count)
    device_id = body.device_id or x_device_id or "unknown"
    ocr_output = screenshot_ocr.extract_from_base64(
        image_b64=body.image,
        fallback_reason=body.fallback_reason
    )
    if not ocr_output.text.strip():
        raise HTTPException(status_code=422, detail={
            "error": "Could not extract text from image",
            "code": "OCR_FAILED",
            "suggestion": "Please try a clearer screenshot with visible text"
        })
    logger.info("OCR | device=%s | method=%s | chars=%d | conf=%.2f",
                device_id, ocr_output.method, ocr_output.char_count, ocr_output.confidence)
    from app.ml.agents.inference import agent14_score_text
    regex_result = agent14_score_text(ocr_output.text)
    logger.info("Agent 14 regex on OCR text | score=%d severity=%s", regex_result["score"], regex_result["severity"])
    result = await analyze(ocr_output.text)
    scan_id = persist_scan(
        "screenshot", user_id, "iOS" if "iOS" in device_id else "Android",
        device_id, ocr_output.text, result, result["verdict"] == "high_risk",
        ocr_method=ocr_output.method, ocr_confidence=ocr_output.confidence,
        ocr_fallback=ocr_output.fallback_used
    )
    return AnalyzeOut(
        scan_id=scan_id, kind="screenshot", **result,
        _meta=OcrMeta(
            ocr_method=ocr_output.method,
            ocr_confidence=round(ocr_output.confidence, 2),
            ocr_fallback=ocr_output.fallback_used
        )
    )

@router.post("/api/v1/sandbox-file")
async def sandbox_file(body: SandboxFileIn,
                       authorization: str = Header(None),
                       x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)
    try:
        file_bytes = base64.b64decode(body.file_bytes_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 file data")
    from app.ml.agents.inference import agent11_predict_malware
    from agents.agent15_ensemble import compute_ensemble_verdict
    malware_prob = agent11_predict_malware(file_bytes)
    score, verdict, ml_debug = compute_ensemble_verdict(
        malware_prob=malware_prob,
        scan_type="image",
    )
    findings = [{"type": "malware", "severity": "high" if malware_prob > 0.5 else "low",
                 "title": "Malware Analysis", "detail": f"Malware probability: {malware_prob:.4f}"}]
    result = {
        "scam_score": min(100, score),
        "verdict": verdict,
        "warning_count": 1 if malware_prob > 0.5 else 0,
        "extracted_text": body.filename,
        "findings": findings,
        "flagged_urls": [],
    }
    try:
        scan_id = persist_scan("file", user_id, body.os, x_device_id, body.filename, result, verdict == "high_risk")
    except Exception as e:
        logger.warning("Failed to persist scan (non-fatal): %s", e)
        scan_id = ""
    return {"scan_id": scan_id, "kind": "file", **result, "_meta": None}
