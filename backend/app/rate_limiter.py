import os
import time
import json
import logging
import uuid
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.database_ext import RedisClient

logger = logging.getLogger("scamshield.ratelimit")

IP_LIMIT = int(os.getenv("RATE_LIMIT_IP", "60"))
USER_LIMIT = int(os.getenv("RATE_LIMIT_USER", "100"))
TENANT_LIMIT = int(os.getenv("RATE_LIMIT_TENANT", "500"))
WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
IP_REP_CACHE_TTL = 300


async def _check_ip_reputation(ip: str) -> Optional[str]:
    r = RedisClient.client()
    if r is None:
        return None
    try:
        raw = await r.get(f"ti:ip:{ip}")
        if raw:
            data = json.loads(raw)
            return data.get("reputation")
    except Exception:
        pass
    return None


_redis_down_logged = False

async def _check_rate_limit(key: str, limit: int) -> tuple[bool, int]:
    global _redis_down_logged
    r = RedisClient.client()
    if r is None:
        if not _redis_down_logged:
            logger.critical("Redis unavailable — rate limiting disabled; app is unprotected")
            _redis_down_logged = True
        return True, 0
    now = int(time.time())
    now_ms = int(time.time() * 1000)
    event_member = f"{now_ms}-{uuid.uuid4().hex}"
    window_start = now - WINDOW_SECONDS
    try:
        async with r.pipeline(transaction=True) as pipe:
            await pipe.zremrangebyscore(key, 0, window_start)
            await pipe.zadd(key, {event_member: now})
            await pipe.zcard(key)
            await pipe.expire(key, WINDOW_SECONDS)
            _, _, count, _ = await pipe.execute()
        allowed = count <= limit
        return allowed, count
    except Exception as exc:
        logger.error("Rate limit check error: %s", exc)
        return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not RedisClient.is_connected():
            global _redis_down_logged
            if not _redis_down_logged:
                logger.critical("Redis unavailable — rate limiting disabled; app is unprotected")
                _redis_down_logged = True
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        route = request.url.path

        rep = await _check_ip_reputation(client_ip)
        if rep == "malicious":
            logger.warning("Blocked malicious IP: %s on %s", client_ip, route)
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=403,
                content={"detail": "Access denied", "code": "IP_BLOCKED"},
            )

        ip_limit = 5 if rep == "suspicious" else IP_LIMIT

        ip_allowed, ip_count = await _check_rate_limit(
            f"rl:ip:{client_ip}:{route}", ip_limit
        )
        if not ip_allowed:
            logger.warning("IP rate limit exceeded: %s on %s (%d/%d)", client_ip, route, ip_count, ip_limit)
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Try again later.", "code": "RATE_LIMITED_IP"},
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )

        from app.auth import _extract_user_from_request
        user_id = _extract_user_from_request(request)
        if user_id:
            user_allowed, user_count = await _check_rate_limit(
                f"rl:user:{user_id}:{route}", USER_LIMIT
            )
            if not user_allowed:
                logger.warning("User rate limit exceeded: %s on %s (%d/%d)", user_id, route, user_count, USER_LIMIT)
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Try again later.", "code": "RATE_LIMITED_USER"},
                    headers={"Retry-After": str(WINDOW_SECONDS)},
                )

        return await call_next(request)
