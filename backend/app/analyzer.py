import re
import httpx
from app.database import supabase
from app.analytics import text_risk_analysis

UPI_RE = re.compile(r"[\w.\-]+@[\w]+")
PHONE_RE = re.compile(r"(?:\+91|91|0)?[6-9]\d{9}")
URL_RE = re.compile(r"https?://[^\s\)\"\'\>\<\]]+")
TYPO_CON_RE = re.compile(r"\b[A-Za-z0-9]+\.con\b", re.IGNORECASE)
BRAND_IMPERSONATION_RE = re.compile(
    r"\b(amazon|google|paytm|phonepe|flipkart|microsoft|apple|netflix|sbi|hdfc|icici)"
    r"\s*(?:team|customer|support|care|help)\b", re.IGNORECASE)

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

    # Pressure language analysis
    tscore, keywords = text_risk_analysis(text)
    if keywords:
        findings.append({"type": "pressure", "severity": "medium", "title": "Pressure tactics detected",
                         "detail": f"Keywords found: {', '.join(keywords[:5])}"})

    # Link analysis
    urls = URL_RE.findall(text)
    async with httpx.AsyncClient(follow_redirects=True, timeout=5) as client:
        for url in urls:
            url = url.rstrip(".,;:!?")
            try:
                r = await client.get(url)
                final = str(r.url)
                domain = httpx.URL(final).host
                bl = supabase.table("blacklisted_domains").select("reputation").eq("domain", domain).execute()
                rep = bl.data[0]["reputation"] if bl.data else "unknown"
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

    # Scoring
    domain_risk = 100 if any(u["reputation"] == "malicious" for u in flagged_urls) else 0
    impersonation_boost = 25 if any(
        f["type"] == "impersonation" and f["severity"] == "high" for f in findings
    ) else 0
    score = round(0.6 * tscore + 0.4 * domain_risk) + impersonation_boost
    warning_count = sum(1 for f in findings if f["severity"] in ("high", "medium"))

    cfg = supabase.table("app_config").select("sensitivity_threshold").eq("id", 1).single().execute().data
    threshold = cfg["sensitivity_threshold"]
    if score >= threshold:
        verdict = "high_risk"
    elif score >= threshold // 2:
        verdict = "suspicious"
    else:
        verdict = "low_risk"

    return {
        "risk_score": min(100, score),
        "verdict": verdict,
        "warning_count": warning_count,
        "extracted_text": text,
        "findings": findings,
        "flagged_urls": flagged_urls,
    }