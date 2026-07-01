"""
Weekly threat-intel refresh for Agent 4 (URL Blacklist Checker).

Pulls domain lists from OpenPhish, URLhaus (abuse.ch), and PhishTank,
merges them into the existing url_blacklist.pkl domain set, and writes
the result back atomically. Each source is best-effort: a failure or
rate-limit on one source (PhishTank in particular requires registration
for reliable/high-frequency access and will 429 without it) never blocks
the others, and existing domains are always preserved — this job only
ever grows the blacklist, it never removes entries.

Run manually:
    python -m jobs.refresh_url_blacklist

Scheduled automatically every 7 days from main.py's lifespan background
task (same pattern as the existing anomaly-monitor task), running
in-process so the newly merged set is hot-swapped into the live agent
via model_loader.reload_agent4_blacklist() without a redeploy.
"""
import csv
import io
import logging
import pickle
import time
from pathlib import Path
from typing import Optional

import httpx
import tldextract

logger = logging.getLogger("scamshield.jobs.blacklist_refresh")

ARTIFACT_PATH = Path(__file__).resolve().parent.parent / "app" / "ml" / "artifacts" / "url_blacklist.pkl"
MAX_FEED_BYTES = 25 * 1024 * 1024  # 25 MB safety cap per source
REQUEST_TIMEOUT = 30.0

SOURCES = {
    "openphish": "https://openphish.com/feed.txt",
    "urlhaus": "https://urlhaus.abuse.ch/downloads/text_online/",
    "phishtank": "https://data.phishtank.com/data/online-valid.csv",
}

# Safety net: never let a major legitimate platform end up in the
# blacklist. Threat feeds frequently contain phishing URLs that abuse an
# OPEN REDIRECT on a legitimate domain (e.g. "google.com/url?q=evil.com",
# a bit.ly/t.co shortener, a Google Forms/Docs link used for credential
# harvesting). Naively extracting the eTLD+1 of every URL in a feed can
# poison the blacklist with the redirector's own domain instead of the
# actual malicious target. This allowlist is intentionally small and
# conservative — top global platforms / redirectors / URL shorteners only.
NEVER_BLACKLIST_DOMAINS = {
    "google.com", "youtube.com", "gmail.com", "goo.gl", "google.co.in",
    "facebook.com", "fb.com", "instagram.com", "whatsapp.com", "wa.me",
    "twitter.com", "x.com", "t.co", "linkedin.com", "lnkd.in",
    "microsoft.com", "live.com", "outlook.com", "office.com", "bing.com",
    "apple.com", "icloud.com", "amazon.com", "amzn.to",
    "github.com", "githubusercontent.com", "gitlab.com",
    "bit.ly", "tinyurl.com", "is.gd", "rebrand.ly", "cutt.ly", "buff.ly",
    "dropbox.com", "drive.google.com", "docs.google.com", "forms.gle",
    "wikipedia.org", "yahoo.com", "telegram.org", "discord.com",
    "paypal.com", "cloudflare.com", "akamai.net", "amazonaws.com",
}


def _domain_from_url(url: str) -> Optional[str]:
    url = (url or "").strip()
    if not url:
        return None
    try:
        ext = tldextract.extract(url)
        if ext.domain and ext.suffix:
            return f"{ext.domain}.{ext.suffix}".lower()
    except Exception:
        pass
    return None


def _fetch(url: str) -> Optional[bytes]:
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                chunks = []
                total = 0
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if total > MAX_FEED_BYTES:
                        logger.warning("Source %s exceeded %d byte cap, truncating", url, MAX_FEED_BYTES)
                        break
                    chunks.append(chunk)
                return b"".join(chunks)
    except Exception as e:
        logger.warning("Fetch failed for %s: %s", url, e)
        return None


def _parse_line_list(raw: bytes) -> set:
    domains = set()
    for line in raw.decode("utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        d = _domain_from_url(line)
        if d:
            domains.add(d)
    return domains


def _parse_phishtank(raw: bytes) -> set:
    domains = set()
    try:
        text = raw.decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            d = _domain_from_url(row.get("url", ""))
            if d:
                domains.add(d)
    except Exception as e:
        logger.warning("PhishTank CSV parse failed: %s", e)
    return domains


PARSERS = {
    "openphish": _parse_line_list,
    "urlhaus": _parse_line_list,
    "phishtank": _parse_phishtank,
}


def refresh(existing_domains: Optional[set] = None) -> dict:
    """Fetch all sources, merge with existing domains. Never removes
    existing domains — only adds newly discovered ones. Domains in
    NEVER_BLACKLIST_DOMAINS are filtered out regardless of source, so an
    open-redirect abuse pattern in a feed can never poison a legitimate
    platform domain into the blacklist."""
    merged = set(existing_domains or set())
    per_source_counts = {}
    blocked_count = 0
    for name, url in SOURCES.items():
        raw = _fetch(url)
        if raw is None:
            per_source_counts[name] = "unavailable"
            continue
        parsed = PARSERS[name](raw)
        safe = parsed - NEVER_BLACKLIST_DOMAINS
        blocked_count += len(parsed) - len(safe)
        per_source_counts[name] = len(safe)
        merged |= safe
        logger.info("Blacklist source %s contributed %d domains (%d filtered by allowlist)",
                   name, len(safe), len(parsed) - len(safe))
    merged -= NEVER_BLACKLIST_DOMAINS
    if blocked_count:
        logger.warning("Blacklist refresh filtered %d allowlisted-domain hits (redirector abuse protection)", blocked_count)
    return {"domains": merged, "sources": per_source_counts}


def _load_existing() -> set:
    if not ARTIFACT_PATH.exists():
        return set()
    try:
        with open(ARTIFACT_PATH, "rb") as f:
            obj = pickle.load(f)
        return obj if isinstance(obj, set) else set(obj.get("domains", set()))
    except Exception as e:
        logger.warning("Could not read existing blacklist, starting fresh: %s", e)
        return set()


def run_and_save() -> dict:
    existing = _load_existing()
    before = len(existing)
    result = refresh(existing)
    merged = result["domains"]
    new_meta = {
        "total_domains": len(merged),
        "sources": result["sources"],
        "last_refreshed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "previous_total": before,
        "added": len(merged) - before,
    }

    tmp_path = ARTIFACT_PATH.with_suffix(".pkl.tmp")
    with open(tmp_path, "wb") as f:
        pickle.dump({"domains": merged, "meta": new_meta}, f)
    tmp_path.replace(ARTIFACT_PATH)

    try:
        from app.ml.model_loader import reload_agent4_blacklist
        reload_agent4_blacklist()
    except Exception as e:
        logger.warning("Could not hot-reload Agent 4 in-process (will pick up on next restart): %s", e)

    logger.info("Agent 4 loaded %d domains (was %d, +%d) | sources=%s",
                len(merged), before, len(merged) - before, result["sources"])
    return new_meta


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    summary = run_and_save()
    print(f"Agent 4 loaded {summary['total_domains']} domains | sources={summary['sources']}")
