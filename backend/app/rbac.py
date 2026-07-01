import logging
from datetime import datetime, timezone
from functools import lru_cache
from fastapi import Header, HTTPException, Depends
from app.auth import require_user
from app.database import supabase

logger = logging.getLogger("scamshield.rbac")

ADMIN_EMAIL_DOMAIN = None

def set_admin_email_domain(domain: str):
    global ADMIN_EMAIL_DOMAIN
    ADMIN_EMAIL_DOMAIN = domain

@lru_cache(maxsize=None)
def _get_service_client():
    from supabase import create_client
    from app.config import settings
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

def _get_user_email(user_id: str) -> str:
    try:
        user = supabase.auth.admin.get_user_by_id(user_id)
        return user.user.email or ""
    except Exception:
        return ""

def _ensure_admin_user(email: str, name: str) -> str:
    sb = _get_service_client()
    result = sb.table("admin_users").select("id").eq("email", email).execute()
    if result.data:
        admin_id = result.data[0]["id"]
        sb.table("admin_users").update({
            "last_login_at": datetime.now(timezone.utc).isoformat(),
            "name": name,
        }).eq("id", admin_id).execute()
        return admin_id
    ins = sb.table("admin_users").insert({
        "email": email,
        "name": name,
        "last_login_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    return ins.data[0]["id"]

def _get_user_permissions(user_id: str) -> list[str]:
    sb = _get_service_client()
    result = sb.table("user_roles") \
        .select("roles!inner(name, role_permissions!inner(permissions!inner(resource, action)))") \
        .eq("user_id", user_id) \
        .execute()
    perms = set()
    for row in result.data or []:
        roles = row.get("roles", {})
        for rp in roles.get("role_permissions", []) if isinstance(roles, dict) else []:
            p = rp.get("permissions", {})
            perms.add(f"{p.get('resource', '')}:{p.get('action', '')}")
    return sorted(perms)

def _get_user_roles(user_id: str) -> list[str]:
    sb = _get_service_client()
    result = sb.table("user_roles") \
        .select("roles!inner(name)") \
        .eq("user_id", user_id) \
        .execute()
    return [row["roles"]["name"] for row in result.data or []]

def require_admin_auth(authorization: str = Header(None)):
    user_id = require_user(authorization)
    email = _get_user_email(user_id)
    if not email:
        raise HTTPException(status_code=403, detail="Access denied: could not resolve user email")
    if ADMIN_EMAIL_DOMAIN:
        parts = email.split("@")
        if len(parts) != 2 or not parts[1].endswith(ADMIN_EMAIL_DOMAIN):
            raise HTTPException(status_code=403, detail=f"Access denied: must use a @{ADMIN_EMAIL_DOMAIN} email")
    name = email.split("@")[0]
    admin_id = _ensure_admin_user(email, name)
    roles = _get_user_roles(admin_id)
    permissions = _get_user_permissions(admin_id)
    if not roles:
        raise HTTPException(status_code=403, detail="Access denied: no admin roles assigned")
    return {
        "admin_id": admin_id,
        "user_id": user_id,
        "email": email,
        "name": name,
        "roles": roles,
        "permissions": permissions,
    }

def require_permission(permission: str):
    def checker(admin: dict = Depends(require_admin_auth)):
        if permission not in admin["permissions"]:
            raise HTTPException(status_code=403, detail=f"Access denied: missing permission '{permission}'")
        return admin
    return checker
