import logging
import secrets
import string
from fastapi import APIRouter, Header, HTTPException
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


@router.post("/api/v1/referral/redeem")
def redeem_referral(body: RedeemRequest, authorization: str = Header(None)):
    current_user_id = require_user(authorization)

    referral = supabase.table("referrals") \
        .select("*") \
        .eq("code", body.referral_code) \
        .maybe_single() \
        .execute()
    if not referral.data:
        raise HTTPException(status_code=400, detail="Invalid or already used referral code.")

    referrer_id = referral.data["owner_id"]
    if referrer_id == current_user_id:
        raise HTTPException(status_code=400, detail="Invalid or already used referral code.")

    existing = supabase.table("referral_redemptions") \
        .select("id") \
        .eq("redeemed_by", current_user_id) \
        .maybe_single() \
        .execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Invalid or already used referral code.")

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

    return {
        "scans_credited": scans_credited,
        "referrer_rewarded": True,
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
