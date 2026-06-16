import re
import httpx
import logging
from app.database import supabase
from app.analytics import text_risk_analysis
from app.config import settings

logger = logging.getLogger("scamshield.analyzer")

UPI_RE = re.compile(r"[\w.\-]+@[\w]+")
PHONE_RE = re.compile(r"(?:\+91|91|0)?[6-9]\d{9}")
URL_RE = re.compile(r"https?://[^\s\)\"\'\>\<\]]+")
TYPO_CON_RE = re.compile(r"\b[A-Za-z0-9]+\.con\b", re.IGNORECASE)
BRAND_IMPERSONATION_RE = re.compile(
    r"\b(amazon|google|paytm|phonepe|flipkart|microsoft|apple|netflix|sbi|hdfc|icici)"
    r"\s*(?:team|customer|support|care|help)\b", re.IGNORECASE)


def _try_ml_text(text: str) -> float:
    try:
        from app.ml.text_model import predict_text_scam
        return predict_text_scam(text)
    except Exception as e:
        logger.debug("ML text model unavailable: %s", e)
        return -1.0


def _try_ml_urls(urls: list[str], payload_text: str = "") -> tuple[float, float, float]:
    try:
        from app.ml.url_model import predict_url_risk, heuristic_url_score
        from app.ml.qr_model import predict_qr_url_risk
    except Exception:
        return -1.0, -1.0, -1.0

    url_probs = []
    qr_probs = []
    heuristic_probs = []
    for url in urls:
        clean = url.rstrip(".,;:!?")
        p = predict_url_risk(clean)
        if p >= 0:
            url_probs.append(p)
        q = predict_qr_url_risk(clean, payload_text)
        if q >= 0:
            qr_probs.append(q)
        heuristic_probs.append(heuristic_url_score(clean))

    max_url = max(url_probs) if url_probs else -1.0
    max_qr = max(qr_probs) if qr_probs else -1.0
    max_heuristic = max(heuristic_probs) if heuristic_probs else -1.0

    if max_url >= 0 and max_url < 0.05:
        max_url = max(max_url, max_heuristic)

    return max_url, max_qr, max_heuristic


def _compute_verdict(score: int, threshold: int) -> str:
    if score >= threshold:
        return "high_risk"
    elif score >= threshold // 2:
        return "suspicious"
    return "low_risk"


def _get_threshold() -> int:
    try:
        cfg = supabase.table("app_config").select("sensitivity_threshold").eq("id", 1).single().execute().data
        return cfg["sensitivity_threshold"]
    except Exception:
        return settings.SENSITIVITY_THRESHOLD


async def analyze(text: str) -> dict:
    findings = []
    flagged_urls = []
    low_text = text.lower()

    # UPI/VPA analysis
    upi_matches = UPI_RE.findall(text)
    upi_found = []
    for upi in upi_matches:
        if "@" in upi:
            bl = supabase.table("blacklisted_vpas").select("vpa_string").eq("vpa_string", upi).execute()
            if bl.data:
                upi_found.append(upi)

    if upi_found:
        for u in upi_found:
            findings.append({"type": "upi", "severity": "high", "title": "Blacklisted UPI ID detected",
                             "detail": f"UPI ID {u} is in the fraud database"})
    elif upi_matches:
        for u in upi_matches[:3]:
            findings.append({"type": "upi", "severity": "low", "title": "UPI ID found",
                             "detail": f"UPI ID {u} present — verify before sending money"})

    has_blacklisted_vpa = bool(upi_found)

    # Phone number analysis
    phone_matches = PHONE_RE.findall(text)
    phone_found = []
    for p in phone_matches:
        p_clean = p[-10:] if len(p) > 10 else p
        bl = supabase.table("blacklisted_numbers").select("phone_number").eq("phone_number", p_clean).execute()
        if bl.data:
            phone_found.append(p_clean)

    if phone_found:
        for p in phone_found:
            findings.append({"type": "phone", "severity": "high", "title": "Fraud number detected",
                             "detail": f"Phone {p} is linked to known scams"})

    has_blacklisted_phone = bool(phone_found)

    # Brand impersonation detection (typosquat .con domains)
    con_matches = TYPO_CON_RE.findall(text)
    if con_matches:
        for m in con_matches[:3]:
            findings.append({"type": "impersonation", "severity": "high",
                             "title": "Brand impersonation detected",
                             "detail": f"'{m}' mimics a legitimate domain — likely a scam"})

    # Brand name impersonation ("Google team", "Amazon customer support" etc.)
    brand_matches = BRAND_IMPERSONATION_RE.findall(text)
    if brand_matches:
        brands = set(m[0] for m in brand_matches)
        findings.append({"type": "impersonation", "severity": "medium",
                         "title": "Fake brand communication",
                         "detail": f"Impersonating: {', '.join(b.title() for b in brands)}"})

    impersonation_boost = 25 if con_matches else 0

    # Rule-based text risk analysis
    tscore, keywords = text_risk_analysis(text)
    if keywords:
        findings.append({"type": "pressure", "severity": "medium", "title": "Pressure tactics detected",
                         "detail": f"Keywords found: {', '.join(keywords[:5])}"})

    # Link analysis
    urls = URL_RE.findall(text)
    has_blacklisted_domain = False

    async with httpx.AsyncClient(follow_redirects=True, timeout=5) as client:
        for url in urls:
            url = url.rstrip(".,;:!?")
            try:
                r = await client.get(url)
                final = str(r.url)
                domain = httpx.URL(final).host
                bl = supabase.table("blacklisted_domains").select("reputation").eq("domain", domain).execute()
                rep = bl.data[0]["reputation"] if bl.data else "unknown"
                if rep == "malicious":
                    has_blacklisted_domain = True
            except Exception:
                final = url
                rep = "unreachable"
            flagged_urls.append({"url": url, "final_url": final, "reputation": rep})

    if flagged_urls:
        malicious = any(u["reputation"] == "malicious" for u in flagged_urls)
        if malicious:
            findings.append({"type": "link", "severity": "high", "title": "Malicious link detected",
                             "detail": f"Found {sum(1 for u in flagged_urls if u['reputation'] == 'malicious')} malicious link(s)"})
    else:
        findings.append({"type": "link", "severity": "none", "title": "No suspicious link found",
                         "detail": "No URLs detected in the message"})

    # ML model inference (best-effort, falls back to -1.0 if unavailable)
    ml_text_prob = _try_ml_text(text)
    ml_url_prob, ml_qr_prob, ml_heuristic_prob = _try_ml_urls(urls, text)

    ml_available = ml_text_prob >= 0 or ml_url_prob >= 0 or ml_qr_prob >= 0

    if ml_available:
        from app.ml.ensemble import compute_ensemble_verdict
        score, verdict, ml_debug = compute_ensemble_verdict(
            ml_url_prob=ml_url_prob,
            ml_qr_prob=ml_qr_prob,
            ml_text_prob=ml_text_prob,
            rule_score=tscore,
            has_blacklisted_domain=has_blacklisted_domain,
            has_blacklisted_vpa=has_blacklisted_vpa,
            has_blacklisted_phone=has_blacklisted_phone,
            impersonation_boost=impersonation_boost,
        )
        findings.append({
            "type": "ml_ensemble",
            "severity": "info",
            "title": "ML model scores",
            "detail": str(ml_debug),
        })
        logger.info("ML ensemble | text=%.4f url=%.4f qr=%.4f rule=%d → score=%d %s",
                     ml_text_prob, ml_url_prob, ml_qr_prob, tscore, score, verdict)
    else:
        domain_risk = 100 if has_blacklisted_domain else 0
        score = round(0.6 * tscore + 0.4 * domain_risk) + impersonation_boost
        threshold = _get_threshold()
        verdict = _compute_verdict(score, threshold)

    warning_count = sum(1 for f in findings if f["severity"] in ("high", "medium"))

    return {
        "risk_score": min(100, score),
        "verdict": verdict,
        "warning_count": warning_count,
        "extracted_text": text,
        "findings": findings,
        "flagged_urls": flagged_urls,
    }
