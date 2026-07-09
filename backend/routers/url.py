import ipaddress
import logging
import time
from typing import Literal, Optional
from urllib.parse import urlparse as _urlparse
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from app.auth import require_user
from app.helpers import persist_scan
from schemas.scan_result import verdict_label as _verdict_label
from agents.agent4_blacklist import check as blacklist_check
from agents.agent15_ensemble import compute
from app.ml.model_loader import get_models
from utils.url import extract_domain
from app.analytics.posthog_client import get_posthog_client

router = APIRouter(tags=["url"])
logger = logging.getLogger("scamshield.url")

SHORTENER_DOMAINS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "rb.gy"}

class AnalyzeURLIn(BaseModel):
    url: str = Field(max_length=2048)
    os: Literal["iOS", "Android"]

@router.post("/api/v1/analyze-url")
@router.post("/api/v1/check-url")
async def analyze_url(request: Request,
                      body: AnalyzeURLIn,
                      authorization: str = Header(None),
                      x_device_id: Optional[str] = Header(None)):
    t0 = time.time()
    user_id = require_user(authorization)
    request.state.user_id = user_id
    request.state.platform = body.os
    endpoint = request.url.path
    request_id = getattr(request.state, "request_id", "")
    posthog = get_posthog_client()

    posthog.capture_event("scan_received", user_id, properties={"channel": "url"},
                          request_id=request_id, endpoint=endpoint, platform=body.os)
    url = body.url

    # ponytail: upi:// scheme belongs in QR/UPI pipeline, not URL ML (F-10)
    if url.lower().startswith("upi://"):
        return JSONResponse(
            status_code=422,
            content={"detail": "UPI deep-link detected. Use /api/v1/check-qr to analyze UPI payloads.",
                     "code": "USE_QR_ENDPOINT"}
        )

    try:
        from app.ml.agents.inference import agent14_score_text
        regex_result = agent14_score_text(url)

        parsed = _urlparse(url)
        host = parsed.hostname or ""
        raw_ip = None
        try:
            raw_ip = ipaddress.ip_address(host)
        except ValueError:
            pass

        non_http_schemes = {"file", "ftp", "javascript", "data", "vbscript"}
        scheme = (parsed.scheme or "").lower()
        if scheme in non_http_schemes:
            result = {"scam_score": 45, "verdict": "suspicious", "verdict_label": "Suspicious", "warning_count": 1,
                      "extracted_text": url, "findings": [{"type": "scheme", "severity": "medium",
                      "title": "Non-HTTP URL scheme", "detail": f"URL uses '{scheme}' scheme which is unusual in messaging"}],
                      "flagged_urls": [url]}
            try:
                scan_id = await persist_scan("url", user_id, body.os, x_device_id, url, result, False)
            except Exception as e:
                logger.warning("Failed to persist scan (non-fatal): %s", e)
                scan_id = ""
            return {"scan_id": scan_id, "kind": "url", "flagged": False, **result, "_meta": None}

        if raw_ip is not None:
            if raw_ip.is_loopback or raw_ip.is_private:
                result = {"scam_score": 0, "verdict": "low_risk", "verdict_label": "Low Risk", "warning_count": 0,
                          "extracted_text": url, "findings": [{"type": "info", "severity": "info",
                          "title": "Local/private IP", "detail": f"{host} is a local/private address"}],
                          "flagged_urls": []}
                try:
                    scan_id = await persist_scan("url", user_id, body.os, x_device_id, url, result, False)
                except Exception as e:
                    logger.warning("Failed to persist scan (non-fatal): %s", e)
                    scan_id = ""
                return {"scan_id": scan_id, "kind": "url", "flagged": False, **result, "_meta": None}
            result = {"scam_score": 75, "verdict": "high_risk", "verdict_label": "High Risk", "warning_count": 1,
                      "extracted_text": url, "findings": [{"type": "ip_address", "severity": "high",
                      "title": "Direct IP address URL", "detail": f"{host} is a direct IP address"}],
                      "flagged_urls": [url]}
            try:
                scan_id = await persist_scan("url", user_id, body.os, x_device_id, url, result, True)
            except Exception as e:
                logger.warning("Failed to persist scan (non-fatal): %s", e)
                scan_id = ""
            return {"scan_id": scan_id, "kind": "url", "flagged": True, **result, "_meta": None}

        posthog.capture_event("analysis_started", user_id, properties={"channel": "url"},
                              request_id=request_id, endpoint=endpoint, platform=body.os)

        bl_models = get_models().get("agent4")
        if bl_models:
            bl_result = blacklist_check(url, bl_models)
        else:
            from app.ml.agents.inference import agent4_check_blacklist
            bl_hit, bl_domain = agent4_check_blacklist(url)
            bl_result = {"blacklist_hit": bl_hit, "blacklist_domain": bl_domain}

        url_prob = -1.0
        if not bl_result["blacklist_hit"]:
            from app.ml.agents.inference import agent3_predict_url
            url_prob = agent3_predict_url(url)

        domain = extract_domain(url)
        brand_flag = False
        matched_brand = None
        from app.ml.agents.inference import agent8_check_brand
        if domain:
            brand_flag, matched_brand, _ = agent8_check_brand(domain)

        from app.ml.url_features import extract_url_signals, compute_url_risk_boost
        url_signals = extract_url_signals(url)
        url_risk_boost = compute_url_risk_boost([url_signals])
        if url_signals.get("is_official_brand_domain"):
            brand_flag = False
            matched_brand = None
        elif not brand_flag:
            full_host = _urlparse(url).netloc.lower()
            bflag, bmatch, _ = agent8_check_brand(full_host)
            if bflag:
                brand_flag = True
                matched_brand = bmatch

        signals = {
            "text_prob": -1,
            "url_prob": url_prob if url_prob >= 0 else -1,
            "blacklist_hit": bl_result["blacklist_hit"],
            "brand_flag": brand_flag,
            "upi_rule_score": 0,
            "upi_xgb_prob": -1,
            "deepfake_prob": -1, "malware_prob": -1, "call_fraud_prob": -1,
            "regex_score": regex_result["score"],
            "regex_high": regex_result["severity"] == "HIGH",
            "regex_triggered": regex_result.get("triggered", []),
            "regex_safe": regex_result.get("regex_safe", False),
            "url_risk_boost": url_risk_boost,
        }
        result = compute(signals, scan_type="url")
        score = result["scam_score"]
        verdict = result["verdict"]
        ml_debug = {
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
                             "detail": f"Domain resembles {matched_brand}"})
        if url_prob >= 0:
            findings.append({"type": "ml_ensemble", "severity": "info", "title": "ML scores",
                             "detail": str(ml_debug)})
        warning_count = sum(1 for f in findings if f["severity"] in ("high", "medium"))

        domain_lower = domain.lower() if domain else ""
        if domain_lower in SHORTENER_DOMAINS:
            score = min(100, score + 10)
            findings.append({"type": "shortener", "severity": "medium", "title": "URL shortener",
                             "detail": f"{domain_lower} is a known URL shortener"})
        warning_count = sum(1 for f in findings if f["severity"] in ("high", "medium"))

        flagged = verdict == "high_risk" or (score >= 60 and brand_flag)
        result = {
            "scam_score": min(100, score),
            "verdict": verdict, "verdict_label": _verdict_label(verdict),
            "warning_count": warning_count,
            "extracted_text": url,
            "findings": findings,
            "flagged_urls": [url],
        }
        try:
            scan_id = await persist_scan("url", user_id, body.os, x_device_id, url, result, flagged)
        except Exception as e:
            logger.warning("Failed to persist scan (non-fatal): %s", e)
            scan_id = ""

        elapsed = int(round((time.time() - t0) * 1000))
        posthog.capture_scan_event(
            event="analysis_completed", user_id=user_id,
            channel="url", verdict=verdict, score=score,
            latency_ms=elapsed, request_id=request_id, endpoint=endpoint, platform=body.os,
            agents_used=["agent3", "agent4", "agent8", "agent14", "agent15"],
            extra_properties={"top_signal": result.get("top_signal", ""), "input_type": "url"},
        )

        return {"scan_id": scan_id, "kind": "url", "flagged": flagged, **result, "_meta": None}
    except Exception as exc:
        elapsed = int(round((time.time() - t0) * 1000))
        posthog.capture_scan_event(
            event="analysis_failed", user_id=user_id,
            channel="url", verdict="error", score=0,
            latency_ms=elapsed, request_id=request_id, endpoint=endpoint, platform=body.os,
            error_type=type(exc).__name__, error_message=str(exc),
            extra_properties={"input_type": "url"},
        )
        raise
