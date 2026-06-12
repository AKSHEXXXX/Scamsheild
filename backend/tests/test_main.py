import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from app.config import settings
from app.database import supabase

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.mark.anyio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

@pytest.mark.anyio
async def test_config_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "scan_credit_cap" in data
    assert "sensitivity_threshold" in data

@pytest.mark.anyio
async def test_sandbox_no_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/sandbox-image",
            json={"image_base64": "dGVzdA==", "os": "iOS"},
        )
    assert resp.status_code == 401

def test_text_risk_analysis():
    from app.analytics import text_risk_analysis
    score, keywords = text_risk_analysis("Your account is blocked. Urgent KYC required.")
    assert score > 0
    assert any("Account" in k for k in keywords)

def test_compliance_score_low():
    from app.scoring import compliance_score
    score, verdict = compliance_score(10, [], 70)
    assert verdict == "low_risk"
    assert score < 70

def test_compliance_score_high():
    from app.scoring import compliance_score
    flagged = [{"url": "http://evil.com", "final_url": "http://evil.com", "reputation": "malicious"}]
    score, verdict = compliance_score(40, flagged, 70)
    assert verdict == "high_risk"
    assert score >= 70