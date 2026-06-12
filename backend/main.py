import os
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.models import ScanIn, ConfigOut, ScanOut
from app.database import supabase
from app.auth import get_user_id, enforce_credit_cap
from app.ocr import run_ocr
from app.analytics import text_risk_analysis
from app.sandbox import sandbox_urls
from app.scoring import compliance_score
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scamshield")
app = FastAPI(title="ScamShield API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    logger.warning(f"422 detail: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

# ---------------------------------------------------------------------------
# 1.3 Config endpoint
# ---------------------------------------------------------------------------
@app.get("/api/v1/config", response_model=ConfigOut)
def get_config():
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

# ---------------------------------------------------------------------------
# 2.x Image sandbox endpoint
# ---------------------------------------------------------------------------
@app.post("/api/v1/sandbox-image", response_model=ScanOut)
async def sandbox_image(body: ScanIn, authorization: str = Header(None)):
    user_id = get_user_id(authorization)

    config = get_config()
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

    text = run_ocr(body.image_base64)
    text_score, keywords = text_risk_analysis(text)
    flagged = await sandbox_urls(text)
    score, verdict = compliance_score(text_score, flagged, config["sensitivity_threshold"])

    supabase.table("scans").insert({
        "user_id": user_id,
        "os": body.os,
        "risk_score": score,
        "verdict": verdict,
        "flagged": verdict == "high_risk",
    }).execute()

    return ScanOut(
        risk_score=score,
        verdict=verdict,
        extracted_text=text,
        matched_keywords=keywords,
        flagged_urls=flagged,
    )

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}