from fastapi import Header, HTTPException
from typing import Optional
from app.database import supabase

def require_user(authorization: Optional[str] = None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    token = authorization.replace("Bearer ", "")
    try:
        user = supabase.auth.get_user(token)
        return user.user.id
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def enforce_credit_cap(user_id: str, cap: int, scan_count: int):
    if scan_count >= cap:
        raise HTTPException(
            status_code=429,
            detail=f"Scan credit cap of {cap} reached. Upgrade or wait for reset."
        )