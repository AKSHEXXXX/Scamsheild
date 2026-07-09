import logging
import re
from datetime import datetime, timezone
from typing import Optional
from app.database_ext import MongoDBClient

logger = logging.getLogger("scamshield.mongo_ops")
_warned = False

_MONGO_KEY_RE = re.compile(r'^[\w\.\$]+$')

def _sanitize_mongo_key(key: str) -> str:
    """Sanitize a key for use in MongoDB query to prevent injection.
    Only allow alphanumeric, underscore, dot, dollar sign."""
    if not _MONGO_KEY_RE.match(key):
        # Replace invalid chars with underscore
        return re.sub(r'[^\w\.\$]', '_', key)
    return key

def _sanitize_mongo_value(value: str) -> str:
    """Sanitize a string value for MongoDB query."""
    # Remove potential MongoDB operator characters at start
    if value.startswith('$') or value.startswith('{') or value.startswith('['):
        return '_' + value
    return value

def _warn_once():
    global _warned
    if not _warned:
        logger.info("MongoDB not connected — data_intel operations are no-ops")
        _warned = True


def save_scan(
    scan_id: str,
    user_id: str,
    channel: str,
    score: int,
    verdict: str,
    result: dict,
    flagged: bool = False,
    warning_count: int = 0,
    input_preview: str = "",
    device_id: str = "unknown",
    os: str = "unknown",
    posture: Optional[dict] = None,
    ip: str = "",
):
    db = MongoDBClient.db()
    if db is None:
        _warn_once()
        return
    try:
        doc = {
            "scan_id": scan_id,
            "user_id": user_id,
            "device_id": device_id,
            "os": os,
            "channel": channel,
            "input_preview": input_preview[:200],
            "result": result,
            "score": score,
            "verdict": verdict,
            "warning_count": warning_count,
            "flagged": flagged,
            "created_at": datetime.now(timezone.utc),
        }
        if posture:
            doc["posture"] = posture
        if ip:
            doc["ip"] = ip
        db.scans.insert_one(doc)
    except Exception as e:
        logger.warning("MongoDB save_scan failed: %s", e)


def save_report(
    report_id: str,
    user_id: str,
    report_type: str,
    value: str,
    channel: str,
    description: Optional[str] = None,
    related_scan_id: Optional[str] = None,
    os: str = "unknown",
    device_id: str = "unknown",
):
    db = MongoDBClient.db()
    if db is None:
        _warn_once()
        return
    try:
        db.reports.insert_one({
            "report_id": report_id,
            "user_id": user_id,
            "report_type": report_type,
            "value": value,
            "channel": channel,
            "description": description,
            "related_scan_id": related_scan_id,
            "os": os,
            "device_id": device_id,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.warning("MongoDB save_report failed: %s", e)


def upsert_threat_domain(domain: str, reputation: str, source: str, tags: Optional[list[str]] = None):
    db = MongoDBClient.db()
    if db is None:
        _warn_once()
        return
    now = datetime.now(timezone.utc)
    try:
        db.threat_intel_domains.update_one(
            {"domain": domain},
            {
                "$set": {
                    "reputation": reputation,
                    "last_seen": now,
                    "source": source,
                },
                "$setOnInsert": {
                    "first_seen": now,
                },
                "$addToSet": {
                    "tags": {"$each": tags or []},
                },
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning("MongoDB upsert_threat_domain failed: %s", e)


def upsert_threat_vpa(vpa: str, reputation: str, source: str):
    db = MongoDBClient.db()
    if db is None:
        _warn_once()
        return
    now = datetime.now(timezone.utc)
    try:
        db.threat_intel_vpas.update_one(
            {"vpa": vpa},
            {"$set": {"reputation": reputation, "last_seen": now, "source": source},
             "$setOnInsert": {"first_seen": now}},
            upsert=True,
        )
    except Exception as e:
        logger.warning("MongoDB upsert_threat_vpa failed: %s", e)


def upsert_threat_number(phone_number: str, reputation: str, source: str):
    db = MongoDBClient.db()
    if db is None:
        _warn_once()
        return
    now = datetime.now(timezone.utc)
    try:
        db.threat_intel_numbers.update_one(
            {"phone_number": phone_number},
            {"$set": {"reputation": reputation, "last_seen": now, "source": source},
             "$setOnInsert": {"first_seen": now}},
            upsert=True,
        )
    except Exception as e:
        logger.warning("MongoDB upsert_threat_number failed: %s", e)


def write_analytics_event(event_type: str, scan_id: str, user_id: str, channel: str, verdict: str, score: int, agents_triggered: Optional[list[int]] = None):
    db = MongoDBClient.db()
    if db is None:
        return
    try:
        db.analytics_events.insert_one({
            "event_id": f"{scan_id}-{event_type}",
            "event_type": event_type,
            "scan_id": scan_id,
            "user_id": user_id,
            "channel": channel,
            "verdict": verdict,
            "score": score,
            "agents_triggered": agents_triggered or [],
            "timestamp": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.warning("MongoDB analytics event failed: %s", e)


def upsert_threat_ip(ip: str, reputation: str, source: str, tags: Optional[list[str]] = None):
    db = MongoDBClient.db()
    if db is None:
        _warn_once()
        return
    now = datetime.now(timezone.utc)
    try:
        db.threat_intel_ips.update_one(
            {"ip": ip},
            {"$set": {"reputation": reputation, "last_seen": now, "source": source},
             "$setOnInsert": {"first_seen": now},
             "$addToSet": {"tags": {"$each": tags or []}}},
            upsert=True,
        )
    except Exception as e:
        logger.warning("MongoDB upsert_threat_ip failed: %s", e)


def save_anomaly(anomaly_type: str, details: dict):
    db = MongoDBClient.db()
    if db is None:
        return
    try:
        db.anomalies.insert_one({
            "type": anomaly_type,
            "details": details,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.warning("MongoDB save_anomaly failed: %s", e)


def save_feedback(scan_id: str, user_id: str, channel: str, label: str, reason: str = ""):
    db = MongoDBClient.db()
    if db is None:
        _warn_once()
        return
    try:
        safe_scan_id = _sanitize_mongo_key(scan_id)
        safe_user_id = _sanitize_mongo_key(user_id)
        safe_channel = _sanitize_mongo_key(channel)
        safe_label = _sanitize_mongo_key(label)
        safe_reason = _sanitize_mongo_value(reason[:500] if reason else "")
        db.feedback.update_one(
            {"scan_id": safe_scan_id, "user_id": safe_user_id},
            {"$set": {
                "scan_id": safe_scan_id,
                "user_id": safe_user_id,
                "channel": safe_channel,
                "label": safe_label,
                "reason": safe_reason,
                "created_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning("MongoDB save_feedback failed: %s", e)


def save_feedback_stats(date_label: str, stats: dict):
    db = MongoDBClient.db()
    if db is None:
        return
    try:
        db.feedback_stats_daily.update_one(
            {"date": date_label},
            {"$set": {
                "date": date_label,
                "stats": stats,
                "created_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning("MongoDB save_feedback_stats failed: %s", e)


def update_model_registry(agent_id: int, agent_name: str, model_version: str, status: str, metrics: Optional[dict] = None):
    db = MongoDBClient.db()
    if db is None:
        return
    try:
        db.model_registry.update_one(
            {"agent_id": agent_id},
            {"$set": {
                "agent_name": agent_name,
                "model_version": model_version,
                "status": status,
                "metrics": metrics or {},
                "updated_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning("MongoDB update_model_registry failed: %s", e)
