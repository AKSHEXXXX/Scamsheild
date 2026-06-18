import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from app.models import AnalyzeOut
from app.database import supabase
from app.auth import require_user, enforce_credit_cap
from app.analyzer import analyze
from app.helpers import get_config_dict, persist_scan

router = APIRouter(tags=["text"])
logger = logging.getLogger("scamshield.text")

class AnalyzeTextIn(BaseModel):
    text: str
    os: str
    ocr_source: Optional[str] = "text_input"

@router.post("/api/v1/analyze-text", response_model=AnalyzeOut)
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
    scan_id = persist_scan("message", user_id, body.os, x_device_id,
                           body.text, result, result["verdict"] == "high_risk")
    return AnalyzeOut(
        scan_id=scan_id, kind="message", **result,
        _meta=None
    )
