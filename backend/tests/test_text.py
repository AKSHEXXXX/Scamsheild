import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.fixture
def anyio_backend():
    return "asyncio"

def _mock_supabase_table():
    m = MagicMock()
    m.select.return_value.eq.return_value.gte.return_value.execute.return_value = MagicMock(count=0)
    return m

TEXT_COMMON_PATCHES = [
    patch("routers.text.require_user", return_value="mock-scan-user"),
    patch("routers.text.calculate_effective_cap", return_value=9999),
    patch("routers.text.enforce_credit_cap"),
    patch("routers.text.persist_scan", return_value="mock-scan-abc"),
    patch("routers.text.supabase.table", _mock_supabase_table()),
]

def _apply_patches():
    for p in TEXT_COMMON_PATCHES:
        p.start()

def _stop_patches():
    for p in reversed(TEXT_COMMON_PATCHES):
        p.stop()

@pytest.mark.anyio
async def test_analyze_text_scam():
    for p in TEXT_COMMON_PATCHES:
        p.start()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/analyze-text", json={
                "text": "Your OTP is 123456. Share it immediately to avoid account suspension.",
                "os": "Android"
            }, headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["scam_score"] >= 40
        assert "signals" in data
    finally:
        _stop_patches()

@pytest.mark.anyio
async def test_analyze_text_safe():
    for p in TEXT_COMMON_PATCHES:
        p.start()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/analyze-text", json={
                "text": "Hey, are we still on for lunch tomorrow?",
                "os": "Android"
            }, headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["verdict"] == "low_risk"
    finally:
        _stop_patches()

@pytest.mark.anyio
async def test_analyze_text_regex_runs_first():
    for p in TEXT_COMMON_PATCHES:
        p.start()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/analyze-text", json={
                "text": "URGENT: Your account is blocked. KYC pending. Share OTP 123456 immediately.",
                "os": "Android"
            }, headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["signals"]["regex_score"] is not None
        assert data["signals"]["regex_score"] > 0
    finally:
        _stop_patches()

@pytest.mark.anyio
async def test_analyze_text_returns_scan_result_schema():
    for p in TEXT_COMMON_PATCHES:
        p.start()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/analyze-text", json={
                "text": "Hey, are we still on for lunch tomorrow?",
                "os": "Android"
            }, headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "scam_score" in data
        assert "verdict" in data
        assert "signals" in data
        assert "top_signal" in data
        assert "confidence" in data
        assert "flagged_urls" in data
        assert "meta" in data
    finally:
        _stop_patches()

@pytest.mark.anyio
async def test_analyze_text_response_has_required_android_fields():
    for p in TEXT_COMMON_PATCHES:
        p.start()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/analyze-text", json={
                "text": "Your OTP is 123456",
                "os": "Android"
            }, headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "scan_id" in data
        assert "findings" in data
        assert isinstance(data["findings"], list)
        assert "warning_count" in data
        assert isinstance(data["warning_count"], int)
        assert "extracted_text" in data
        assert data["extracted_text"] == "Your OTP is 123456"
        assert "kind" in data
        assert data["kind"] == "message"
        assert "flagged" in data
        assert isinstance(data["flagged"], bool)
        assert isinstance(data["flagged_urls"], list)
        for url in data["flagged_urls"]:
            assert isinstance(url, str)
    finally:
        _stop_patches()
