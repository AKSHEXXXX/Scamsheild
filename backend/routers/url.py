import logging
from typing import Optional
from fastapi import APIRouter, Header
from pydantic import BaseModel
from app.auth import require_user
from app.helpers import persist_scan
from agents.agent4_blacklist import check as blacklist_check
from agents.agent15_ensemble import compute_ensemble_verdict
from app.ml.model_loader import get_models
from utils.url import extract_domain

router = APIRouter(tags=["url"])
logger = logging.getLogger("scamshield.url")

class AnalyzeURLIn(BaseModel):
    url: str
    os: str

@router.post("/api/v1/analyze-url")
async def analyze_url(body: AnalyzeURLIn,
                      authorization: str = Header(None),
                      x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)
    url = body.url

    from app.ml.agents.inference import agent14_score_text
    regex_result = agent14_score_text(url)

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

    score, verdict, ml_debug = compute_ensemble_verdict(
        ml_url_prob=url_prob if url_prob >= 0 else -1.0,
        rule_score=regex_result["score"],
        has_blacklisted_domain=bl_result["blacklist_hit"],
        brand_flag=brand_flag,
        regex_score=regex_result["score"],
        regex_high=regex_result["severity"] == "HIGH",
        scan_type="url",
    )

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

    result = {
        "scam_score": min(100, score),
        "verdict": verdict,
        "warning_count": warning_count,
        "extracted_text": url,
        "findings": findings,
        "flagged_urls": [{"url": url, "final_url": url, "reputation": "blacklisted" if bl_result["blacklist_hit"] else "unknown"}],
    }
    try:
        scan_id = persist_scan("url", user_id, body.os, x_device_id, url, result, verdict == "high_risk")
    except Exception as e:
        logger.warning("Failed to persist scan (non-fatal): %s", e)
        scan_id = ""
    return {"scan_id": scan_id, "kind": "url", **result, "_meta": None}
