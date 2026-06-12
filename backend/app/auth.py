from fastapi import Header, HTTPException
from jose import jwt, JWTError
from app.config import settings

def verify_jwt(authorization: str) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.replace("Bearer ", "")
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
        return payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def enforce_credit_cap(user_id: str, cap: int, scan_count: int):
    if scan_count >= cap:
        raise HTTPException(
            status_code=429,
            detail=f"Scan credit cap of {cap} reached. Upgrade or wait for reset."
        )