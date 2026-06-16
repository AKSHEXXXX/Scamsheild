import os
import uuid
import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.models import (
    ScanIn, SandboxImageRequest, AnalyzeTextIn, AnalyzeOut,
    ConfigOut, ReportIn, ReportOut, HistoryOut, HistoryCounts,
    HistoryItem, OcrMeta
)
from app.database import supabase
from app.auth import require_user, enforce_credit_cap
from app.ocr import screenshot_ocr
from app.config import settings
from app.analyzer import analyze

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scamshield")
app = FastAPI(title="ScamShield API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_config_dict() -> dict:
    result = supabase.table("app_config").select("*").eq("id", 1).single().execute()
    row = result.data
    if not row:
        raise HTTPException(status_code=500, detail="Config not found")
    return {
        "scan_credit_cap": row["scan_credit_cap"],
        "ad_frequency": row["ad_frequency"],
        "sensitivity_threshold": row["sensitivity_threshold"],
        "config_version": row["config_version"],
    }

def persist_scan(kind: str, user_id: str, body_os: str, device_id: Optional[str],
                 input_text: str, result: dict, warned: bool,
                 ocr_method: Optional[str] = None, ocr_confidence: Optional[float] = None):
    scan_id = str(uuid.uuid4())
    record = {
        "id": scan_id,
        "kind": kind,
        "user_id": user_id,
        "device_id": device_id or "unknown",
        "os": body_os,
        "input_text": input_text[:200],
        "result_json": result,
        "risk_score": result["risk_score"],
        "verdict": result["verdict"],
        "warning_count": result["warning_count"],
        "flagged": warned,
    }
    supabase.table("scans").insert(record).execute()
    return scan_id

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@app.get("/api/v1/config", response_model=ConfigOut)
def get_config():
    return get_config_dict()

# ---------------------------------------------------------------------------
# Analyze text
# ---------------------------------------------------------------------------
@app.post("/api/v1/analyze-text", response_model=AnalyzeOut)
async def analyze_text(body: AnalyzeTextIn,
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

    if body.os not in ("iOS", "Android"):
        raise HTTPException(status_code=400, detail="os must be 'iOS' or 'Android'")

    result = await analyze(body.text)
    ocr_method = body.ocr_source or "text_input"
    scan_id = persist_scan("message", user_id, body.os, x_device_id,
                           body.text, result, result["verdict"] == "high_risk",
                           ocr_method=ocr_method)

    return AnalyzeOut(
        scan_id=scan_id, kind="message", **result,
        _meta=OcrMeta(ocr_method=ocr_method, ocr_confidence=1.0, ocr_fallback=False)
    )

# ---------------------------------------------------------------------------
# Sandbox image
# ---------------------------------------------------------------------------
@app.post("/api/v1/sandbox-image", response_model=AnalyzeOut)
async def sandbox_image(
    body: SandboxImageRequest,
    authorization: str = Header(None),
    x_device_id: Optional[str] = Header(None)
):
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

    logger.info(
        f"OCR | device={device_id} | method={ocr_output.method} | "
        f"chars={ocr_output.char_count} | conf={ocr_output.confidence:.2f}"
    )

    result = await analyze(ocr_output.text)
    scan_id = persist_scan(
        "screenshot", user_id, "iOS" if "iOS" in device_id else "Android",
        device_id, ocr_output.text, result, result["verdict"] == "high_risk",
        ocr_method=ocr_output.method, ocr_confidence=ocr_output.confidence
    )

    return AnalyzeOut(
        scan_id=scan_id, kind="screenshot", **result,
        _meta=OcrMeta(
            ocr_method=ocr_output.method,
            ocr_confidence=round(ocr_output.confidence, 2),
            ocr_fallback=ocr_output.fallback_used
        )
    )

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@app.post("/api/v1/report", response_model=ReportOut)
async def report(body: ReportIn,
                 authorization: str = Header(None),
                 x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)

    if body.report_type not in ("upi", "phone", "link", "other"):
        raise HTTPException(status_code=400, detail="Invalid report_type")
    if body.channel not in ("whatsapp", "sms", "phone_call", "email"):
        raise HTTPException(status_code=400, detail="Invalid channel")
    if body.os not in ("iOS", "Android"):
        raise HTTPException(status_code=400, detail="os must be 'iOS' or 'Android'")

    record = {
        "report_type": body.report_type,
        "value": body.value,
        "channel": body.channel,
        "description": body.description,
        "os": body.os,
        "user_id": user_id,
    }
    if x_device_id:
        record["device_id"] = x_device_id

    result = supabase.table("reports").insert(record).execute()
    report_id = result.data[0]["id"]
    return ReportOut(ok=True, report_id=report_id)

# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
@app.get("/api/v1/history", response_model=HistoryOut)
def get_history(authorization: str = Header(None)):
    user_id = require_user(authorization)

    scans = supabase.table("scans") \
        .select("id,kind,verdict,input_text,created_at") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .limit(50) \
        .execute()

    reports = supabase.table("reports") \
        .select("id", count="exact") \
        .eq("user_id", user_id) \
        .execute()

    items = []
    msg_count = 0
    ss_count = 0
    for s in scans.data:
        if s["kind"] == "message":
            msg_count += 1
        elif s["kind"] == "screenshot":
            ss_count += 1
        preview = (s.get("input_text") or "")[:60]
        items.append(HistoryItem(
            scan_id=s["id"],
            kind=s["kind"],
            verdict=s["verdict"],
            preview=preview,
            created_at=s["created_at"],
        ))

    return HistoryOut(
        counts=HistoryCounts(
            messages=msg_count,
            screenshots=ss_count,
            reports=reports.count or 0,
        ),
        items=items,
    )

# ---------------------------------------------------------------------------
# Scan detail
# ---------------------------------------------------------------------------
@app.get("/api/v1/scan/{scan_id}")
def get_scan(scan_id: str,
             authorization: str = Header(None)):
    user_id = require_user(authorization)

    result = supabase.table("scans").select("*").eq("id", scan_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Scan not found")

    row = result.data
    if row.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not your scan")

    return row["result_json"]

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "version": "2.1.0"}

@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    body = await request.body()
    content_type = request.headers.get("content-type", "")
    if body:
        import json as j
        try:
            data = j.loads(body)
            logger.warning(f"422 on {request.url.path}: body_keys={list(data.keys())}, "
                         f"os={data.get('os', '?')}, "
                         f"b64_len={len(data.get('image_base64', '')) if 'image_base64' in data else 0}, "
                         f"b64_present={'image_base64' in data}, "
                         f"content_type={content_type}")
        except Exception:
            logger.warning(f"422 on {request.url.path}: invalid JSON body, content_type={content_type}")
    else:
        logger.warning(f"422 on {request.url.path}: empty body, content_type={content_type}")
    if hasattr(exc, "errors"):
        detail = exc.errors()
    else:
        detail = exc.detail if hasattr(exc, "detail") else str(exc)
    logger.warning(f"422 detail: {detail}")
    return JSONResponse(status_code=422, content={"detail": detail})
