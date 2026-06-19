import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scamshield")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading all AI agents at startup...")
    from app.ml.model_loader import load_all
    load_all()
    yield

app = FastAPI(title="ScamShield API", version="2.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers.meta import router as meta_router
from routers.text import router as text_router
from routers.url import router as url_router
from routers.qr import router as qr_router
from routers.upi import router as upi_router
from routers.image import router as image_router
from routers.audio import router as audio_router
app.include_router(meta_router)
app.include_router(text_router)
app.include_router(url_router)
app.include_router(qr_router)
app.include_router(upi_router)
app.include_router(image_router)
app.include_router(audio_router)

@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    body = await request.body()
    content_type = request.headers.get("content-type", "")
    if body:
        import json as j
        try:
            data = j.loads(body)
            logger.warning(f"422 on {request.url.path}: body_keys={list(data.keys())}, "
                         f"os={data.get('os', '?')}, "
                         f"b64_len={len(data.get('image_base64', '')) if 'image_base64' in data else 0}, "
                         f"b64_present={'image_base64' in data}, "
                         f"content_type={content_type}")
        except Exception:
            logger.warning(f"422 on {request.url.path}: invalid JSON body, content_type={content_type}")
    else:
        logger.warning(f"422 on {request.url.path}: empty body, content_type={content_type}")
    if hasattr(exc, "errors"):
        detail = exc.errors()
    else:
        detail = exc.detail if hasattr(exc, "detail") else str(exc)
    logger.warning(f"422 detail: {detail}")
    return JSONResponse(status_code=422, content={"detail": detail})
