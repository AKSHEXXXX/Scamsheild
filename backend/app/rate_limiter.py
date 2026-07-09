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
IP_LIMIT_GLOBAL = int(os.getenv("RATE_LIMIT_IP_GLOBAL", "200"))  # Global across all routes
USER_LIMIT = int(os.getenv("RATE_LIMIT_USER", "100"))
TENANT_LIMIT = int(os.getenv("RATE_LIMIT_TENANT", "500"))
WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
IP_REP_CACHE_TTL = 300
# Fail-closed mode: if True (default), deny all requests when Redis is down (production)
# If False, allow all when Redis down (dev convenience)
RATE_LIMIT_FAIL_CLOSED = os.getenv("RATE_LIMIT_FAIL_CLOSED", "true").lower() == "true"

_redis_down_logged = False

# Lua script for atomic rate limiting: ZREMRANGEBYSCORE + ZADD + ZCARD in one atomic op
_RATE_LIMIT_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_start = now - tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local event_member = ARGV[4]

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

-- Add new event
redis.call('ZADD', key, now, event_member)

-- Set expiry
redis.call('EXPIRE', key, tonumber(ARGV[2]))

-- Count current
local count = redis.call('ZCARD', key)

return {count, limit}
"""

async def _check_rate_limit(key: str, limit: int) -> tuple[bool, int]:
    global _redis_down_logged
    r = RedisClient.client()
    if r is None:
        if not _redis_down_logged:
            logger.critical("Redis unavailable — rate limiting %s; app is %s",
                          "DISABLED (fail-open)" if not RATE_LIMIT_FAIL_CLOSED else "FAIL-CLOSED",
                          "unprotected" if not RATE_LIMIT_FAIL_CLOSED else "protected")
            _redis_down_logged = True
        if RATE_LIMIT_FAIL_CLOSED:
            return False, limit + 1  # Deny
        return True, 0  # Allow

    now = int(time.time())
    now_ms = int(time.time() * 1000)
    event_member = f"{now_ms}-{uuid.uuid4().hex}"
    try:
        # Atomic rate limit check via Lua script
        result = await r.eval(_RATE_LIMIT_LUA, 1, key, now, WINDOW_SECONDS, limit, event_member)
        count = int(result[0])
        allowed = count <= limit
        return allowed, count
    except Exception as exc:
        logger.error("Rate limit check error: %s", exc)
        if RATE_LIMIT_FAIL_CLOSED:
            return False, limit + 1
        return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not RedisClient.is_connected():
            global _redis_down_logged
            if not _redis_down_logged:
                logger.critical("Redis unavailable — rate limiting %s",
                              "FAIL-CLOSED (deny all)" if RATE_LIMIT_FAIL_CLOSED else "DISABLED (allow all)")
                _redis_down_logged = True
            if RATE_LIMIT_FAIL_CLOSED:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Rate limiter unavailable", "code": "RATE_LIMITER_DOWN"},
                )
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

        # Global IP limit (across all routes) - prevents spreading requests
        global_allowed, global_count = await _check_rate_limit(
            f"rl:ip:{client_ip}:global", IP_LIMIT_GLOBAL
        )
        if not global_allowed:
            logger.warning("Global IP rate limit exceeded: %s (%d/%d)", client_ip, global_count, IP_LIMIT_GLOBAL)
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Try again later.", "code": "RATE_LIMITED_IP_GLOBAL"},
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )

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
