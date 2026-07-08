import logging
import secrets
import string
import posthog
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel
from app.auth import require_user, _sum_bonus_earned, _count_bonus_consumed
from app.database import supabase
from app.helpers import get_config_dict

"""
============================================================================
REFERRAL REWARD MODEL — SPEC A (flat one-time credit)
============================================================================
Spec A: New user redeems referral_code once. Referrer gets +5 scans ONE TIME,
permanently added to their balance. New user gets +5 scans ONE TIME.

Spec B (alternative — recurring monthly bonus):
  - +5 scans apply only to the current month, reset each month
  - Requires monthly entitlement tracking rather than one-time credit

To switch to Spec B:
  1. Toggle USE_MONTHLY_RESET = True below
  2. Add a "reward_month" column (date-trunc to month) to
     referral_redemptions
  3. Change scan-credits math to sum only redemptions matching current month
     (instead of lifetime sum)
  4. Referral notification logic stays the same (one notification per
     redemption, not repeated monthly)
============================================================================
"""
USE_MONTHLY_RESET = False  # TODO: Set to True if Spec B is confirmed

router = APIRouter(tags=["referral"])
logger = logging.getLogger("scamshield.referral")

CODE_CHARS = string.ascii_uppercase + string.digits


def _generate_referral_code() -> str:
    return "TS-" + "".join(secrets.choice(CODE_CHARS) for _ in range(8))


def _ensure_referral(user_id: str) -> dict:
    result = supabase.table("referrals").select("*").eq("owner_id", user_id).maybe_single().execute()
    if result.data:
        return result.data
    for attempt in range(5):
        code = _generate_referral_code()
        try:
            r = supabase.table("referrals").insert({
                "owner_id": user_id,
                "code": code,
            }).execute()
            return r.data[0]
        except Exception:
            continue
    raise HTTPException(status_code=500, detail="Failed to generate unique referral code")


class RedeemRequest(BaseModel):
    referral_code: str


@router.get("/api/v1/referral/status")
def referral_status(authorization: str = Header(None)):
    user_id = require_user(authorization)
    referral = _ensure_referral(user_id)
    code = referral["code"]

    redemptions = supabase.table("referral_redemptions") \
        .select("scans_credited") \
        .eq("referral_id", referral["id"]) \
        .execute()
    rows = redemptions.data or []
    referrals_count = len(rows)
    scans_earned = sum(r["scans_credited"] for r in rows)

    return {
        "referral_code": code,
        "referral_link": f"https://trustscan.app/invite/{code}",
        "referrals_count": referrals_count,
        "scans_earned": scans_earned,
    }


@router.get("/api/v1/referral/validate/{referral_code}")
def validate_referral(referral_code: str, authorization: str = Header(None)):
    current_user_id = require_user(authorization)
    code = (referral_code or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="referral_code is required")

    referral = supabase.table("referrals") \
        .select("id,owner_id,code") \
        .eq("code", code) \
        .maybe_single() \
        .execute()
    if not referral.data:
        return {
            "valid": False,
            "can_redeem": False,
            "reason": "invalid_code",
        }

    referrer_id = referral.data["owner_id"]
    if referrer_id == current_user_id:
        return {
            "valid": True,
            "can_redeem": False,
            "reason": "self_referral_not_allowed",
        }

    existing = supabase.table("referral_redemptions") \
        .select("id") \
        .eq("redeemed_by", current_user_id) \
        .maybe_single() \
        .execute()
    if existing.data:
        return {
            "valid": True,
            "can_redeem": False,
            "reason": "already_redeemed",
        }

    return {
        "valid": True,
        "can_redeem": True,
        "reason": "ok",
        "referral_code": referral.data["code"],
    }


@router.get("/api/v1/invite/{referral_code}")
def invite_lookup(referral_code: str):
    code = (referral_code or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="referral_code is required")

    referral = supabase.table("referrals") \
        .select("id,owner_id,code") \
        .eq("code", code) \
        .maybe_single() \
        .execute()
    if not referral.data:
        return {
            "valid": False,
            "referral_code": code,
            "deep_link": f"trustscan://invite/{code}",
        }

    return {
        "valid": True,
        "referral_code": referral.data["code"],
        "deep_link": f"trustscan://invite/{referral.data['code']}",
    }


@router.post("/api/v1/referral/redeem")
def redeem_referral(body: RedeemRequest, authorization: str = Header(None)):
    current_user_id = require_user(authorization)
    code = (body.referral_code or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="referral_code is required")

    referral = supabase.table("referrals") \
        .select("*") \
        .eq("code", code) \
        .maybe_single() \
        .execute()
    if not referral.data:
        raise HTTPException(status_code=404, detail="Referral code not found.")

    referrer_id = referral.data["owner_id"]
    if referrer_id == current_user_id:
        raise HTTPException(status_code=409, detail="You cannot redeem your own referral code.")

    existing = supabase.table("referral_redemptions") \
        .select("id") \
        .eq("redeemed_by", current_user_id) \
        .maybe_single() \
        .execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="You have already redeemed a referral code.")

    scans_credited = 5
    supabase.table("referral_redemptions").insert({
        "referral_id": referral.data["id"],
        "redeemed_by": current_user_id,
        "scans_credited": scans_credited,
    }).execute()

    _insert_notification(
        user_id=referrer_id,
        kind="referral_reward",
        title="Referral Reward Earned!",
        body=f"You earned {scans_credited} bonus scans! A new user joined using your code.",
    )

    posthog.capture(
        current_user_id,
        "referral_redeemed",
        properties={"scans_credited": scans_credited},
    )

    return {"bonus_scans_credited": scans_credited}


@router.get("/api/v1/referral/redemption-status")
def redemption_status(authorization: str = Header(None)):
    user_id = require_user(authorization)
    redemption = supabase.table("referral_redemptions") \
        .select("id,referral_id,redeemed_at,scans_credited") \
        .eq("redeemed_by", user_id) \
        .maybe_single() \
        .execute()

    if not redemption.data:
        return {
            "has_redeemed": False,
            "redeemed_at": None,
            "scans_credited": 0,
            "referral_code": None,
        }

    code = None
    referral_id = redemption.data.get("referral_id")
    if referral_id:
        ref = supabase.table("referrals") \
            .select("code") \
            .eq("id", referral_id) \
            .maybe_single() \
            .execute()
        if ref.data:
            code = ref.data.get("code")

    return {
        "has_redeemed": True,
        "redeemed_at": redemption.data.get("redeemed_at"),
        "scans_credited": redemption.data.get("scans_credited", 0),
        "referral_code": code,
    }


def _insert_notification(user_id: str, kind: str, title: str, body: str):
    try:
        supabase.table("notifications").insert({
            "user_id": user_id,
            "kind": kind,
            "title": title,
            "body": body,
        }).execute()
    except Exception as e:
        logger.warning("Failed to insert notification: %s", e)


@router.get("/api/v1/user/scan-credits")
def scan_credits(authorization: str = Header(None)):
    user_id = require_user(authorization)

    try:
        config = get_config_dict()
        base_daily_cap = config.get("scan_credit_cap", 50)
    except Exception:
        base_daily_cap = 50

    bonus_earned = _sum_bonus_earned(user_id)
    bonus_consumed = _count_bonus_consumed(user_id)
    bonus_remaining = max(0, bonus_earned - bonus_consumed)

    return {
        "base_daily_cap": base_daily_cap,
        "bonus_scans": bonus_remaining,
        "total_available": base_daily_cap + bonus_remaining,
    }


@router.get("/api/v1/referral/scan-credits")
def referral_scan_credits(authorization: str = Header(None)):
    # Alias for mobile clients that scope all referral APIs under /referral.
    return scan_credits(authorization)


@router.get("/api/v1/notifications")
def list_notifications(
    authorization: str = Header(None),
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
):
    user_id = require_user(authorization)
    query = supabase.table("notifications") \
        .select("id,kind,title,body,read,created_at") \
        .eq("user_id", user_id)
    if unread_only:
        query = query.eq("read", False)

    resp = query.order("created_at", desc=True).limit(limit).execute()
    rows = resp.data or []
    unread_count = sum(1 for n in rows if not n.get("read"))
    return {
        "items": rows,
        "unread_count": unread_count,
    }


@router.post("/api/v1/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str, authorization: str = Header(None)):
    user_id = require_user(authorization)
    supabase.table("notifications") \
        .update({"read": True}) \
        .eq("id", notification_id) \
        .eq("user_id", user_id) \
        .execute()
    return {"ok": True}


@router.post("/api/v1/notifications/read-all")
def mark_notifications_read_all(authorization: str = Header(None)):
    user_id = require_user(authorization)
    supabase.table("notifications") \
        .update({"read": True}) \
        .eq("user_id", user_id) \
        .eq("read", False) \
        .execute()
    return {"ok": True}
