import os
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
    # 0.6*60 + 0.4*100 = 76 >= 70
    score, verdict = compliance_score(60, flagged, 70)
    assert verdict == "high_risk"
    assert score >= 70

def test_impersonation_boost_alone_stays_low():
    """A single .con typosquat with no other signals should NOT reach high_risk."""
    from app.scoring import compliance_score
    score, verdict = compliance_score(0, [], 70, impersonation_boost=25)
    assert score <= 25
    assert verdict == "low_risk"

def test_impersonation_boost_clamped_at_100():
    """Score with boost must never exceed 100."""
    from app.scoring import compliance_score
    flagged = [{"url": "http://evil.com", "final_url": "http://evil.com", "reputation": "malicious"}]
    score, verdict = compliance_score(100, flagged, 70, impersonation_boost=25)
    assert score == 100

def test_labeled_split_all_scams_detected():
    """Every known-scam sample must return high_risk or suspicious (never low_risk)."""
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
    """Every known-legitimate sample must return low_risk (never high/suspicious)."""
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
