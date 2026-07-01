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
from docs.observability.structured_logging import setup_logging

setup_logging()
from app.rbac import set_admin_email_domain
_admin_domain = os.getenv("ADMIN_EMAIL_DOMAIN", "")
if _admin_domain:
    set_admin_email_domain(_admin_domain)
logger = logging.getLogger("scamshield")

_anomaly_task = None


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _anomaly_task
    logger.info("Starting background model loading and database connections...")
    from app.ml.model_loader import load_all
    asyncio.create_task(asyncio.to_thread(load_all))
    from app.database_ext import connect_databases, close_databases
    connect_databases()
    _anomaly_task = asyncio.create_task(_run_anomaly_monitor())
    yield
    if _anomaly_task:
        _anomaly_task.cancel()
    close_databases()

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
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)

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

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc):
    logger.info("422 on %s: invalid request body", request.url.path)
    return JSONResponse(status_code=422, content={"detail": "Invalid request body"})
