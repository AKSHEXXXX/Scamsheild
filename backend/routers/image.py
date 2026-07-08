import base64
import os
import logging
import time
from typing import Literal, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException, File, UploadFile, Form, Request
from pydantic import BaseModel, ValidationError
from app.models import AnalyzeOut, SandboxImageRequest
from app.database import supabase
from app.auth import require_user, enforce_credit_cap, calculate_effective_cap, record_bonus_consumption
from app.ocr import screenshot_ocr
from app.analyzer import analyze
from app.helpers import get_config_dict, persist_scan
from schemas.scan_result import verdict_label as _verdict_label
from app.analytics.posthog_client import get_posthog_client
from app.analytics.error_tracker import track_db_error, track_external_api_error

router = APIRouter(tags=["image"])
logger = logging.getLogger("scamshield.image")

class SandboxFileIn(BaseModel):
    filename: str = ""
    file_bytes_b64: str
    os: Literal["iOS", "Android"]

@router.post("/api/v1/sandbox-image")
async def sandbox_image(request: Request,
                        authorization: str = Header(None),
                        x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)
    request.state.user_id = user_id
    content_type = request.headers.get("content-type", "")
    endpoint = request.url.path
    request_id = getattr(request.state, "request_id", "")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file") or form.get("image")
        if upload is None or not hasattr(upload, "read"):
            logger.warning("sandbox-image 422: multipart body missing 'file'/'image' field. fields=%s",
                           list(form.keys()))
            raise HTTPException(status_code=422, detail={
                "error": "Expected a 'file' or 'image' multipart field containing the image",
                "code": "MULTIPART_FIELD_MISSING",
            })
        file_bytes = await upload.read()
        image_b64 = base64.b64encode(file_bytes).decode("utf-8")
        device_id_field = form.get("device_id")
        fallback_reason_field = form.get("fallback_reason")
        body = SandboxImageRequest(
            image=image_b64,
            device_id=(device_id_field if isinstance(device_id_field, str) else None) or x_device_id,
            fallback_reason=(fallback_reason_field if isinstance(fallback_reason_field, str) else None),
        )
        platform = "iOS" if "iOS" in (x_device_id or "") else "Android"
        request.state.platform = platform
        return await _process_sandbox_image(body, user_id, platform, x_device_id, request_id, endpoint)

    raw = await request.body()
    try:
        import json
        payload = json.loads(raw or b"{}")
    except Exception as e:
        logger.warning("sandbox-image 422: non-JSON body (content-type=%r, len=%d): %r | error=%s",
                       content_type, len(raw), raw[:300], e)
        raise HTTPException(status_code=422, detail={
            "error": "Expected application/json or multipart/form-data",
            "code": "UNSUPPORTED_CONTENT_TYPE",
            "content_type_received": content_type,
        })
    try:
        body = SandboxImageRequest(**payload)
    except ValidationError as e:
        logger.warning("sandbox-image 422: JSON body did not match schema. body_keys=%s | errors=%s",
                       list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__, e.errors())
        raise HTTPException(status_code=422, detail={
            "error": "Invalid request body",
            "code": "SCHEMA_MISMATCH",
            "expected_fields": {"image": "required base64 string", "device_id": "optional string", "fallback_reason": "optional string"},
            "received_keys": list(payload.keys()) if isinstance(payload, dict) else None,
        })
    platform = body.device_id or x_device_id or "unknown"
    request.state.platform = platform
    return await _process_sandbox_image(body, user_id, platform, x_device_id, request_id, endpoint)

@router.post("/api/v1/sandbox-image-upload")
async def sandbox_image_upload(request: Request,
                                file: UploadFile = File(...),
                                authorization: str = Header(None),
                                x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)
    request.state.user_id = user_id
    endpoint = request.url.path
    request_id = getattr(request.state, "request_id", "")
    file_bytes = await file.read()
    image_b64 = base64.b64encode(file_bytes).decode("utf-8")
    body = SandboxImageRequest(image=image_b64, device_id=x_device_id)
    platform = x_device_id or "unknown"
    request.state.platform = platform
    return await _process_sandbox_image(body, user_id, platform, x_device_id, request_id, endpoint)


async def _process_sandbox_image(
    body: SandboxImageRequest,
    user_id: str,
    platform: str,
    x_device_id: Optional[str],
    request_id: str,
    endpoint: str,
):
    t0 = time.time()
    posthog = get_posthog_client()

    posthog.capture_event("image_uploaded", user_id, properties={},
                          request_id=request_id, endpoint=endpoint, platform=platform)

    try:
        config = get_config_dict()
        base_cap = config.get("scan_credit_cap", 50)
    except Exception as e:
        logger.warning("get_config_dict failed (is migration applied?): %s", e)
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
    device_id = body.device_id or x_device_id or "unknown"

    ocr_t0 = time.time()
    posthog.capture_event("ocr_started", user_id, properties={},
                          request_id=request_id, endpoint=endpoint, platform=platform)
    ocr_output = screenshot_ocr.extract_from_base64(
        image_b64=body.image,
        fallback_reason=body.fallback_reason
    )
    ocr_elapsed = int(round((time.time() - ocr_t0) * 1000))

    if not ocr_output.text.strip():
        posthog.capture_ocr_event(
            event="ocr_failed", user_id=user_id,
            method=ocr_output.method, confidence=ocr_output.confidence,
            char_count=ocr_output.char_count, fallback_used=ocr_output.fallback_used,
            latency_ms=ocr_elapsed, request_id=request_id, endpoint=endpoint,
            platform=platform, error_message="No text extracted from image",
        )
        raise HTTPException(status_code=422, detail={
            "error": "Could not extract text from image",
            "code": "OCR_FAILED",
            "suggestion": "Please try a clearer screenshot with visible text",
        })

    posthog.capture_ocr_event(
        event="ocr_completed", user_id=user_id,
        method=ocr_output.method, confidence=ocr_output.confidence,
        char_count=ocr_output.char_count, fallback_used=ocr_output.fallback_used,
        latency_ms=ocr_elapsed, request_id=request_id, endpoint=endpoint, platform=platform,
    )
    logger.info("OCR | device=%s | method=%s | chars=%d | conf=%.2f",
                device_id, ocr_output.method, ocr_output.char_count, ocr_output.confidence)

    from app.preprocessing.text_normalizer import normalize
    from app.ml.agents.inference import agent14_score_text

    import re as _re
    ocr_output.text = _re.sub(r'(?<=\b\w)\s(?=\w\b)', '', ocr_output.text)
    ocr_output.text = normalize(ocr_output.text)

    posthog.capture_event("analysis_started", user_id, properties={"channel": "image"},
                          request_id=request_id, endpoint=endpoint, platform=platform)

    regex_result = agent14_score_text(ocr_output.text)
    logger.info("Agent 14 regex on OCR text | score=%d severity=%s safe=%s",
                regex_result["score"], regex_result["severity"], regex_result.get("regex_safe", False))
    result = analyze(ocr_output.text,
                     regex_score=regex_result["score"],
                     regex_high=regex_result["severity"] == "HIGH",
                     regex_triggered=regex_result.get("triggered", []),
                     regex_safe=regex_result.get("regex_safe", False))
    scan_id = ""
    try:
        scan_id = await persist_scan(
            "screenshot", user_id, "iOS" if "iOS" in device_id else "Android",
            device_id, ocr_output.text, result, result["verdict"] == "high_risk",
            ocr_method=ocr_output.method, ocr_confidence=ocr_output.confidence,
            ocr_fallback=ocr_output.fallback_used
        )
        if scan_id and scan_count >= base_cap:
            record_bonus_consumption(user_id, scan_id)
    except Exception as e:
        logger.warning("Failed to persist scan (non-fatal): %s", e)
        track_db_error("persist_scan_screenshot", e, user_id, request_id, endpoint, platform)

    elapsed = int(round((time.time() - t0) * 1000))
    posthog.capture_scan_event(
        event="analysis_completed", user_id=user_id,
        channel="image", verdict=result["verdict"], score=result["scam_score"],
        latency_ms=elapsed, request_id=request_id, endpoint=endpoint, platform=platform,
    )

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
async def sandbox_file(request: Request,
                       body: SandboxFileIn,
                       authorization: str = Header(None),
                       x_device_id: Optional[str] = Header(None)):
    t0 = time.time()
    user_id = require_user(authorization)
    request.state.user_id = user_id
    request.state.platform = body.os
    endpoint = request.url.path
    request_id = getattr(request.state, "request_id", "")
    posthog = get_posthog_client()

    posthog.capture_event("scan_received", user_id, properties={"channel": "file"},
                          request_id=request_id, endpoint=endpoint, platform=body.os)
    try:
        file_bytes = base64.b64decode(body.file_bytes_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 file data")

    posthog.capture_event("analysis_started", user_id, properties={"channel": "file"},
                          request_id=request_id, endpoint=endpoint, platform=body.os)

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
        "verdict": verdict, "verdict_label": _verdict_label(verdict),
        "warning_count": (1 if malware_prob > 0.5 else 0) + len(regex_result["triggered"]),
        "extracted_text": body.filename,
        "findings": findings,
        "flagged_urls": [],
    }
    flagged = verdict == "high_risk"
    try:
        scan_id = await persist_scan("file", user_id, body.os, x_device_id, body.filename, result, flagged)
    except Exception as e:
        logger.warning("Failed to persist scan (non-fatal): %s", e)
        scan_id = ""

    elapsed = int(round((time.time() - t0) * 1000))
    posthog.capture_scan_event(
        event="analysis_completed", user_id=user_id,
        channel="file", verdict=verdict, score=result["scam_score"],
        latency_ms=elapsed, request_id=request_id, endpoint=endpoint, platform=body.os,
    )
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
