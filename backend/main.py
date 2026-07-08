import os
import asyncio
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.rate_limiter import RateLimitMiddleware
from app.middleware.request_tracking import RequestTrackingMiddleware
from app.analytics.posthog_client import setup_posthog, close_posthog, get_posthog_client
from docs.observability.structured_logging import setup_logging
import traceback

from app.config import settings
setup_logging(use_json=settings.ENVIRONMENT == "production")
from app.rbac import set_admin_email_domain
_admin_domain = os.getenv("ADMIN_EMAIL_DOMAIN", "")
if _admin_domain:
    set_admin_email_domain(_admin_domain)
logger = logging.getLogger("scamshield")

_anomaly_task = None
_blacklist_refresh_task = None
_retraining_task = None
BLACKLIST_REFRESH_INTERVAL_SECONDS = 7 * 24 * 3600  # weekly

# Endpoints that require auth — checked at header level before body is parsed
# ponytail: prevents unauthenticated DoS (C2 Red Team audit)
_AUTH_REQUIRED_PREFIXES = (
    "/api/v1/analyze-text",
    "/api/v1/sandbox-image",
    "/api/v1/check-qr",
    "/api/v1/analyze-url",
    "/api/v1/check-url",
    "/api/v1/feedback",
    "/api/v1/delete-account",
    "/api/v1/report",
)
_MAX_BODY_BYTES = 2_000_000  # 2 MB hard cap


async def _run_anomaly_monitor():
    await asyncio.sleep(30)
    while True:
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "jobs.anomaly_monitor",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await proc.communicate()
            if stdout:
                for line in stdout.decode().strip().splitlines():
                    if "INFO:" in line or "WARNING:" in line:
                        continue
                    logger.info("anomaly: %s", line)
        except Exception as e:
            logger.warning("anomaly_monitor run failed: %s", e)
        await asyncio.sleep(600)


async def _run_blacklist_refresh():
    await asyncio.sleep(120)
    while True:
        try:
            from jobs.refresh_url_blacklist import run_and_save
            summary = await asyncio.to_thread(run_and_save)
            logger.info("Weekly blacklist refresh complete: Agent 4 loaded %d domains (+%d) | sources=%s",
                       summary["total_domains"], summary["added"], summary["sources"])
        except Exception as e:
            logger.warning("blacklist refresh run failed: %s", e)
        await asyncio.sleep(BLACKLIST_REFRESH_INTERVAL_SECONDS)


async def _start_retraining_listener():
    await asyncio.sleep(30)
    from jobs.retraining_trigger import watch
    await watch()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _anomaly_task, _blacklist_refresh_task, _retraining_task
    logger.info("Starting background model loading and database connections...")
    setup_posthog()
    from app.ml.model_loader import load_all
    asyncio.create_task(asyncio.to_thread(load_all))
    from app.database_ext import connect_databases, close_databases
    connect_databases()
    _anomaly_task = asyncio.create_task(_run_anomaly_monitor())
    _blacklist_refresh_task = asyncio.create_task(_run_blacklist_refresh())
    _retraining_task = asyncio.create_task(_start_retraining_listener())
    yield
    if _anomaly_task:
        _anomaly_task.cancel()
    if _blacklist_refresh_task:
        _blacklist_refresh_task.cancel()
    if _retraining_task:
        _retraining_task.cancel()
    close_databases()
    close_posthog()

app = FastAPI(
    title="ScamShield API",
    version="2.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

_cors_origins = settings.CORS_ORIGINS or ["*"]
_allow_credentials = "*" not in _cors_origins
if not _allow_credentials:
    logger.warning("CORS_ORIGINS contains '*' so allow_credentials is disabled for safety")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-Device-Id"],
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestTrackingMiddleware)


@app.middleware("http")
async def auth_and_size_guard(request: Request, call_next):
    """Check Authorization header and body size BEFORE FastAPI parses the body.
    Prevents unauthenticated large-body DoS (Red Team C2)."""
    path = request.url.path
    if any(path.startswith(p) for p in _AUTH_REQUIRED_PREFIXES):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(status_code=401,
                                content={"detail": "Authorization header required"})
        cl = request.headers.get("content-length")
        if cl and int(cl) > _MAX_BODY_BYTES:
            return JSONResponse(status_code=413,
                                content={"detail": "Request body too large (max 2 MB)"})
    response = await call_next(request)
    # Security headers (H2 Red Team audit)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


from routers.meta import router as meta_router
from routers.text import router as text_router
from routers.url import router as url_router
from routers.qr import router as qr_router
from routers.upi import router as upi_router
from routers.image import router as image_router
from routers.audio import router as audio_router
from routers.scan import router as scan_router
from routers.dashboard import router as dashboard_router
from routers.feedback import router as feedback_router
from routers.admin_dashboard import router as admin_router
from routers.referral import router as referral_router
from routers.account import router as account_router
app.include_router(meta_router)
app.include_router(scan_router)
app.include_router(dashboard_router)
app.include_router(feedback_router)
app.include_router(text_router)
app.include_router(url_router)
app.include_router(qr_router)
app.include_router(upi_router)
app.include_router(image_router)
app.include_router(audio_router)
app.include_router(admin_router)
app.include_router(referral_router)
app.include_router(account_router)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc):
    try:
        raw_body = await request.body()
    except Exception:
        raw_body = b""
    logger.info("422 on %s: invalid request body | content-type=%s | body=%r | errors=%s",
                request.url.path, request.headers.get("content-type", ""), raw_body[:500], exc.errors())
    try:
        get_posthog_client().capture_event(
            "api_request_failed", "unknown",
            properties={"method": request.method, "status": "validation_error"},
            endpoint=request.url.path,
            http_status=422,
            status="failure",
            error_type="ValidationError",
            error_message=str(exc.errors())[:300],
        )
    except Exception:
        pass
    return JSONResponse(status_code=422, content={"detail": "Invalid request body"})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    error_type = type(exc).__name__
    error_msg = str(exc) or "Internal server error"
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error("500 on %s: %s: %s\n%s", request.url.path, error_type, error_msg, tb)
    try:
        user_id = getattr(request.state, "user_id", "unknown")
        get_posthog_client().capture_event(
            "api_request_failed", user_id,
            properties={"method": request.method},
            endpoint=request.url.path,
            platform=getattr(request.state, "platform", "unknown"),
            http_status=500,
            status="failure",
            error_type=error_type,
            error_message=error_msg[:500],
        )
    except Exception:
        pass
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
