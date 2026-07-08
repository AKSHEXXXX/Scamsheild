import logging
from fastapi import APIRouter, Header, HTTPException, Request
from app.models import FeedbackIn, FeedbackOut
from app.auth import require_user
from app.logging_utils import log_event, hash_id
from app.data_intel.mongo_ops import MongoDBClient
from app.helpers import _get_service_client
from app.analytics.posthog_client import get_posthog_client

router = APIRouter(tags=["feedback"])
logger = logging.getLogger("scamshield.feedback")

VALID_LABELS = {"scam", "legit", "unsure"}

@router.post("/api/v1/feedback", response_model=FeedbackOut)
async def submit_feedback(request: Request,
                           body: FeedbackIn,
                           authorization: str = Header(None)):
    user_id = require_user(authorization)
    request.state.user_id = user_id
    endpoint = request.url.path
    request_id = getattr(request.state, "request_id", "")
    posthog = get_posthog_client()
    label = body.label.lower()
    if label not in VALID_LABELS:
        raise HTTPException(status_code=400, detail=f"label must be one of: {', '.join(VALID_LABELS)}")
    # Verify scan exists in MongoDB
    db = MongoDBClient.db()
    if db is None:
        raise HTTPException(status_code=503, detail="Feedback storage unavailable")
    scan = db.scans.find_one({"scan_id": body.scan_id}, {"user_id": 1, "channel": 1})
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="You can only label your own scans")
    try:
        sb = _get_service_client()
        sb.table("feedback").insert({
            "scan_id": body.scan_id,
            "user_id": user_id,
            "label": label,
            "reason": body.reason or "",
        }).execute()
    except Exception as e:
        logger.warning("Supabase feedback insert failed (non-fatal): %s", e)
    from app.data_intel.mongo_ops import save_feedback
    save_feedback(
        scan_id=body.scan_id,
        user_id=user_id,
        channel=scan.get("channel", "unknown"),
        label=label,
        reason=body.reason or "",
    )
    log_event("feedback_submitted", level="INFO",
              scan_id=body.scan_id, user_id=hash_id(user_id),
              extra={"channel": scan.get("channel", ""), "label": label})
    posthog.capture_event(
        "feedback_submitted", user_id,
        properties={
            "channel": scan.get("channel", "unknown"),
            "label": label,
        },
        request_id=request_id, endpoint=endpoint, platform="unknown",
    )
    return FeedbackOut(ok=True)
