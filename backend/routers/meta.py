from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Header, HTTPException
from app.database import supabase
from app.auth import require_user
from app.helpers import get_config_dict, persist_scan
from app.models import ConfigOut, ReportIn, ReportOut, HistoryOut, HistoryCounts, HistoryItem

router = APIRouter(tags=["meta"])

@router.get("/health")
def health():
    from app.ml.model_loader import get_models_loaded_count
    return {
        "status": "ok",
        "version": "2.1.0",
        "models_loaded": get_models_loaded_count(),
    }

@router.get("/api/v1/config", response_model=ConfigOut)
def get_config():
    cfg = get_config_dict()
    cfg["features"] = {
        "text_analysis": True,
        "url_analysis": True,
        "image_analysis": True,
        "qr_scanning": True,
    }
    cfg["model_version"] = "2.1.0"
    th = cfg["sensitivity_threshold"]
    cfg["score_thresholds"] = {
        "low_risk": th // 2 - 1,
        "suspicious": th - 1,
        "high_risk": th,
    }
    return cfg

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
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

@router.post("/api/v1/report", response_model=ReportOut)
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
    result = supabase.table("reports").insert(record).execute()
    report_id = result.data[0]["id"]
    return ReportOut(ok=True, report_id=report_id)

@router.get("/api/v1/history", response_model=HistoryOut)
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

@router.get("/api/v1/scan/{scan_id}")
def get_scan(scan_id: str, authorization: str = Header(None)):
    user_id = require_user(authorization)
    result = supabase.table("scans").select("*").eq("id", scan_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Scan not found")
    row = result.data
    if row.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not your scan")
    return row["result_json"]
