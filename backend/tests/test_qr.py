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

QR_COMMON_PATCHES = [
    patch("routers.qr.require_user", return_value="mock-qr-user"),
    patch("routers.qr.calculate_effective_cap", return_value=9999),
    patch("routers.qr.enforce_credit_cap"),
    patch("routers.qr.persist_scan", return_value="mock-qr-scan"),
    patch("routers.qr.supabase.table", _mock_supabase_table()),
]

@pytest.mark.anyio
async def test_check_qr_returns_result():
    for p in QR_COMMON_PATCHES:
        p.start()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/check-qr", json={
                "payload": "https://www.google.com",
                "os": "Android"
            }, headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "scam_score" in data
        assert "verdict" in data
    finally:
        for p in reversed(QR_COMMON_PATCHES):
            p.stop()
