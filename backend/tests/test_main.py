import os
from unittest.mock import patch, MagicMock
import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from app.config import settings
from app.database import supabase

skip_if_no_supabase = pytest.mark.skipif(
    not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_KEY"),
    reason="SUPABASE_URL and SUPABASE_SERVICE_KEY must be set"
)

@pytest.fixture
def anyio_backend():
    return "asyncio"

@skip_if_no_supabase
@pytest.mark.anyio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

@skip_if_no_supabase
@pytest.mark.anyio
async def test_config_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "scan_credit_cap" in data
    assert "sensitivity_threshold" in data

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
    score, verdict = compliance_score(60, flagged, 70)
    assert verdict == "high_risk"
    assert score >= 70

def test_impersonation_boost_alone_stays_low():
    from app.scoring import compliance_score
    score, verdict = compliance_score(0, [], 70, impersonation_boost=25)
    assert score <= 25
    assert verdict == "low_risk"

def test_impersonation_boost_clamped_at_100():
    from app.scoring import compliance_score
    flagged = [{"url": "http://evil.com", "final_url": "http://evil.com", "reputation": "malicious"}]
    score, verdict = compliance_score(100, flagged, 70, impersonation_boost=25)
    assert score == 100

def test_labeled_split_all_scams_detected():
    from app.analytics import text_risk_analysis
    from app.scoring import compliance_score
    from tests.labeled_samples import SCAM_SAMPLES

    failures = []
    for s in SCAM_SAMPLES:
        tscore, keywords = text_risk_analysis(s["text"])
        score, verdict = compliance_score(tscore, [], 70)
        ok = verdict in s["expected_verdict_in"]
        if not ok:
            failures.append(f"  {s['label']}: got '{verdict}' ({score}), expected {s['expected_verdict_in']}")

    assert not failures, f"\n{len(failures)} scam(s) not flagged:\n" + "\n".join(failures)

def test_labeled_split_all_legit_pass():
    from app.analytics import text_risk_analysis
    from app.scoring import compliance_score
    from tests.labeled_samples import LEGIT_SAMPLES

    failures = []
    for s in LEGIT_SAMPLES:
        tscore, keywords = text_risk_analysis(s["text"])
        score, verdict = compliance_score(tscore, [], 70)
        ok = verdict in s["expected_verdict_in"]
        if not ok:
            failures.append(f"  {s['label']}: got '{verdict}' ({score}), expected {s['expected_verdict_in']}")

    assert not failures, f"\n{len(failures)} legit message(s) falsely flagged:\n" + "\n".join(failures)


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

@pytest.mark.anyio
@patch("routers.meta.require_user", return_value="mock-report-user")
@patch("routers.meta.persist_report", return_value="mock-report-id")
async def test_report_submission(mock_persist, mock_auth):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/report", json={
            "report_type": "other",
            "value": "test-report@example.com",
            "channel": "email",
            "os": "Android"
        }, headers={"Authorization": "Bearer test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    mock_persist.assert_called_once()

@pytest.mark.anyio
@patch("routers.meta.require_user", return_value="mock-history-user")
async def test_history_returns_structured(mock_auth):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.database.supabase.table") as mock_table:
            mock_scans = [{"id": "s1", "kind": "message", "verdict": "low_risk",
                           "input_text": "hello", "created_at": "2026-01-01T00:00:00Z"}]
            mock_table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=mock_scans)
            mock_table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(count=1)
            resp = await client.get("/api/v1/history", headers={"Authorization": "Bearer test"})
    assert resp.status_code == 200
    data = resp.json()
    assert "counts" in data
    assert "items" in data

@pytest.mark.anyio
@patch("routers.meta.require_user", return_value="mock-scan-user")
@patch("routers.text.require_user", return_value="mock-scan-user")
@patch("routers.text.persist_scan", return_value="mock-scan-id")
@patch("app.database.supabase.table")
async def test_get_scan_by_id(mock_table, mock_persist, mock_text_auth, mock_meta_auth):
    mock_scans = [{"id": "mock-scan-id", "kind": "message", "verdict": "low_risk",
                   "input_text": "test scan for id lookup", "created_at": "2026-01-01T00:00:00Z"}]
    mock_table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=mock_scans)
    mock_table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(count=0)
    mock_table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = MagicMock(count=0)
    mock_table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data={"id": "mock-scan-id", "user_id": "mock-scan-user", "result_json": {"scam_score": 50, "verdict": "low_risk"}}
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/analyze-text", json={
            "text": "test scan for id lookup",
            "os": "Android"
        }, headers={"Authorization": "Bearer test"})
        history = await client.get("/api/v1/history", headers={"Authorization": "Bearer test"})
        assert history.status_code == 200
        items = history.json()["items"]
        assert len(items) > 0
        scan_id = items[0]["scan_id"]
        resp = await client.get(f"/api/v1/scan/{scan_id}", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
