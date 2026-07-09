import logging
import uuid
from fastapi import APIRouter, Header, HTTPException, Request
from app.auth import require_user
from app.database import supabase
from app.analytics.posthog_client import get_posthog_client

router = APIRouter(tags=["account"])
logger = logging.getLogger("scamshield.account")

SUPABASE_ADMIN_API = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users"


def _validate_user_id(user_id: str) -> None:
    """Validate user_id is a valid UUID to prevent SSRF via malformed JWT claims."""
    try:
        uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")


def _delete_supabase_user_rows(user_id: str):
    for table, column in (
        ("scans", "user_id"),
        ("reports", "user_id"),
        ("referral_redemptions", "redeemed_by"),
        ("referrals", "owner_id"),
        ("notifications", "user_id"),
        ("feedback", "user_id"),
        ("bonus_scan_consumptions", "user_id"),
    ):
        try:
            supabase.table(table).delete().eq(column, user_id).execute()
        except Exception as e:
            logger.warning("Cleanup of %s for user %s failed (non-fatal): %s", table, user_id, e)


def _delete_mongo_user_scans(user_id: str):
    try:
        from app.data_intel.mongo_ops import MongoDBClient
        db = MongoDBClient.db()
        if db is not None:
            db.scans.delete_many({"user_id": user_id})
    except Exception:
        pass


@router.post("/api/v1/delete-account", status_code=204)
async def delete_account(request: Request,
                         authorization: str = Header(None)):
    user_id = require_user(authorization)
    _validate_user_id(user_id)
    request.state.user_id = user_id
    request_id = getattr(request.state, "request_id", "")

    # Use Supabase client instead of raw HTTP to avoid service key in headers
    try:
        supabase.auth.admin.delete_user(user_id)
    except Exception as e:
        logger.warning("Supabase admin delete failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to delete account. Please try again later.")

    _delete_mongo_user_scans(user_id)
    _delete_supabase_user_rows(user_id)
    posthog = get_posthog_client()
    posthog.capture_event("account_deleted", user_id, properties={},
                          request_id=request_id, endpoint="/api/v1/delete-account", platform="unknown")
    logger.info("Account deleted: user_id=%s", user_id)
    return None
