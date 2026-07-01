import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Header, HTTPException
from app.database import supabase
from app.auth import require_user
from app.helpers import get_config_dict
from app.models import ReportIn, ReportOut, HistoryOut, HistoryCounts, HistoryItem

router = APIRouter(tags=["meta"])
logger = logging.getLogger("scamshield.meta")

@router.get("/health")
@router.get("/api/v1/health")
def health():
    from app.ml.model_loader import get_models_loaded_count
    from app.database_ext import MongoDBClient, RedisClient
    return {
        "status": "ok",
        "version": "2.1.0",
        "models_loaded": get_models_loaded_count(),
        "mongodb_connected": MongoDBClient.is_connected(),
        "redis_connected": RedisClient.is_connected(),
    }

@router.get("/api/v1/config")
def get_config():
    try:
        cfg = get_config_dict()
    except Exception as e:
        logger.warning("get_config_dict failed (is migration applied?): %s", e)
        cfg = {"scan_credit_cap": 50, "ad_frequency": 10,
               "sensitivity_threshold": 70, "config_version": "1"}
    cfg["features"] = {
        "text_analysis": True,
        "url_analysis": True,
        "image_analysis": True,
        "qr_scanning": True,
    }
    cfg["model_version"] = "2.1.0"
    th = cfg.get("sensitivity_threshold", 70)
    cfg["score_thresholds"] = {
        "low_risk": th // 2 - 1,
        "suspicious": th - 1,
        "high_risk": th,
    }
    from app.ml.model_loader import get_agent_status
    statuses = get_agent_status()
    ready = sum(1 for v in statuses.values() if v.get("status") == "READY")
    beta = sum(1 for v in statuses.values() if v.get("status") == "BETA")
    not_ready = sum(1 for v in statuses.values() if v.get("status") == "NOT_READY")
    cfg["agents"] = {"total": 15, "ready": ready, "beta": beta, "not_ready": not_ready}
    return cfg

@router.get("/api/v1/agents")
def list_agents():
    from app.ml.model_loader import get_agent_status, get_agent_folder_status, get_reports, get_models_loaded_count
    statuses = get_agent_status()
    folder_status = get_agent_folder_status()
    reports = get_reports()
    agents_list = []
    seen_ids = set()
    for aid in sorted(statuses.keys(), key=int):
        s = statuses[aid]
        rid = f"agent{aid}"
        rep = reports.get(rid, {})
        metric = rep.get("type") or rep.get("auc") or rep.get("total_domains") or rep.get("precision") or "N/A"
        health = s.get("health", {})
        status = "DISABLED" if health.get("disabled") else s.get("status", "UNKNOWN")
        agents_list.append({
            "id": int(aid),
            "name": s.get("name", ""),
            "status": status,
            "status_detail": s.get("status_detail", ""),
            "metric_value": metric if metric != "N/A" else s.get("status_detail", "N/A"),
            "health": health,
        })
        seen_ids.add(int(aid))
    for fname, finfo in sorted(folder_status.items()):
        if finfo["id"] not in seen_ids:
            agents_list.append({
                "id": finfo["id"],
                "name": finfo["name"],
                "status": finfo["status"],
                "status_detail": finfo["status_detail"],
                "metric_value": finfo["status_detail"],
                "health": {},
            })
            seen_ids.add(finfo["id"])
    return {"agents": agents_list, "total": len(agents_list), "models_loaded": get_models_loaded_count()}

@router.get("/api/model-accuracy")
def model_accuracy():
    from app.ml.model_loader import get_reports, get_models_loaded_count
    reports = get_reports()
    agents_list = [
        {"id": 1,  "name": "Text Scam Classifier (TF-IDF + LogReg)",    "metric": "AUC",        "value": reports.get("agent1", {}).get("auc", "N/A")},
        {"id": 2,  "name": "Text Scam Classifier (DistilBERT FP16)",     "metric": "AUC",        "value": reports.get("agent2", {}).get("auc", "skipped — model not loaded")},
        {"id": 3,  "name": "URL Phishing Classifier (XGBoost)",          "metric": "AUC",        "value": reports.get("agent3", {}).get("auc", "N/A")},
        {"id": 4,  "name": "URL Blacklist Checker",                      "metric": "Coverage",   "value": f"{reports.get('agent4', {}).get('total_domains', 0)} domains"},
        {"id": 5,  "name": "QR Threat Classifier (XGBoost)",             "metric": "AUC",        "value": reports.get("agent5", {}).get("auc", "N/A")},
        {"id": 6,  "name": "UPI Heuristic Rule Engine",                  "metric": "Type",       "value": "Rule-based: 100% deterministic"},
        {"id": 7,  "name": "UPI Meta Classifier (XGBoost)",              "metric": "AUC",        "value": reports.get("agent7", {}).get("auc", "N/A")},
        {"id": 8,  "name": "Brand Guard v1 (Edit-Distance)",             "metric": "Precision",  "value": reports.get("agent8", {}).get("precision", "see report")},
        {"id": 9,  "name": "Brand Guard v2 (Siamese BiLSTM)",            "metric": "AUC",        "value": reports.get("agent9", {}).get("auc", "skipped — model not loaded")},
        {"id": 10, "name": "Deepfake / AI Image Detector (DeiT)",        "metric": "AUC",        "value": reports.get("agent10", {}).get("auc", "skipped — model not loaded")},
        {"id": 11, "name": "Malware File Analyzer (Random Forest)",      "metric": "AUC",        "value": reports.get("agent11", {}).get("auc", "N/A")},
        {"id": 12, "name": "Whisper ASR (India/Gulf)",                   "metric": "WER",        "value": reports.get("agent12", {}).get("wer", "skipped — model not loaded")},
        {"id": 13, "name": "Call Transcript Fraud Detector (DistilBERT)","metric": "AUC",        "value": reports.get("agent13", {}).get("auc", "skipped — model not loaded")},
        {"id": 14, "name": "Regex Rule Engine",                          "metric": "Type",       "value": "Rule-based: 36 rules, 100% deterministic"},
        {"id": 15, "name": "Ensemble Scorer & Overrides",                "metric": "Type",       "value": "Calibrated weight tables + hard overrides"},
    ]
    return {
        "agents": agents_list,
        "models_loaded": get_models_loaded_count(),
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
    }

def persist_report(record: dict) -> str:
    result = supabase.table("reports").insert(record).execute()
    report_id = result.data[0]["id"]
    _mongo_save_report(report_id, record)
    return report_id


def _mongo_save_report(report_id: str, record: dict):
    try:
        from app.data_intel.mongo_ops import save_report as m_save
        m_save(
            report_id=report_id,
            user_id=record.get("user_id", ""),
            report_type=record.get("report_type", ""),
            value=record.get("value", ""),
            channel=record.get("channel", ""),
            description=record.get("description"),
            os=record.get("os", "unknown"),
            device_id=record.get("device_id", "unknown"),
        )
    except Exception:
        pass

@router.post("/api/v1/report")
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
        "device_id": x_device_id or "unknown",
    }
    try:
        report_id = persist_report(record)
        return ReportOut(ok=True, report_id=report_id)
    except Exception as e:
        logger.warning("Failed to insert report (RLS or migration?): %s", e)
        raise HTTPException(status_code=500, detail="Failed to submit report")

def _mongo_get_history(user_id: str) -> tuple[list[dict], int, int]:
    from app.data_intel.mongo_ops import MongoDBClient
    db = MongoDBClient.db()
    if db is None:
        return [], 0, 0
    try:
        cursor = db.scans.find(
            {"user_id": user_id},
            {"scan_id": 1, "channel": 1, "verdict": 1, "input_preview": 1, "created_at": 1},
        ).sort("created_at", -1).limit(50)
        items = []
        msg_count = 0
        ss_count = 0
        for doc in cursor:
            kind = doc.get("channel", "unknown")
            if kind in ("sms", "whatsapp", "email", "text", "message"):
                msg_count += 1
            elif kind in ("image", "screenshot"):
                ss_count += 1
            preview = (doc.get("input_preview") or "")[:60]
            created = doc.get("created_at")
            items.append(HistoryItem(
                scan_id=doc["scan_id"],
                kind=kind,
                verdict=doc.get("verdict", "unknown"),
                preview=preview,
                created_at=str(created) if created else "",
            ))
        return items, msg_count, ss_count
    except Exception:
        return [], 0, 0


@router.get("/api/v1/history", response_model=HistoryOut)
def get_history(authorization: str = Header(None)):
    user_id = require_user(authorization)
    mongo_items, msg_count, ss_count = _mongo_get_history(user_id)
    reports = supabase.table("reports") \
        .select("id", count="exact") \
        .eq("user_id", user_id) \
        .execute()
    return HistoryOut(
        counts=HistoryCounts(messages=msg_count, screenshots=ss_count, reports=reports.count or 0),
        items=mongo_items,
    )


def _mongo_get_scan(scan_id: str, user_id: str) -> Optional[dict]:
    from app.data_intel.mongo_ops import MongoDBClient
    db = MongoDBClient.db()
    if db is None:
        return None
    try:
        doc = db.scans.find_one({"scan_id": scan_id, "user_id": user_id})
        if doc:
            return doc.get("result") or doc.get("result_json", {})
    except Exception:
        pass
    return None


@router.get("/api/v1/scan/{scan_id}")
def get_scan(scan_id: str, authorization: str = Header(None)):
    user_id = require_user(authorization)
    mongo_result = _mongo_get_scan(scan_id, user_id)
    if mongo_result:
        return mongo_result
    result = supabase.table("scans").select("*").eq("id", scan_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Scan not found")
    row = result.data
    if row.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not your scan")
    return row["result_json"]
