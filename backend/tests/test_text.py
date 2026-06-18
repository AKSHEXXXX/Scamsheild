import os
import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from app.database import supabase

skip_if_no_supabase = pytest.mark.skipif(
    not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_KEY"),
    reason="SUPABASE_URL and SUPABASE_SERVICE_KEY must be set"
)

_headers = {}

def _ensure_token():
    if _headers:
        return
    try:
        resp = supabase.auth.sign_in_with_password({"email": "test-runner@scamshield.com", "password": "testpass123"})
        _headers["Authorization"] = f"Bearer {resp.session.access_token}"
    except Exception:
        resp = supabase.auth.admin.create_user({"email": "test-runner@scamshield.com", "password": "testpass123", "email_confirm": True})
        resp2 = supabase.auth.sign_in_with_password({"email": "test-runner@scamshield.com", "password": "testpass123"})
        _headers["Authorization"] = f"Bearer {resp2.session.access_token}"

@pytest.fixture
def anyio_backend():
    return "asyncio"

@skip_if_no_supabase
@pytest.mark.anyio
async def test_analyze_text_scam():
    _ensure_token()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/analyze-text", json={
            "text": "Your OTP is 123456. Share it immediately to avoid account suspension.",
            "os": "Android"
        }, headers=_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["scam_score"] >= 40
    assert "signals" in data
    assert data["signals"]["text_tfidf_prob"] is not None

@skip_if_no_supabase
@pytest.mark.anyio
async def test_analyze_text_safe():
    _ensure_token()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/analyze-text", json={
            "text": "Hey, are we still on for lunch tomorrow?",
            "os": "Android"
        }, headers=_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "low_risk"

@skip_if_no_supabase
@pytest.mark.anyio
async def test_analyze_text_regex_runs_first():
    _ensure_token()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/analyze-text", json={
            "text": "URGENT: Your account is blocked. KYC pending. Share OTP 123456 immediately.",
            "os": "Android"
        }, headers=_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["signals"]["regex_score"] is not None
    assert data["signals"]["regex_score"] > 0

@skip_if_no_supabase
@pytest.mark.anyio
async def test_analyze_text_returns_scan_result_schema():
    """Verify the response matches the ScanResult schema"""
    _ensure_token()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/analyze-text", json={
            "text": "Hey, are we still on for lunch tomorrow?",
            "os": "Android"
        }, headers=_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "scam_score" in data
    assert "verdict" in data
    assert "signals" in data
    assert "top_signal" in data
    assert "confidence" in data
    assert "flagged_urls" in data
    assert "meta" in data
