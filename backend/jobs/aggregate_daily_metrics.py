"""Compute daily metrics from MongoDB scans and upsert into Supabase daily_metrics.
Run as: python -m jobs.aggregate_daily_metrics
Scheduled via cron or Railway cron job once per hour."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logging
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aggregate_daily_metrics")


def run():
    from app.database_ext import MongoDBClient
    from supabase import create_client
    from app.config import settings

    mongo_ok = MongoDBClient.connect()
    if not mongo_ok:
        logger.warning("MongoDB not available, skipping")
        return

    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    db = MongoDBClient.db()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = start - timedelta(days=1)

    try:
        pipeline = [
            {"$match": {"created_at": {"$gte": start}}},
            {"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "high_risk": {"$sum": {"$cond": [{"$eq": ["$verdict", "high_risk"]}, 1, 0]}},
                "suspicious": {"$sum": {"$cond": [{"$eq": ["$verdict", "suspicious"]}, 1, 0]}},
                "low_risk": {"$sum": {"$cond": [{"$eq": ["$verdict", "low_risk"]}, 1, 0]}},
                "avg_score": {"$avg": "$score"},
                "unique_users": {"$addToSet": "$user_id"},
                "channels": {"$push": "$channel"},
            }},
        ]
        result = list(db.scans.aggregate(pipeline))
        if not result:
            logger.info("No scans today yet")
            return

        r = result[0]
        total = r.get("total", 0)
        high = r.get("high_risk", 0)
        susp = r.get("suspicious", 0)
        low = r.get("low_risk", 0)
        scam = high + susp
        safe = low
        avg = round(r.get("avg_score", 0) or 0, 2)
        users = len(r.get("unique_users", []))

        channels = {}
        for ch in r.get("channels", []):
            channels[ch] = channels.get(ch, 0) + 1

        sb.table("daily_metrics").upsert({
            "date": today,
            "total_scans": total,
            "scam_scans": scam,
            "safe_scans": safe,
            "high_risk_scans": high,
            "suspicious_scans": susp,
            "low_risk_scans": low,
            "avg_score": avg,
            "unique_users": users,
            "by_channel": channels,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="date").execute()

        logger.info("Aggregated %d scans for %s", total, today)
    except Exception as e:
        logger.error("Aggregation failed: %s", e)
    finally:
        MongoDBClient.close()


if __name__ == "__main__":
    run()
