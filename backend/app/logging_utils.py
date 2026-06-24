import re
import json
import hashlib
import logging
from typing import Optional

logger = logging.getLogger("scamshield.logging")

_PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{7,15}\d)")
_UPI_RE = re.compile(r"[a-zA-Z0-9._\-]{2,}@[a-zA-Z0-9._\-]{2,}")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def _mask_phone(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) >= 10:
        return digits[:4] + "XXXXXX" + digits[-2:]
    return match.group(0)


def _mask_upi(match: re.Match) -> str:
    parts = match.group(0).split("@")
    if len(parts) == 2:
        return parts[0][:2] + "***@" + parts[1]
    return match.group(0)


def _mask_email(match: re.Match) -> str:
    parts = match.group(0).split("@")
    if len(parts) == 2:
        local = parts[0][:2] + "***" if len(parts[0]) > 2 else parts[0]
        return f"{local}@{parts[1]}"
    return match.group(0)


def _mask_url(match: re.Match) -> str:
    url = match.group(0)
    domain_match = re.search(r"https?://([^/\s\"'<>]+)", url)
    if domain_match:
        domain = domain_match.group(1)
        parts = url.split("://", 1)
        scheme = parts[0] if len(parts) > 1 else "http"
        suffix = ""
        path_match = re.search(r"/[^?\s]*", url)
        if path_match:
            path = path_match.group(0)
            if len(path) > 20:
                suffix = path[:10] + "..." + path[-7:]
            else:
                suffix = path
        qs_match = re.search(r"\?[^\s]*", url)
        if qs_match:
            suffix += "?..."
        return f"{scheme}://{domain}{suffix}"
    return url


def sanitize_pii(text: str) -> str:
    text = _PHONE_RE.sub(_mask_phone, text)
    text = _EMAIL_RE.sub(_mask_email, text)
    text = _UPI_RE.sub(_mask_upi, text)
    text = _URL_RE.sub(_mask_url, text)
    return text


def hash_id(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def log_event(
    event_type: str,
    level: str = "INFO",
    scan_id: Optional[str] = None,
    user_id: Optional[str] = None,
    device_id: Optional[str] = None,
    ip: Optional[str] = None,
    channel: Optional[str] = None,
    verdict: Optional[str] = None,
    score: Optional[int] = None,
    agent_ids: Optional[list[int]] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
    extra: Optional[dict] = None,
):
    record = {
        "event": event_type,
        "deployment_id": "scamshield-prod",
        "service": "scamshield-api",
    }
    if scan_id:
        record["scan_id"] = scan_id
    if user_id:
        record["user_id"] = user_id
    if device_id:
        record["device_id"] = hash_id(device_id) if device_id not in ("unknown", "") else "unknown"
    if ip:
        record["ip"] = ip
    if channel:
        record["channel"] = channel
    if verdict:
        record["verdict"] = verdict
    if score is not None:
        record["score"] = score
    if agent_ids:
        record["agent_ids"] = agent_ids
    if message:
        record["message"] = sanitize_pii(message)
    if error:
        record["error"] = error
    if extra:
        record.update(extra)

    log_line = json.dumps(record, default=str)
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level, "%s", log_line)
    return record
