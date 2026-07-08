import logging
import time
import uuid
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Request
from app.models import ScanRequest, UnifiedScanResult, AgentResultItem
from app.auth import require_user
from app.ml.model_loader import get_agent_status
from app.logging_utils import log_event, hash_id
from app.analytics.posthog_client import get_posthog_client

router = APIRouter(tags=["scan"])
logger = logging.getLogger("scamshield.scan")

def _agent_result(aid: int, name: str, score: float, verdict: str = "SAFE", signals: list = None) -> AgentResultItem:
    flat = []
    if signals:
        for s in signals:
            if isinstance(s, dict):
                flat.append(s.get("name", s.get("rule", str(s))))
            else:
                flat.append(str(s))
    return AgentResultItem(agent_id=aid, name=name, score=score, verdict=verdict, signals=flat)

@router.post("/api/v1/scan")
async def unified_scan(request: Request,
                       body: ScanRequest,
                       authorization: str = Header(None),
                       x_device_id: Optional[str] = Header(None)):
    t0 = time.time()
    user_id = require_user(authorization)
    client_ip = request.client.host if request.client else ""
    channel = body.channel.lower()
    agent_results: list[AgentResultItem] = []
    statuses = get_agent_status()

    if channel in ("sms", "whatsapp", "email", "text"):
        if not body.text:
            raise HTTPException(status_code=400, detail="text required for channel=sms/whatsapp/email/text")
        try:
            from app.ml.agents.inference import agent1_predict_text, agent2_predict_text, agent14_score_text
            regex = agent14_score_text(body.text)
            agent_results.append(_agent_result(14, statuses.get("14", {}).get("name", "Regex"), float(regex.get("score", 0)),
                                               regex.get("severity", "SAFE"), regex.get("triggered", [])))
            tfidf = agent1_predict_text(body.text)
            if tfidf >= 0:
                agent_results.append(_agent_result(1, statuses.get("1", {}).get("name", "TF-IDF"), round(tfidf * 100, 1),
                                                   "SCAM" if tfidf > 0.7 else "SUSPICIOUS" if tfidf > 0.3 else "SAFE"))
            berts = agent2_predict_text(body.text)  # stub, returns -1
            if berts >= 0:
                agent_results.append(_agent_result(2, statuses.get("2", {}).get("name", "DistilBERT"), round(berts * 100, 1)))
            from agents.agent15_ensemble import compute
            signals = {
                "text_prob": tfidf if tfidf >= 0 else -1,
                "regex_score": regex.get("score", 0),
                "regex_high": regex.get("severity") == "HIGH",
                "regex_triggered": regex.get("triggered", []),
                "blacklist_hit": False, "brand_flag": False,
                "upi_rule_score": 0, "upi_xgb_prob": -1,
                "deepfake_prob": -1, "malware_prob": -1, "call_fraud_prob": -1,
            }
            ensemble = compute(signals, scan_type="text")
            agent_results.append(_agent_result(15, statuses.get("15", {}).get("name", "Ensemble"), float(ensemble["scam_score"]),
                                               ensemble["verdict"], [ensemble["top_signal"]]))
        except Exception as e:
            logger.warning("Text scan agent error: %s", e)
            agent_results.append(_agent_result(0, "Text Pipeline", 0, "ERROR", [f"Agent error: {str(e)}"]))

    elif channel in ("url", "link"):
        if not body.url:
            raise HTTPException(status_code=400, detail="url required for channel=url/link")
        try:
            from app.ml.agents.inference import agent3_predict_url, agent4_check_blacklist, agent8_check_brand
            blacklisted, domain = agent4_check_blacklist(body.url)
            if blacklisted:
                agent_results.append(_agent_result(4, statuses.get("4", {}).get("name", "Blacklist"), 100, "SCAM", [f"Domain blacklisted: {domain}"]))
            brand_flag, brand_name, _ = agent8_check_brand(body.url)
            if brand_flag:
                agent_results.append(_agent_result(8, statuses.get("8", {}).get("name", "Brand Guard"), 80, "SUSPICIOUS", [f"Impersonates: {brand_name}"]))
            url_prob = agent3_predict_url(body.url)
            if url_prob >= 0:
                agent_results.append(_agent_result(3, statuses.get("3", {}).get("name", "URL XGBoost"), round(url_prob * 100, 1),
                                                   "SCAM" if url_prob > 0.7 else "SUSPICIOUS" if url_prob > 0.3 else "SAFE"))
            from agents.agent15_ensemble import compute
            signals = {
                "url_prob": url_prob if url_prob >= 0 else -1,
                "blacklist_hit": blacklisted,
                "brand_flag": brand_flag,
                "regex_score": 0, "regex_high": False, "regex_triggered": [],
                "text_prob": -1, "upi_rule_score": 0, "upi_xgb_prob": -1,
                "deepfake_prob": -1, "malware_prob": -1, "call_fraud_prob": -1,
            }
            ensemble = compute(signals, scan_type="url")
            agent_results.append(_agent_result(15, statuses.get("15", {}).get("name", "Ensemble"), float(ensemble["scam_score"]),
                                               ensemble["verdict"], [ensemble["top_signal"]]))
        except Exception as e:
            logger.warning("URL scan agent error: %s", e)
            agent_results.append(_agent_result(0, "URL Pipeline", 0, "ERROR", [f"Agent error: {str(e)}"]))

    elif channel in ("qr", "qrcode"):
        if not body.text:
            raise HTTPException(status_code=400, detail="text/url required for channel=qr")
        from app.ml.agents.inference import agent5_predict_qr_payload, agent1_predict_text, agent14_score_text, agent4_check_blacklist, agent8_check_brand
        qr_prob = agent5_predict_qr_payload(body.text)
        if qr_prob >= 0:
            agent_results.append(_agent_result(5, statuses.get("5", {}).get("name", "QR XGBoost"), round(qr_prob * 100, 1),
                                               "SCAM" if qr_prob > 0.7 else "SUSPICIOUS" if qr_prob > 0.3 else "SAFE"))
        tfidf = agent1_predict_text(body.text)
        if tfidf >= 0:
            agent_results.append(_agent_result(1, statuses.get("1", {}).get("name", "TF-IDF"), round(tfidf * 100, 1)))
        regex = agent14_score_text(body.text)
        agent_results.append(_agent_result(14, statuses.get("14", {}).get("name", "Regex"), float(regex["score"]), regex["severity"], regex["triggered"]))
        from agents.agent15_ensemble import compute
        signals = {
            "url_prob": qr_prob if qr_prob >= 0 else -1,
            "text_prob": tfidf if tfidf >= 0 else -1,
            "regex_score": regex["score"], "regex_high": regex["severity"] == "HIGH",
            "regex_triggered": regex.get("triggered", []),
            "blacklist_hit": False, "brand_flag": False,
            "upi_rule_score": 0, "upi_xgb_prob": -1,
            "deepfake_prob": -1, "malware_prob": -1, "call_fraud_prob": -1,
        }
        ensemble = compute(signals, scan_type="qr")
        agent_results.append(_agent_result(15, statuses.get("15", {}).get("name", "Ensemble"), float(ensemble["scam_score"]),
                                           ensemble["verdict"], [ensemble["top_signal"]]))

    elif channel in ("upi", "payment"):
        if not body.text:
            raise HTTPException(status_code=400, detail="text required for channel=upi")
        txn = {"amount": 0, "note": body.text, "vpa": body.url or "", "channel": "scan"}
        try:
            from app.ml.agents.inference import agent6_scan_upi, agent7_predict_upi, agent1_predict_text, agent14_score_text
            upi_rule = agent6_scan_upi(txn)
            agent_results.append(_agent_result(6, statuses.get("6", {}).get("name", "UPI Heuristic"), float(upi_rule.get("score", 0)),
                                               upi_rule.get("severity", "SAFE"), upi_rule.get("triggered_rules", [])))
            upi_xgb = agent7_predict_upi(txn) if upi_rule.get("severity") != "HIGH" else -1
            if upi_xgb >= 0:
                agent_results.append(_agent_result(7, statuses.get("7", {}).get("name", "UPI XGBoost"), round(upi_xgb * 100, 1)))
            tfidf = agent1_predict_text(body.text)
            if tfidf >= 0:
                agent_results.append(_agent_result(1, statuses.get("1", {}).get("name", "TF-IDF"), round(tfidf * 100, 1)))
            regex = agent14_score_text(body.text)
            agent_results.append(_agent_result(14, statuses.get("14", {}).get("name", "Regex"), float(regex.get("score", 0)),
                                               regex.get("severity", "SAFE"), regex.get("triggered", [])))
            from agents.agent15_ensemble import compute
            signals = {
                "upi_rule_score": upi_rule.get("score", 0),
                "upi_xgb_prob": upi_xgb if upi_xgb >= 0 else -1,
                "text_prob": tfidf if tfidf >= 0 else -1,
                "regex_score": regex.get("score", 0), "regex_high": regex.get("severity") == "HIGH",
                "regex_triggered": regex.get("triggered", []),
                "blacklist_hit": False, "brand_flag": False,
                "url_prob": -1, "deepfake_prob": -1, "malware_prob": -1, "call_fraud_prob": -1,
            }
            ensemble = compute(signals, scan_type="upi")
            agent_results.append(_agent_result(15, statuses.get("15", {}).get("name", "Ensemble"), float(ensemble["scam_score"]),
                                               ensemble["verdict"], [ensemble["top_signal"]]))
        except Exception as e:
            logger.warning("UPI scan agent error: %s", e)
            agent_results.append(_agent_result(0, "UPI Pipeline", 0, "ERROR", [f"Agent error: {str(e)}"]))

    elif channel in ("image", "screenshot"):
        raise HTTPException(status_code=501, detail="Image scan via unified endpoint coming soon — use POST /api/v1/sandbox-image")

    elif channel in ("file", "document"):
        raise HTTPException(status_code=501, detail="File scan via unified endpoint coming soon — use POST /api/v1/sandbox-file")

    elif channel in ("audio", "voice"):
        raise HTTPException(status_code=501, detail="Audio scan not yet available — coming in Sprint 3")

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported channel: {channel}")

    elapsed = time.time() - t0
    ensemble_result = [r for r in agent_results if r.agent_id == 15]
    if ensemble_result:
        score = int(round(ensemble_result[0].score))
        if score >= 70:
            final = "SCAM"
        elif score >= 35:
            final = "SUSPICIOUS"
        else:
            final = "SAFE"
    else:
        score = max(r.score for r in agent_results) if agent_results else 0
        if score >= 70:
            final = "SCAM"
        elif score >= 35:
            final = "SUSPICIOUS"
        else:
            final = "SAFE"

    top = max(agent_results, key=lambda r: r.score) if agent_results else None
    top_reason = f"Agent {top.agent_id}: {top.name} — score {top.score}" if top else "No results"

    from app.data_intel.mongo_ops import save_scan, write_analytics_event
    scan_id = str(uuid.uuid4())
    flagged_agents = [r.agent_id for r in agent_results if r.verdict in ("SCAM", "HIGH")]
    save_scan(
        scan_id=scan_id, user_id=user_id,
        channel=channel, score=score, verdict=final,
        result={"final_verdict": final, "score": score, "agent_results": [r.model_dump() for r in agent_results]},
        flagged=final == "SCAM", warning_count=len(flagged_agents),
        input_preview=body.text or body.url or "", device_id=x_device_id or "", os=body.os or "",
        posture=body.posture, ip=client_ip,
    )
    write_analytics_event("scan_completed", scan_id, user_id, channel, final, score, flagged_agents)

    log_event("scan_completed", level="INFO", scan_id=scan_id, user_id=user_id,
              channel=channel, verdict=final, score=score, agent_ids=flagged_agents,
              ip=client_ip, message=body.text or body.url)

    posthog = get_posthog_client()
    error_agents = [r for r in agent_results if r.verdict == "ERROR"]
    posthog.capture_scan_event(
        event="analysis_completed",
        user_id=user_id,
        channel=channel,
        verdict=final,
        score=score,
        latency_ms=int(round(elapsed * 1000)),
        request_id=getattr(request.state, "request_id", ""),
        endpoint=request.url.path,
        platform=body.os or "unknown",
        agents_used=[str(r.agent_id) for r in agent_results if r.verdict not in ("ERROR",)],
    )
    if error_agents:
        posthog.capture_scan_event(
            event="analysis_failed",
            user_id=user_id,
            channel=channel,
            verdict="error",
            score=score,
            latency_ms=int(round(elapsed * 1000)),
            request_id=getattr(request.state, "request_id", ""),
            endpoint=request.url.path,
            platform=body.os or "unknown",
            error_type="agent_error",
            error_message=f"{len(error_agents)} agent(s) returned ERROR",
        )

    return UnifiedScanResult(
        final_verdict=final,
        score=score,
        label=final.lower(),
        top_reason=top_reason,
        agent_results=agent_results,
        meta={"deployment_id": "6fd63ed4", "latency_ms": int(round(elapsed * 1000)), "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
    )
