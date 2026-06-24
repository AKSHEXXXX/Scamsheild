import base64
import os
import logging
from typing import Literal, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from app.models import AnalyzeOut, SandboxImageRequest
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
    os: Literal["iOS", "Android"]

@router.post("/api/v1/sandbox-image")
async def sandbox_image(body: SandboxImageRequest,
                        authorization: str = Header(None),
                        x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)
    return await _process_sandbox_image(body, user_id, x_device_id)

@router.post("/api/v1/sandbox-image-upload")
async def sandbox_image_upload(file: UploadFile = File(...),
                                authorization: str = Header(None),
                                x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)
    file_bytes = await file.read()
    image_b64 = base64.b64encode(file_bytes).decode("utf-8")
    body = SandboxImageRequest(image=image_b64, device_id=x_device_id)
    return await _process_sandbox_image(body, user_id, x_device_id)


async def _process_sandbox_image(body: SandboxImageRequest, user_id: str, x_device_id: Optional[str]):
    try:
        config = get_config_dict()
        cap = config.get("scan_credit_cap", 50)
    except Exception as e:
        logger.warning("get_config_dict failed (is migration applied?): %s", e)
        cap = 50
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
    from app.preprocessing.text_normalizer import normalize
    from app.ml.agents.inference import agent14_score_text

    import re as _re
    ocr_output.text = _re.sub(r'(?<=\b\w)\s(?=\w\b)', '', ocr_output.text)
    ocr_output.text = normalize(ocr_output.text)
    regex_result = agent14_score_text(ocr_output.text)
    logger.info("Agent 14 regex on OCR text | score=%d severity=%s safe=%s", regex_result["score"], regex_result["severity"], regex_result.get("regex_safe", False))
    result = analyze(ocr_output.text,
                     regex_score=regex_result["score"],
                     regex_high=regex_result["severity"] == "HIGH",
                     regex_triggered=regex_result.get("triggered", []),
                     regex_safe=regex_result.get("regex_safe", False))
    scan_id = ""
    try:
        scan_id = persist_scan(
            "screenshot", user_id, "iOS" if "iOS" in device_id else "Android",
            device_id, ocr_output.text, result, result["verdict"] == "high_risk",
            ocr_method=ocr_output.method, ocr_confidence=ocr_output.confidence,
            ocr_fallback=ocr_output.fallback_used
        )
    except Exception as e:
        logger.warning("Failed to persist scan (non-fatal): %s", e)
    flagged_urls = [u["url"] if isinstance(u, dict) else str(u)
                    for u in result.get("flagged_urls", [])]
    return AnalyzeOut(
        scan_id=scan_id,
        scam_score=result["scam_score"],
        verdict=result["verdict"],
        top_signal=result.get("top_signal", "ml_ensemble"),
        flagged_urls=flagged_urls,
        findings=result.get("findings", []),
        warning_count=result.get("warning_count", 0),
        extracted_text=result.get("extracted_text", ocr_output.text),
        kind="screenshot",
        flagged=result["verdict"] == "high_risk",
        meta={
            "ocr_method": ocr_output.method,
            "ocr_confidence": round(ocr_output.confidence, 2),
            "ocr_fallback": ocr_output.fallback_used,
            "ocr_extracted_text": ocr_output.text[:500],
        }
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
    from app.ml.agents.inference import agent11_predict_malware, agent14_score_text
    from agents.agent15_ensemble import compute_ensemble_verdict
    malware_prob = agent11_predict_malware(file_bytes)
    regex_result = agent14_score_text(body.filename)
    score, verdict, ml_debug = compute_ensemble_verdict(
        malware_prob=malware_prob,
        regex_score=regex_result["score"],
        regex_high=regex_result["severity"] == "HIGH",
        regex_triggered=regex_result.get("triggered", []),
        scan_type="image",
    )
    findings = [{"type": "malware", "severity": "high" if malware_prob > 0.5 else "low",
                 "title": "Malware Analysis", "detail": f"Malware probability: {malware_prob:.4f}"}]
    if regex_result["triggered"]:
        findings.append({"type": "regex_rule", "severity": regex_result["severity"].lower(),
                         "title": "Filename Scam Signal", "detail": f"Matched: {', '.join(regex_result['triggered'])}"})
    result = {
        "scam_score": min(100, score),
        "verdict": verdict,
        "warning_count": (1 if malware_prob > 0.5 else 0) + len(regex_result["triggered"]),
        "extracted_text": body.filename,
        "findings": findings,
        "flagged_urls": [],
    }
    flagged = verdict == "high_risk"
    try:
        scan_id = persist_scan("file", user_id, body.os, x_device_id, body.filename, result, flagged)
    except Exception as e:
        logger.warning("Failed to persist scan (non-fatal): %s", e)
        scan_id = ""
    return {"scan_id": scan_id, "kind": "file", "flagged": flagged, **result}


INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")


@router.get("/api/v1/internal/health-ocr")
async def health_ocr(authorization: str = Header(None)):
    if INTERNAL_API_KEY:
        token = (authorization or "").replace("Bearer ", "")
        if token != INTERNAL_API_KEY:
            raise HTTPException(status_code=403, detail="Forbidden")
    from jobs.test_ocr_health import run_health_check
    ok = run_health_check()
    return {"ok": ok}
