import os
from datetime import datetime, timezone
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models import ScanIn, ConfigOut, ScanOut
from app.database import supabase
from app.auth import verify_jwt, enforce_credit_cap
from app.ocr import run_ocr
from app.analytics import text_risk_analysis
from app.sandbox import sandbox_urls
from app.scoring import compliance_score
from app.config import settings

app = FastAPI(title="ScamShield API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    user_id = verify_jwt(authorization)

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