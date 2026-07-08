import logging
import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from app.auth import require_user
from app.config import settings
from app.database import supabase
from app.analytics.posthog_client import get_posthog_client

router = APIRouter(tags=["account"])
logger = logging.getLogger("scamshield.account")

SUPABASE_ADMIN_API = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users"


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
    request.state.user_id = user_id
    request_id = getattr(request.state, "request_id", "")
    headers = {
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "apikey": settings.SUPABASE_SERVICE_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(
                f"{SUPABASE_ADMIN_API}/{user_id}",
                headers=headers,
            )
    except httpx.HTTPError as e:
        logger.warning("Supabase Admin API delete request failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to delete account. Please try again later.")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="User not found or already deleted.")
    if resp.status_code not in (200, 204):
        logger.warning("Supabase Admin API delete failed: %d %s", resp.status_code, resp.text[:200])
        raise HTTPException(status_code=502, detail="Failed to delete account. Please try again later.")

    _delete_mongo_user_scans(user_id)
    _delete_supabase_user_rows(user_id)
    posthog = get_posthog_client()
    posthog.capture_event("account_deleted", user_id, properties={},
                          request_id=request_id, endpoint="/api/v1/delete-account", platform="unknown")
    logger.info("Account deleted: user_id=%s", user_id)
    return None
