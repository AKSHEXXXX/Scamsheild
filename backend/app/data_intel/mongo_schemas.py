MONGODB_COLLECTIONS = {
    "scans": {
        "description": "Final scan results for history, analytics, and retraining",
        "indexes": [
            {"keys": [("user_id", 1), ("created_at", -1)]},
            {"keys": [("scan_id", 1)], "unique": True},
            {"keys": [("created_at", -1)]},
            {"keys": [("channel", 1), ("created_at", -1)]},
        ],
        "ttl_days": None,
    },
    "reports": {
        "description": "User-submitted 'this looks wrong' reports",
        "indexes": [
            {"keys": [("value", 1)]},
            {"keys": [("created_at", -1)]},
            {"keys": [("report_id", 1)], "unique": True},
            {"keys": [("related_scan_id", 1)]},
        ],
        "ttl_days": None,
    },
    "threat_intel_domains": {
        "description": "Domain-level threat intel from feeds (OpenPhish, PhishTank, URLhaus)",
        "indexes": [
            {"keys": [("domain", 1)], "unique": True},
            {"keys": [("reputation", 1), ("last_seen", -1)]},
        ],
        "ttl_days": None,
    },
    "threat_intel_vpas": {
        "description": "UPI VPAs flagged by rule engine or external feeds",
        "indexes": [
            {"keys": [("vpa", 1)], "unique": True},
        ],
        "ttl_days": None,
    },
    "threat_intel_numbers": {
        "description": "Phone numbers flagged as scam",
        "indexes": [
            {"keys": [("phone_number", 1)], "unique": True},
        ],
        "ttl_days": None,
    },
    "model_registry": {
        "description": "Track agent/model versions and readiness",
        "indexes": [
            {"keys": [("agent_id", 1)], "unique": True},
        ],
        "ttl_days": None,
    },
    "analytics_events": {
        "description": "Event log for analytics / retraining pipeline",
        "indexes": [
            {"keys": [("event_type", 1), ("timestamp", -1)]},
            {"keys": [("timestamp", -1)]},
        ],
        "ttl_days": 90,
    },
    "threat_intel_ips": {
        "description": "IP addresses flagged as malicious/suspicious",
        "indexes": [
            {"keys": [("ip", 1)], "unique": True},
            {"keys": [("reputation", 1), ("last_seen", -1)]},
        ],
        "ttl_days": None,
    },
    "anomalies": {
        "description": "Detected anomalies from monitoring job",
        "indexes": [
            {"keys": [("created_at", -1)]},
            {"keys": [("type", 1), ("created_at", -1)]},
        ],
        "ttl_days": 30,
    },
    "feedback": {
        "description": "User-submitted labels (scam/legit/unsure) for retraining",
        "indexes": [
            {"keys": [("scan_id", 1)]},
            {"keys": [("user_id", 1), ("created_at", -1)]},
            {"keys": [("created_at", -1)]},
        ],
        "ttl_days": None,
    },
    "feedback_stats_daily": {
        "description": "Daily aggregated feedback stats for dashboard",
        "indexes": [
            {"keys": [("date", -1)], "unique": True},
            {"keys": [("created_at", -1)]},
        ],
        "ttl_days": 90,
    },
    "bounty_results": {
        "description": "Bounty test results per deployment",
        "indexes": [
            {"keys": [("deployment_id", 1), ("timestamp", -1)]},
            {"keys": [("timestamp", -1)]},
        ],
        "ttl_days": None,
    },
}
