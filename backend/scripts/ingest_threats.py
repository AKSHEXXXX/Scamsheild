"""
Threat-intel ingestion script.

Pulls public threat feeds, normalises them, and upserts into the three
blacklist tables in Supabase.

Usage:
    python scripts/ingest_threats.py

Schedule nightly via GitHub Actions cron or Supabase pg_cron.
"""
import os
import sys
from datetime import datetime, timezone

import httpx
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("FATAL: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ---------------------------------------------------------------------------
# Feed sources (only use datasets whose terms permit this use)
# ---------------------------------------------------------------------------
FEEDS = {
    "domains": [
        # OpenPhish – phishing domains
        "https://openphish.com/feed.txt",
        # PhishTank – raw CSV of phishing URLs (use raw CSV endpoint)
        "https://data.phishtank.com/data/online-valid.csv",
    ],
    "phone_numbers": [
        # Example: national do-not-call / spam-number lists.
        # Replace with actual consented/authoritative sources.
    ],
    "vpas": [
        # Example: reported UPI IDs from CERT-In or NPCI feeds.
    ],
}

def fetch_text(url: str) -> str | None:
    try:
        r = httpx.get(url, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception as exc:
        print(f"WARN: failed to fetch {url}: {exc}")
        return None

def extract_domains(text: str) -> list[str]:
    """Extract unique domain names from plain-text URL lists."""
    domains = set()
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("http"):
            # If it's a full URL, extract host
            if line.startswith("http"):
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(line).hostname
                    if domain and "." in domain:
                        domains.add(domain.lower())
                except Exception:
                    pass
            continue
        if "." in line:
            domains.add(line.lower())
    return list(domains)

def upsert_domains(domains: list[str], source: str):
    if not domains:
        return
    records = [{"domain": d, "source": source} for d in set(domains)]
    supabase.table("blacklisted_domains").upsert(records, ignore_duplicates=False).execute()
    print(f"Upserted {len(records)} domains from {source}")

def upsert_numbers(numbers: list[str], source: str):
    if not numbers:
        return
    records = [{"phone_number": n, "source": source} for n in set(numbers)]
    supabase.table("blacklisted_numbers").upsert(records, ignore_duplicates=False).execute()
    print(f"Upserted {len(records)} phone numbers from {source}")

def upsert_vpas(vpas: list[str], source: str):
    if not vpas:
        return
    records = [{"vpa_string": v, "source": source} for v in set(vpas)]
    supabase.table("blacklisted_vpas").upsert(records, ignore_duplicates=False).execute()
    print(f"Upserted {len(records)} VPAs from {source}")

def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting threat intel ingestion")

    # Domains
    for url in FEEDS["domains"]:
        text = fetch_text(url)
        if text is None:
            continue
        domains = extract_domains(text)
        source = "openphish" if "openphish" in url else "phishtank"
        upsert_domains(domains, source)

    # Phone numbers (placeholder – add real sources)
    for url in FEEDS["phone_numbers"]:
        text = fetch_text(url)
        if text is None:
            continue
        numbers = [l.strip() for l in text.splitlines() if l.strip()]
        upsert_numbers(numbers, "external_feed")

    # VPAs (placeholder – add real sources)
    for url in FEEDS["vpas"]:
        text = fetch_text(url)
        if text is None:
            continue
        vpas = [l.strip() for l in text.splitlines() if l.strip()]
        upsert_vpas(vpas, "external_feed")

    print(f"[{datetime.now(timezone.utc).isoformat()}] Ingestion complete")

if __name__ == "__main__":
    main()