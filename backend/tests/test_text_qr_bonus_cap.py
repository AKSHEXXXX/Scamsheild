"""
Integration test: verify bonus-scans consumption accounting on the
text (/api/v1/analyze-text) and QR (/api/v1/check-qr) endpoints.

Mirrors tests/test_referral_bonus.py Part D (image cap enforcement),
applied to the two endpoints that previously had NO cap enforcement
at all (calculate_effective_cap / enforce_credit_cap / record_bonus_consumption
were never called in text.py or qr.py before this fix).

All tests mock supabase at the module level to isolate from the real DB.
"""
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from main import app
from tests.test_referral_bonus import build_mock_supabase


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ==============================================================================
# TEXT endpoint (/api/v1/analyze-text)
# ==============================================================================

@pytest.mark.anyio
async def test_text_effective_cap_includes_bonus():
    """
    POST-FIX: user at base cap (10 scans) with 5 bonus remaining -> allowed.
    PRE-FIX: analyze-text never checked any cap at all, so this always passed
    for the wrong reason. This test pins the correct (bonus-aware) behavior.
    """
    mock_supabase = build_mock_supabase(
        base_cap=10, scan_count=10,
        bonuses_as_referrer=[5], bonuses_as_redeemer=[], bonus_consumed_count=0,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("routers.text.supabase", mock_supabase),
            patch("app.auth.supabase", mock_supabase),
            patch("app.helpers._get_service_client", return_value=mock_supabase),
            patch("routers.text.require_user", return_value="user-referrer"),
        ):
            resp = await client.post(
                "/api/v1/analyze-text",
                json={"text": "hello there, how are you doing today", "os": "Android"},
                headers={"Authorization": "Bearer test"},
            )
    assert resp.status_code != 429, (
        f"User at base cap with bonus should be ALLOWED. Got {resp.status_code}. "
        f"effective_cap should be 15 (10 base + 5 bonus), scan_count=10."
    )


@pytest.mark.anyio
async def test_text_effective_cap_blocks_when_bonus_exhausted():
    """
    POST-FIX: user over cap (15 scans) with bonus fully consumed (5 earned,
    5 consumed) -> blocked (429).
    """
    mock_supabase = build_mock_supabase(
        base_cap=10, scan_count=15,
        bonuses_as_referrer=[5], bonuses_as_redeemer=[], bonus_consumed_count=5,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("routers.text.supabase", mock_supabase),
            patch("app.auth.supabase", mock_supabase),
            patch("app.helpers._get_service_client", return_value=mock_supabase),
            patch("routers.text.require_user", return_value="user-referrer"),
        ):
            resp = await client.post(
                "/api/v1/analyze-text",
                json={"text": "hello there, how are you doing today", "os": "Android"},
                headers={"Authorization": "Bearer test"},
            )
    assert resp.status_code == 429, (
        f"User with 15 scans and 0 bonus remaining should be BLOCKED. "
        f"Got {resp.status_code}."
    )
    detail = resp.json().get("detail", "")
    assert "10" in detail, f"Cap in error should reference 10, got: {detail}"


@pytest.mark.anyio
async def test_text_regression_no_cap_was_ever_enforced():
    """
    Regression guard for the exact bug reported: pre-fix, analyze-text had
    NO cap check at all, so a user with an absurd scan_count (999) and zero
    bonus was never blocked. Confirms the gap is closed.
    """
    mock_supabase = build_mock_supabase(
        base_cap=10, scan_count=999,
        bonuses_as_referrer=[], bonuses_as_redeemer=[], bonus_consumed_count=0,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("routers.text.supabase", mock_supabase),
            patch("app.auth.supabase", mock_supabase),
            patch("app.helpers._get_service_client", return_value=mock_supabase),
            patch("routers.text.require_user", return_value="user-referrer"),
        ):
            resp = await client.post(
                "/api/v1/analyze-text",
                json={"text": "hello there, how are you doing today", "os": "Android"},
                headers={"Authorization": "Bearer test"},
            )
    assert resp.status_code == 429


# ==============================================================================
# QR endpoint (/api/v1/check-qr)
# ==============================================================================

@pytest.mark.anyio
async def test_qr_effective_cap_includes_bonus():
    """POST-FIX: user at base cap (10) with 5 bonus remaining -> allowed."""
    mock_supabase = build_mock_supabase(
        base_cap=10, scan_count=10,
        bonuses_as_referrer=[5], bonuses_as_redeemer=[], bonus_consumed_count=0,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("routers.qr.supabase", mock_supabase),
            patch("app.auth.supabase", mock_supabase),
            patch("app.helpers._get_service_client", return_value=mock_supabase),
            patch("routers.qr.require_user", return_value="user-referrer"),
        ):
            resp = await client.post(
                "/api/v1/check-qr",
                json={"payload": "https://www.google.com", "os": "Android"},
                headers={"Authorization": "Bearer test"},
            )
    assert resp.status_code != 429, (
        f"User at base cap with bonus should be ALLOWED. Got {resp.status_code}. "
        f"effective_cap should be 15 (10 base + 5 bonus), scan_count=10."
    )


@pytest.mark.anyio
async def test_qr_effective_cap_blocks_when_bonus_exhausted():
    """POST-FIX: user over cap with bonus fully consumed -> blocked (429)."""
    mock_supabase = build_mock_supabase(
        base_cap=10, scan_count=15,
        bonuses_as_referrer=[5], bonuses_as_redeemer=[], bonus_consumed_count=5,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("routers.qr.supabase", mock_supabase),
            patch("app.auth.supabase", mock_supabase),
            patch("app.helpers._get_service_client", return_value=mock_supabase),
            patch("routers.qr.require_user", return_value="user-referrer"),
        ):
            resp = await client.post(
                "/api/v1/check-qr",
                json={"payload": "https://www.google.com", "os": "Android"},
                headers={"Authorization": "Bearer test"},
            )
    assert resp.status_code == 429, (
        f"User with 15 scans and 0 bonus remaining should be BLOCKED. "
        f"Got {resp.status_code}."
    )
    detail = resp.json().get("detail", "")
    assert "10" in detail, f"Cap in error should reference 10, got: {detail}"


@pytest.mark.anyio
async def test_qr_regression_no_cap_was_ever_enforced():
    """
    Regression guard for the exact bug reported: pre-fix, check-qr had NO
    cap check at all. Confirms the gap is closed.
    """
    mock_supabase = build_mock_supabase(
        base_cap=10, scan_count=999,
        bonuses_as_referrer=[], bonuses_as_redeemer=[], bonus_consumed_count=0,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("routers.qr.supabase", mock_supabase),
            patch("app.auth.supabase", mock_supabase),
            patch("app.helpers._get_service_client", return_value=mock_supabase),
            patch("routers.qr.require_user", return_value="user-referrer"),
        ):
            resp = await client.post(
                "/api/v1/check-qr",
                json={"payload": "https://www.google.com", "os": "Android"},
                headers={"Authorization": "Bearer test"},
            )
    assert resp.status_code == 429
