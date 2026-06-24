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
        "risk_score": result.get("scam_score", result.get("risk_score", 0)),
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
    _mongo_save_scan(scan_id, user_id, body_os, device_id, kind, input_text, result, warned)
    return scan_id


def _mongo_save_scan(scan_id, user_id, body_os, device_id, kind, input_text, result, warned):
    try:
        from app.data_intel.mongo_ops import save_scan as m_save
        verdict = result.get("verdict", "unknown")
        score = result.get("scam_score", result.get("risk_score", 0))
        wc = result.get("warning_count", 0)
        m_save(
            scan_id=scan_id, user_id=user_id,
            channel=kind, score=score, verdict=verdict,
            result=result, flagged=warned, warning_count=wc,
            input_preview=input_text, device_id=device_id, os=body_os,
        )
    except Exception:
        pass
