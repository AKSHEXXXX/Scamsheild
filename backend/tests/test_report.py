from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from main import app
import pytest

_headers = {"Authorization": "Bearer test-token"}

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.mark.anyio
@patch("routers.meta.require_user", return_value="mock-user-id")
@patch("routers.meta.persist_report", return_value="mock-report-id")
async def test_submit_report_success(mock_persist, mock_auth):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/report", json={
            "report_type": "other",
            "value": "test-report@example.com",
            "channel": "email",
            "os": "Android"
        }, headers=_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["report_id"] == "mock-report-id"
    mock_persist.assert_called_once()
