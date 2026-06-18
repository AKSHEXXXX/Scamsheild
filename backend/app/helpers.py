import uuid
from typing import Optional
from functools import lru_cache
from fastapi import HTTPException

@lru_cache(maxsize=None)
def _get_service_client():
    from supabase import create_client
    from app.config import settings
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

def get_config_dict() -> dict:
    sb = _get_service_client()
    result = sb.table("app_config").select("*").eq("id", 1).single().execute()
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
                 ocr_method: Optional[str] = None, ocr_confidence: Optional[float] = None,
                 ocr_fallback: Optional[bool] = None):
    sb = _get_service_client()
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
    if ocr_method is not None:
        record["ocr_method"] = ocr_method
    if ocr_confidence is not None:
        record["ocr_confidence"] = ocr_confidence
    if ocr_fallback is not None:
        record["ocr_fallback"] = ocr_fallback
    sb.table("scans").insert(record).execute()
    return scan_id
