import re
import ipaddress
from urllib.parse import urlparse
import tldextract

SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "shorturl.at", "rb.gy", "cutt.ly", "short.link", "tiny.cc", "tr.im", "v.gd", "click.ru"}
SUSPICIOUS_TLDS = {".xyz", ".info", ".cc", ".tk", ".top", ".pw", ".loan", ".click", ".work", ".bid", ".men", ".date", ".racing", ".win", ".download", ".review", ".stream", ".science", ".party", ".asia"}
BRAND_TOKENS = ["hdfc", "sbi", "paypal", "amazon", "google", "facebook", "fedex", "dhl", "income", "aadhaar", "upi", "npci", "icici", "axis", "kotak", "yesbank", "flipkart", "phonepe", "paytm", "whatsapp", "telegram", "netflix", "gpay", "amazonpay", "visa", "mastercard"]
TRUSTED_DOMAINS = {
    "hdfcbank.com", "onlinesbi.com", "sbicard.com", "paypal.com", "paypal.me",
    "amazon.in", "amazon.com", "flipkart.com", "flipkart.in", "paytm.com",
    "phonepe.com", "gpay.com", "netflix.com", "google.com", "facebook.com",
    "whatsapp.com", "instagram.com", "icicibank.com", "axisbank.com",
    "kotak.com", "yesbank.in", "npci.org.in", "upi.org.in",
    "sbi.co.in", "uidai.gov.in", "incometax.gov.in", "indiapost.gov.in",
    "nsdl.co.in", "cdslindia.com", "sebi.gov.in", "rbi.org.in",
    "epfindia.gov.in", "nseindia.com", "bseindia.com", "licindia.in",
}


PRIVATE_PREFIXES = ("127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.",
                    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
                    "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.")

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}


def _is_private_host(host: str) -> bool:
    lower = host.lower().strip("[]")
    if lower in LOOPBACK_HOSTS:
        return True
    if any(lower.startswith(p) for p in PRIVATE_PREFIXES):
        return True
    try:
        ip = ipaddress.ip_address(lower)
        return ip.is_private or ip.is_loopback
    except ValueError:
        return False


def _get_domain(url: str) -> str:
    try:
        ext = tldextract.extract(url)
        return f"{ext.domain}.{ext.suffix}".lower() if ext.domain and ext.suffix else ""
    except Exception:
        return ""


def _get_tld(domain: str) -> str:
    parts = domain.split(".")
    if len(parts) >= 2:
        return "." + parts[-1].lower()
    return ""


def extract_url_signals(url: str) -> dict:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower() if parsed.hostname else ""
    domain = _get_domain(url)
    tld = _get_tld(domain)
    lower_domain = domain.lower()
    netloc = parsed.netloc.lower()

    is_dangerous_scheme = scheme in ("file", "ftp")
    is_loopback_or_private = _is_private_host(host) if host else False
    has_embedded_creds = "@" in netloc and "@" not in host

    return {
        "is_shortened": domain in SHORTENERS,
        "has_suspicious_tld": tld in SUSPICIOUS_TLDS,
        "has_brand_token": any(b in lower_domain for b in BRAND_TOKENS),
        "is_official_brand_domain": domain in TRUSTED_DOMAINS,
        "keyword_stuffed": lower_domain.count("-") >= 2,
        "is_dangerous_scheme": is_dangerous_scheme,
        "is_loopback_or_private": is_loopback_or_private,
        "has_embedded_creds": has_embedded_creds,
    }


def compute_url_risk_boost(url_signals_list: list[dict]) -> int:
    boost = 0
    for sig in url_signals_list:
        if sig["is_official_brand_domain"]:
            boost = min(boost, -15)
        elif sig["has_embedded_creds"]:
            boost = max(boost, 90)
        elif sig["is_dangerous_scheme"] or sig["is_loopback_or_private"]:
            boost = max(boost, 85)
        elif sig["is_shortened"] and sig["has_brand_token"]:
            boost = max(boost, 45)
        elif sig["is_shortened"]:
            boost = max(boost, 40)
        elif sig["has_suspicious_tld"] and sig["has_brand_token"]:
            boost = max(boost, 35)
        elif sig["keyword_stuffed"] and sig["has_brand_token"]:
            boost = max(boost, 30)
        elif sig["keyword_stuffed"] or sig["has_suspicious_tld"]:
            boost = max(boost, 10)
    return boost
