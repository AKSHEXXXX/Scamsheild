from fastapi import Header, HTTPException, Request
from typing import Optional
from app.database import supabase

def require_user(authorization: Optional[str] = None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header must start with 'Bearer '")
    token = authorization[7:]  # Remove "Bearer " prefix (exact 7 chars)
    if not token:
        raise HTTPException(status_code=401, detail="Bearer token missing")
    try:
        user = supabase.auth.get_user(token)
        return user.user.id
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _extract_user_from_request(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    token = auth[7:]  # Remove "Bearer " prefix
    if not token:
        return None
    try:
        user = supabase.auth.get_user(token)
        return user.user.id
    except Exception:
        return None


def enforce_credit_cap(user_id: str, cap: int, scan_count: int):
    if scan_count >= cap:
        raise HTTPException(
            status_code=429,
            detail=f"Scan credit cap of {cap} reached. Upgrade or wait for reset."
        )


# ── Bonus-scan helpers (referral system) ──────────────────────

def _sum_bonus_earned(user_id: str) -> int:
    """Total scans_credited to this user across referral_redemptions
    (both as referrer and as redeemer)."""
    total = 0
    try:
        referrals = supabase.table("referrals") \
            .select("id") \
            .eq("owner_id", user_id) \
            .execute()
        if referrals.data:
            for ref in referrals.data:
                redemptions = supabase.table("referral_redemptions") \
                    .select("scans_credited") \
                    .eq("referral_id", ref["id"]) \
                    .execute()
                for r in (redemptions.data or []):
                    total += r["scans_credited"]
        my_redemptions = supabase.table("referral_redemptions") \
            .select("scans_credited") \
            .eq("redeemed_by", user_id) \
            .execute()
        for r in (my_redemptions.data or []):
            total += r["scans_credited"]
    except Exception:
        return total
    return total


def _count_bonus_consumed(user_id: str) -> int:
    """Number of bonus scans already consumed by this user."""
    try:
        result = supabase.table("bonus_scan_consumptions") \
            .select("id", count="exact") \
            .eq("user_id", user_id) \
            .execute()
        return result.count or 0
    except Exception:
        return 0


def calculate_effective_cap(user_id: str, base_cap: int) -> int:
    """Effective daily cap = base_cap + remaining bonus scans."""
    earned = _sum_bonus_earned(user_id)
    consumed = _count_bonus_consumed(user_id)
    remaining = max(0, earned - consumed)
    return base_cap + remaining


def record_bonus_consumption(user_id: str, scan_id: Optional[str] = None):
    """Record that one bonus scan was consumed."""
    try:
        supabase.table("bonus_scan_consumptions").insert({
            "user_id": user_id,
            "scan_id": scan_id or "",
        }).execute()
    except Exception:
        pass