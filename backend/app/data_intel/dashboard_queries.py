import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("scamshield.dashboard")

def _db():
    from app.database_ext import MongoDBClient
    return MongoDBClient.db()

def get_overview_metrics(window_minutes: int = 60):
    db = _db()
    if db is None:
        return {"total_scans": 0, "by_channel": {}, "score_distribution": {}}
    start = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    pipeline = [
        {"$match": {"created_at": {"$gte": start}}},
        {"$group": {
            "_id": "$channel",
            "count": {"$sum": 1},
            "high_risk": {"$sum": {"$cond": [{"$eq": ["$verdict", "high_risk"]}, 1, 0]}},
            "suspicious": {"$sum": {"$cond": [{"$eq": ["$verdict", "suspicious"]}, 1, 0]}},
            "low_risk": {"$sum": {"$cond": [{"$eq": ["$verdict", "low_risk"]}, 1, 0]}},
            "scores": {"$push": "$score"},
        }},
    ]
    try:
        results = list(db.scans.aggregate(pipeline))
    except Exception as e:
        logger.warning("dashboard overview aggregation failed: %s", e)
        return {"total_scans": 0, "by_channel": {}, "score_distribution": {}}

    total = 0
    by_channel = {}
    score_dist = {}
    for r in results:
        ch = r["_id"] or "unknown"
        by_channel[ch] = {
            "count": r["count"],
            "high_risk": r["high_risk"],
            "suspicious": r["suspicious"],
            "low_risk": r["low_risk"],
        }
        total += r["count"]
        scores = sorted(r["scores"])
        if scores:
            n = len(scores)
            score_dist[ch] = {
                "p10": scores[max(0, n // 10 - 1)],
                "p50": scores[n // 2],
                "p90": scores[min(n - 1, 9 * n // 10)],
            }
    return {"total_scans": total, "by_channel": by_channel, "score_distribution": score_dist}


def _fn_fp_via_feedback(db, start, verdicts_fn, verdict_fp):
    try:
        fn_pipeline = [
            {"$match": {"created_at": {"$gte": start}, "verdict": {"$in": verdicts_fn}}},
            {"$lookup": {
                "from": "feedback",
                "let": {"sid": "$scan_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$and": [
                        {"$eq": ["$scan_id", "$$sid"]},
                        {"$eq": ["$label", "scam"]},
                    ]}}},
                    {"$limit": 1},
                ],
                "as": "matching_feedback",
            }},
            {"$match": {"matching_feedback.0": {"$exists": True}}},
            {"$group": {"_id": "$channel", "count": {"$sum": 1}}},
        ]
        fn_candidates = list(db.scans.aggregate(fn_pipeline))
    except Exception as e:
        logger.warning("dashboard FN query failed: %s", e)
        fn_candidates = []

    try:
        fp_pipeline = [
            {"$match": {"created_at": {"$gte": start}, "verdict": verdict_fp}},
            {"$lookup": {
                "from": "feedback",
                "let": {"sid": "$scan_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$and": [
                        {"$eq": ["$scan_id", "$$sid"]},
                        {"$eq": ["$label", "legit"]},
                    ]}}},
                    {"$limit": 1},
                ],
                "as": "matching_feedback",
            }},
            {"$match": {"matching_feedback.0": {"$exists": True}}},
            {"$group": {"_id": "$channel", "count": {"$sum": 1}}},
        ]
        fp_candidates = list(db.scans.aggregate(fp_pipeline))
    except Exception as e:
        logger.warning("dashboard FP query failed: %s", e)
        fp_candidates = []

    result = {}
    for ch in set(r["_id"] for r in fn_candidates) | set(r["_id"] for r in fp_candidates):
        result[ch] = {
            "fn_candidates": next((r["count"] for r in fn_candidates if r["_id"] == ch), 0),
            "fp_candidates": next((r["count"] for r in fp_candidates if r["_id"] == ch), 0),
        }
    return result


def get_quality_metrics(window_minutes: int = 60):
    db = _db()
    if db is None:
        return {"approx_fn_fp": {}}
    start = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    feedback_result = _fn_fp_via_feedback(db, start, ["low_risk", "suspicious"], "high_risk")
    return {"approx_fn_fp": feedback_result}


def get_agent_quality_metrics(window_minutes: int = 60):
    db = _db()
    if db is None:
        return []
    start = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    from app.ml.model_loader import get_agent_status, get_accuracy
    statuses = get_agent_status()
    accuracy = get_accuracy()
    try:
        signal_counts = list(db.scans.aggregate([
            {"$match": {"created_at": {"$gte": start}, "result.agent_results": {"$exists": True}}},
            {"$unwind": "$result.agent_results"},
            {"$group": {"_id": "$result.agent_results.agent_id", "signals_used": {"$sum": 1}}},
        ]))
    except Exception as e:
        logger.warning("dashboard signal count query failed: %s", e)
        signal_counts = []

    signal_map = {r["_id"]: r["signals_used"] for r in signal_counts}
    agents = []
    for aid in sorted(statuses.keys(), key=int):
        s = statuses[aid]
        acc = accuracy.get(f"agent{aid}", {})
        agents.append({
            "agent_id": int(aid),
            "name": s.get("name", ""),
            "status": s.get("status", "UNKNOWN"),
            "model_version": f"agent{aid}-{s.get('status', 'unknown').lower()}",
            "signals_used": signal_map.get(int(aid), 0),
            "metric": acc.get("metric", ""),
            "metric_value": acc.get("value", "N/A"),
            "notes": s.get("status_detail", ""),
        })
    return agents


def get_recent_anomalies(window_minutes: int = 60):
    db = _db()
    if db is None:
        return []
    start = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    try:
        docs = list(db.anomalies.find(
            {"created_at": {"$gte": start}},
        ).sort("created_at", -1).limit(20))
    except Exception as e:
        logger.warning("dashboard anomalies query failed: %s", e)
        return []
    return [{
        "type": d.get("type", "unknown"),
        "severity": d.get("details", {}).get("severity", "info"),
        "count": d.get("details", {}).get("count", 0),
        "window": str(d.get("created_at", "")),
    } for d in docs]


def compute_feedback_stats():
    """Aggregate feedback by channel+label, compute daily stats, store result."""
    db = _db()
    if db is None:
        return {}
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        by_channel_label = list(db.feedback.aggregate([
            {"$match": {"created_at": {"$gte": seven_days_ago}}},
            {"$group": {"_id": {"channel": "$channel", "label": "$label"}, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]))
    except Exception as e:
        logger.warning("feedback channel/label agg failed: %s", e)
        by_channel_label = []

    try:
        top_confusing = list(db.feedback.aggregate([
            {"$match": {"created_at": {"$gte": seven_days_ago}}},
            {"$group": {"_id": "$scan_id", "count": {"$sum": 1}, "reasons": {"$push": "$reason"}}},
            {"$sort": {"count": -1}},
            {"$limit": 5},
            {"$lookup": {
                "from": "scans",
                "localField": "_id",
                "foreignField": "scan_id",
                "as": "scan",
            }},
            {"$project": {
                "scan_id": "$_id", "count": 1,
                "preview": {"$arrayElemAt": ["$scan.input_preview", 0]},
                "sample_reasons": {"$slice": ["$reasons", 3]},
            }},
        ]))
    except Exception as e:
        logger.warning("feedback top confusing query failed: %s", e)
        top_confusing = []

    counts_by_channel = {}
    total_scam = 0
    total_legit = 0
    total_unsure = 0
    for r in by_channel_label:
        ch = r["_id"]["channel"] or "unknown"
        lb = r["_id"]["label"]
        c = r["count"]
        counts_by_channel.setdefault(ch, {})[lb] = c
        if lb == "scam":
            total_scam += c
        elif lb == "legit":
            total_legit += c
        elif lb == "unsure":
            total_unsure += c

    ratio = round(total_scam / max(total_legit, 1), 2)
    stats = {
        "feedback_counts_by_channel": counts_by_channel,
        "feedback_ratio_scams_vs_legit": ratio,
        "total_scam": total_scam,
        "total_legit": total_legit,
        "total_unsure": total_unsure,
        "top_confusing_scans": [
            {"scan_id": r.get("scan_id"), "count": r["count"],
             "preview": (r.get("preview") or "")[:120],
             "sample_reasons": r.get("sample_reasons", [])}
            for r in top_confusing
        ],
    }

    try:
        from app.data_intel.mongo_ops import save_feedback_stats
        save_feedback_stats(today, stats)
    except Exception as e:
        logger.warning("save_feedback_stats failed: %s", e)

    return stats


def get_bounty_results(limit: int = 5) -> list:
    db = _db()
    if db is None:
        return []
    try:
        docs = list(db.bounty_results.find(
            {}, {"_id": 0}
        ).sort("timestamp", -1).limit(limit))
    except Exception as e:
        logger.warning("bounty_results query failed: %s", e)
        return []
    return docs


def get_feedback_stats() -> dict:
    """Fetch latest stored feedback daily stats."""
    db = _db()
    if db is None:
        return {}
    try:
        doc = db.feedback_stats_daily.find_one(
            {}, sort=[("date", -1)]
        )
        if doc:
            return doc.get("stats", {})
    except Exception as e:
        logger.warning("get_feedback_stats failed: %s", e)
    return {}
