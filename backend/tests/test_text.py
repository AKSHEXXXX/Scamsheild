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
    assert data["risk_score"] >= 40
    assert "scan_id" in data

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
