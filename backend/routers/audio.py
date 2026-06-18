import uuid
import base64
import logging
from typing import Optional
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from app.auth import require_user
from app.helpers import persist_scan

router = APIRouter(tags=["audio"])
logger = logging.getLogger("scamshield.audio")

class AnalyzeAudioIn(BaseModel):
    audio_bytes_b64: str
    os: str

@router.post("/api/v1/analyze-audio")
async def analyze_audio(body: AnalyzeAudioIn,
                        authorization: str = Header(None),
                        x_device_id: Optional[str] = Header(None)):
    user_id = require_user(authorization)
    from app.ml.agents.inference import agent12_transcribe, agent13_predict_transcript, agent1_predict_text
    from agents.agent15_ensemble import compute_ensemble_verdict
    try:
        audio_bytes = base64.b64decode(body.audio_bytes_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 audio data")
    asr = agent12_transcribe(audio_bytes)
    transcript = asr.get("transcript", "")
    if not transcript:
        return {
            "scan_id": str(uuid.uuid4()), "kind": "audio",
            "risk_score": 0, "verdict": "low_risk",
            "warning_count": 0, "extracted_text": "",
            "findings": [{"type": "asr", "severity": "info",
                          "title": "ASR not available",
                          "detail": "Whisper ASR requires PyTorch — not loaded"}],
            "flagged_urls": [],
            "_meta": {"asr_method": "unavailable"},
        }
    text_prob = agent1_predict_text(transcript)
    call_prob = agent13_predict_transcript(transcript)
    score, verdict, ml_debug = compute_ensemble_verdict(
        ml_text_prob=text_prob,
        call_fraud_prob=call_prob,
        scan_type="audio",
    )
    result = {
        "risk_score": min(100, score),
        "verdict": verdict,
        "warning_count": 1 if verdict == "high_risk" else 0,
        "extracted_text": transcript,
        "findings": [{"type": "ml_ensemble", "severity": "info",
                      "title": "ML scores", "detail": str(ml_debug)}],
        "flagged_urls": [],
    }
    scan_id = persist_scan("audio", user_id, body.os, x_device_id, transcript, result, verdict == "high_risk")
    return {"scan_id": scan_id, "kind": "audio", **result, "_meta": {"asr_method": asr.get("method", "unavailable")}}
