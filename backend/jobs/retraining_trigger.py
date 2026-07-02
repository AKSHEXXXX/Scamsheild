import asyncio
import logging
from datetime import datetime, timezone

from app.database_ext import MongoDBClient

logger = logging.getLogger("scamshield.retraining_trigger")

BATCH_THRESHOLD = 500
POLL_INTERVAL = 5.0
STATE_COLLECTION = "retrain_config"
STATE_DOC_ID = "state"
REPORTS_COLLECTION = "scam_reports"

# Lazy import target — set by _get_trigger() on first call, or overridden
# in tests via monkeypatch.
_trigger_fn = None


async def _get_trigger():
    global _trigger_fn
    if _trigger_fn is None:
        from jobs.colab_retrainer import trigger_colab_retraining
        _trigger_fn = trigger_colab_retraining
    return _trigger_fn


async def _check_and_fire() -> bool:
    """Check MongoDB report count and fire retraining if threshold met.
    Returns True if retraining was triggered, False otherwise."""
    db = MongoDBClient.db()
    if db is None:
        return False

    state = db[STATE_COLLECTION].find_one({"_id": STATE_DOC_ID})
    if state is None:
        db[STATE_COLLECTION].insert_one({
            "_id": STATE_DOC_ID,
            "last_count": 0,
            "last_run": None,
        })
        last_count = 0
    else:
        last_count = state.get("last_count", 0)

    current_count = db[REPORTS_COLLECTION].count_documents({})
    if current_count < 0:
        current_count = 0

    new_reports = current_count - last_count

    if new_reports >= BATCH_THRESHOLD:
        logger.info(
            "Retraining trigger: %d new reports (threshold=%d). Firing...",
            new_reports, BATCH_THRESHOLD)

        db[STATE_COLLECTION].update_one(
            {"_id": STATE_DOC_ID},
            {"$set": {
                "last_count": current_count,
                "last_run": datetime.now(timezone.utc).isoformat(),
            }},
        )

        records = list(
            db[REPORTS_COLLECTION]
            .find({})
            .sort("_id", -1)
            .limit(BATCH_THRESHOLD)
        )

        trigger_fn = await _get_trigger()
        asyncio.create_task(trigger_fn(records))
        return True

    return False


async def watch():
    logger.info("Retraining trigger: starting change stream watcher")
    await asyncio.sleep(15)

    while True:
        try:
            await _check_and_fire()
        except Exception as e:
            logger.warning("Retraining trigger error: %s", e)

        await asyncio.sleep(POLL_INTERVAL)
