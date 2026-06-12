from fastapi import Header, HTTPException
from typing import Optional
from app.database import supabase

def resolve_identity(device_id: str, authorization: Optional[str] = None) -> tuple:
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-Id header is required")
    
    user_id = None
    if authorization:
        token = authorization.replace("Bearer ", "")
        try:
            user = supabase.auth.get_user(token)
            user_id = user.user.id
        except Exception:
            pass
    
    return device_id, user_id

def enforce_credit_cap(subject: str, cap: int, scan_count: int):
    if scan_count >= cap:
        raise HTTPException(
            status_code=429,
            detail=f"Scan credit cap of {cap} reached. Upgrade or wait for reset."
        )