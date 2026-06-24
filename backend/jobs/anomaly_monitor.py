"""
Anomaly monitor job.

Queries MongoDB scans for last 10 minutes, compares to rolling 24h baseline,
and writes anomaly events when thresholds are exceeded.

Usage:
    python jobs/anomaly_monitor.py

Schedule via Railway cron every 5-10 minutes.
"""
import os
import sys
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("anomaly_monitor")


def _get_db():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.database_ext import MongoDBClient
    from app.config import settings
    MongoDBClient.connect()
    return MongoDBClient.db()


def _aggregate_window(db, minutes: int, label: str) -> dict:
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    pipeline = [
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "high_risk": {"$sum": {"$cond": [{"$eq": ["$verdict", "high_risk"]}, 1, 0]}},
            "suspicious": {"$sum": {"$cond": [{"$eq": ["$verdict", "suspicious"]}, 1, 0]}},
            "avg_score": {"$avg": "$score"},
        }},
    ]
    cursor = list(db.scans.aggregate(pipeline))
    if not cursor:
        return {"label": label, "total": 0, "high_risk": 0, "suspicious": 0, "avg_score": 0}
    row = cursor[0]
    return {
        "label": label,
        "total": row.get("total", 0),
        "high_risk": row.get("high_risk", 0),
        "suspicious": row.get("suspicious", 0),
        "avg_score": round(row.get("avg_score", 0), 1),
    }


def _save_anomaly(anomaly_type: str, details: dict):
    try:
        from app.data_intel.mongo_ops import save_anomaly
        save_anomaly(anomaly_type, details)
    except Exception as e:
        logger.warning("Failed to save anomaly: %s", e)


def main():
    db = _get_db()
    if db is None:
        logger.warning("MongoDB not connected — skipping anomaly check")
        return

    current = _aggregate_window(db, 10, "last_10min")
    baseline = _aggregate_window(db, 1440, "last_24h")

    logger.info("Current(10m): total=%d high=%d suspicious=%d avg=%.1f",
                current["total"], current["high_risk"], current["suspicious"], current["avg_score"])
    logger.info("Baseline(24h): total=%d high=%d suspicious=%d avg=%.1f",
                baseline["total"], baseline["high_risk"], baseline["suspicious"], baseline["avg_score"])

    if baseline["total"] == 0:
        logger.info("No baseline data yet — skipping anomaly detection")
        return

    anomalies = []

    hr_ratio_current = current["high_risk"] / max(current["total"], 1)
    hr_ratio_baseline = baseline["high_risk"] / max(baseline["total"], 1)
    if hr_ratio_current > 0.8:
        anomalies.append({
            "type": "spike_high_risk",
            "details": {
                "current_ratio": hr_ratio_current,
                "baseline_ratio": hr_ratio_baseline,
                "current_high": current["high_risk"],
                "baseline_high": baseline["high_risk"],
            },
        })

    if baseline["total"] > 0 and current["total"] > baseline["total"] * 5:
        anomalies.append({
            "type": "traffic_surge",
            "details": {
                "current_total": current["total"],
                "baseline_total": baseline["total"],
            },
        })

    if current["total"] == 0 and baseline["total"] > 10:
        anomalies.append({
            "type": "traffic_drop",
            "details": {
                "baseline_total": baseline["total"],
            },
        })

    for anomaly in anomalies:
        logger.warning("Anomaly detected: %s — %s", anomaly["type"], anomaly["details"])
        _save_anomaly(anomaly["type"], anomaly["details"])

    if not anomalies:
        logger.info("No anomalies detected")


if __name__ == "__main__":
    main()
