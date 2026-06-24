import uuid
import base64
import logging
from typing import Literal, Optional
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from app.auth import require_user
from app.helpers import persist_scan

router = APIRouter(tags=["audio"])
logger = logging.getLogger("scamshield.audio")

class AnalyzeAudioIn(BaseModel):
    audio_bytes_b64: str = Field(max_length=10_000_000)
    os: Literal["iOS", "Android"]

@router.post("/api/v1/analyze-audio")
async def analyze_audio(body: AnalyzeAudioIn,
                        authorization: str = Header(None),
                        x_device_id: Optional[str] = Header(None)):
    raise HTTPException(
        status_code=501,
        detail={
            "error": "audio_analysis_unavailable",
            "message": "Audio analysis is coming in the next update.",
            "available_at": "Sprint 3"
        }
    )
