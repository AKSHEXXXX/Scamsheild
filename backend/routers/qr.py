import logging
from typing import Literal, Optional
from urllib.parse import urlparse, parse_qs
from fastapi import APIRouter, Header
from pydantic import BaseModel, Field
from app.auth import require_user
from app.helpers import persist_scan
from schemas.scan_result import verdict_label as _verdict_label
from agents.agent4_blacklist import check as blacklist_check
from app.ml.model_loader import get_models

router = APIRouter(tags=["qr"])
logger = logging.getLogger("scamshield.qr")

UPI_MERCHANT_ALLOWLIST = {"merchant.store@okaxis", "paytm@paytm", "googlepay@okaxis", "phonepe@ybl",
                          "amazon@pay", "flipkart@upi", "zomato@pay", "swiggy@upi",
                          "recharge@upi", "electricity@upi", "broadband@upi"}

class CheckQRIn(BaseModel):
    payload: str = Field(max_length=4096)
    os: Literal["iOS", "Android"]

@router.post("/api/v1/check-qr")
async def check_qr(body: CheckQRIn,
                   authorization: str = Header(None),
                   x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)
    from app.preprocessing.text_normalizer import normalize
    payload = body.payload

    stripped = payload.strip()
    if not stripped:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail={"error": "QR payload is empty", "code": "QR_EMPTY"})

    lower = stripped.lower()
    if any(lower.startswith(prefix) for prefix in ("javascript:", "data:", "vbscript:")):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail={"error": "QR payload contains a potentially dangerous URI scheme", "code": "QR_MALFORMED"})

    # Detect benign structured payloads (vCard, WiFi config) — default to low_risk
    payload_upper = payload.strip().upper()
    if payload_upper.startswith("BEGIN:VCARD") or payload_upper.startswith("WIFI:"):
        return {
            "scan_id": "", "kind": "qr", "flagged": False,
            "scam_score": 5, "verdict": "low_risk", "verdict_label": "Low Risk",
            "top_signal": "structured_benign_payload",
            "warning_count": 0, "extracted_text": payload[:60],
            "findings": [{"type": "info", "severity": "none",
                          "title": "Structured Payload",
                          "detail": "QR contains a structured configuration payload (vCard/WiFi)"}],
            "flagged_urls": [], "_meta": None,
        }

    from app.ml.agents.inference import agent5_predict_qr_payload, agent1_predict_text, agent8_check_brand, agent14_score_text, agent3_predict_url, agent6_scan_upi, agent7_predict_upi, agent4_check_blacklist

    qr_prob = agent5_predict_qr_payload(payload)

    bl_models = get_models().get("agent4")
    if bl_models:
        bl_result = blacklist_check(payload, bl_models)
    else:
        bl_hit, bl_domain = agent4_check_blacklist(payload)
        bl_result = {"blacklist_hit": bl_hit, "blacklist_domain": bl_domain}

    brand_flag, matched_brand, _ = agent8_check_brand(payload)

    text_prob = -1.0
    url_prob = -1.0
    upi_rule_score = 0
    upi_xgb_prob = -1.0
    regex_result = {"score": 0, "severity": "SAFE", "triggered": []}

    url_risk_boost = 0
    if payload.lower().startswith(("http://", "https://")):
        from app.ml.url_features import extract_url_signals, compute_url_risk_boost
        url_signals = extract_url_signals(payload)
        url_risk_boost = compute_url_risk_boost([url_signals])
        if url_signals.get("is_official_brand_domain"):
            brand_flag = False
            matched_brand = None
        url_prob = agent3_predict_url(payload) if not bl_result["blacklist_hit"] else -1.0
        regex_result = agent14_score_text(payload)
    elif payload.lower().startswith("upi://"):
        parsed = urlparse(payload)
        params = parse_qs(parsed.query)
        vpa = params.get("pa", [""])[0]
        merchant = params.get("pn", [""])[0]
        try:
            amt = float(params.get("am", ["0"])[0])
        except ValueError:
            amt = 0.0
        txn = {"amount": amt, "note": merchant or "", "vpa": vpa, "channel": "qr"}
        heuristic = agent6_scan_upi(txn)
        upi_rule_score = heuristic["score"]
        if vpa and vpa.lower() in UPI_MERCHANT_ALLOWLIST:
            upi_rule_score = min(upi_rule_score, 20)
        upi_xgb_prob = agent7_predict_upi(txn) if heuristic["severity"] != "HIGH" else -1.0
        regex_result = agent14_score_text(payload)
        text_prob = agent1_predict_text(f"{merchant} {vpa}")
        if not brand_flag:
            brand_flag, matched_brand, _ = agent8_check_brand(merchant)
        if not brand_flag and "@" in vpa:
            vpa_name = vpa.split("@")[0]
            brand_flag, matched_brand, _ = agent8_check_brand(vpa_name)
        high_risk_merchant_keywords = ["fake", "scam", "fraud", "verify", "kyc", "urgent", "won", "prize", "refund", "cashback"]
        for kw in high_risk_merchant_keywords:
            if kw in merchant.lower() or kw in vpa.lower():
                upi_rule_score = max(upi_rule_score, 70)
                break
    else:
        normalized = normalize(payload)
        text_prob = agent1_predict_text(normalized)
        regex_result = agent14_score_text(normalized)

    from agents.agent15_ensemble import compute
    signals = {
        "text_prob": text_prob if text_prob >= 0 else -1,
        "url_prob": url_prob if url_prob >= 0 else (qr_prob if qr_prob >= 0 else -1),
        "blacklist_hit": bl_result["blacklist_hit"],
        "brand_flag": brand_flag,
        "upi_rule_score": upi_rule_score,
        "upi_xgb_prob": upi_xgb_prob if upi_xgb_prob >= 0 else -1,
        "deepfake_prob": -1, "malware_prob": -1, "call_fraud_prob": -1,
        "regex_score": regex_result["score"],
        "regex_high": regex_result["severity"] == "HIGH",
        "regex_triggered": regex_result.get("triggered", []),
        "regex_safe": regex_result.get("regex_safe", False),
        "url_risk_boost": url_risk_boost,
    }
    ensemble = compute(signals, scan_type="qr")
    score = ensemble["scam_score"]
    verdict = ensemble["verdict"]
    top_signal = ensemble["top_signal"]
    ml_debug = {
        "ml_text_prob": round(text_prob, 4) if text_prob >= 0 else None,
        "ml_url_prob": round(url_prob, 4) if url_prob >= 0 else None,
        "rule_score_norm": round(regex_result["score"] / 100.0, 2),
        "blacklist_hit": bl_result["blacklist_hit"],
    }

    findings = []
    if bl_result["blacklist_hit"]:
        findings.append({"type": "blacklist", "severity": "high", "title": "Blacklisted domain",
                         "detail": f'{bl_result["blacklist_domain"]} is in fraud database'})
    if brand_flag:
        findings.append({"type": "brand", "severity": "medium", "title": "Brand impersonation",
                         "detail": f"Payload resembles {matched_brand}"})
    if ml_debug:
        findings.append({"type": "ml_ensemble", "severity": "info", "title": "ML scores",
                         "detail": str(ml_debug)})
    warning_count = sum(1 for f in findings if f["severity"] in ("high", "medium"))
    flagged = verdict == "high_risk" or (score >= 60 and brand_flag)
    result = {
        "scam_score": min(100, score),
        "verdict": verdict, "verdict_label": _verdict_label(verdict),
        "warning_count": warning_count,
        "extracted_text": payload,
        "findings": findings,
        "flagged_urls": [],
    }
    try:
        scan_id = await persist_scan("qr", user_id, body.os, x_device_id, payload, result, flagged)
    except Exception as e:
        logger.warning("Failed to persist scan (non-fatal): %s", e)
        scan_id = ""
    return {"scan_id": scan_id, "kind": "qr", "flagged": flagged,
            "top_signal": top_signal,
            **result, "_meta": None}
