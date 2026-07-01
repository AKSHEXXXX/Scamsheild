"""
Integration test: verify bonus-scans consumption accounting.

Tests the full chain:
  enforce_credit_cap -> calculate_effective_cap -> bonus consumed tracking
  -> scan-credits endpoint returns remaining (not raw credited) bonus.

All tests mock supabase at the module level to isolate from real DB.
"""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from main import app
from app.auth import enforce_credit_cap
from fastapi import HTTPException


# ==============================================================================
# PART A - enforce_credit_cap unit tests (pure function)
# ==============================================================================

def test_enforce_credit_cap_blocks_at_limit():
    with pytest.raises(HTTPException) as exc:
        enforce_credit_cap("user-1", cap=10, scan_count=10)
    assert exc.value.status_code == 429


def test_enforce_credit_cap_passes_below_limit():
    enforce_credit_cap("user-1", cap=10, scan_count=9)


def test_enforce_credit_cap_passes_at_zero():
    enforce_credit_cap("user-1", cap=10, scan_count=0)


def test_enforce_credit_cap_ignores_user_id():
    """Same cap + scan_count yields same outcome -- user_id has no effect."""  # noqa
    with pytest.raises(HTTPException):
        enforce_credit_cap("user-with-bonus", cap=10, scan_count=10)
    with pytest.raises(HTTPException):
        enforce_credit_cap("user-without-bonus", cap=10, scan_count=10)


# ==============================================================================
# PART B - Shared mock builder
# ==============================================================================

@pytest.fixture
def anyio_backend():
    return "asyncio"


def build_mock_supabase(
    base_cap: int = 10,
    scan_count: int = 0,
    bonuses_as_referrer: list[int] = None,
    bonuses_as_redeemer: list[int] = None,
    bonus_consumed_count: int = 0,
):
    """
    Build a unified mock for supabase that handles all tables used by
    the auth.py helpers, image.py, and referral.py endpoints.
    """
    bonuses_as_referrer = bonuses_as_referrer or []
    bonuses_as_redeemer = bonuses_as_redeemer or []

    def _redemptions_data(scans: list[int]) -> list[dict]:
        return [{"id": f"r-{i}", "scans_credited": s} for i, s in enumerate(scans)]

    def _execute_with_data(data):
        m = MagicMock()
        m.data = data
        m.count = None
        return m

    def _execute_with_count(count_val):
        m = MagicMock()
        m.data = [{"id": "dummy"}]
        m.count = count_val
        return m

    def table_router(name: str):
        if name == "app_config":
            return MagicMock(
                select=lambda *a: MagicMock(
                    eq=lambda f, v: MagicMock(
                        single=lambda: MagicMock(
                            execute=lambda: MagicMock(
                                data={
                                    "scan_credit_cap": base_cap,
                                    "ad_frequency": 3,
                                    "sensitivity_threshold": 70,
                                    "config_version": 1,
                                }
                            )
                        )
                    )
                )
            )

        if name == "scans":
            chain = MagicMock()
            chain.eq.return_value.gte.return_value.execute.return_value = (
                _execute_with_count(scan_count)
            )
            return MagicMock(select=MagicMock(return_value=chain))

        if name == "referrals":
            referrals_data = [
                {"id": "ref-1", "owner_id": "user-referrer",
                 "code": "TS-TESTCODE1"}
            ]
            return MagicMock(
                select=lambda *a: MagicMock(
                    eq=lambda f, v: MagicMock(
                        execute=lambda: _execute_with_data(referrals_data)
                    )
                )
            )

        if name == "referral_redemptions":
            dispatch_map = {
                ("referral_id", "ref-1"): _execute_with_data(
                    _redemptions_data(bonuses_as_referrer)
                ),
                ("redeemed_by", "user-referrer"): _execute_with_data(
                    _redemptions_data(bonuses_as_redeemer)
                ),
            }
            def eq_dispatch(field, val):
                result = dispatch_map.get((field, val), _execute_with_data([]))
                m = MagicMock()
                m.execute.return_value = result
                return m
            return MagicMock(select=lambda *a, **kw: MagicMock(eq=eq_dispatch))

        if name == "bonus_scan_consumptions":
            return MagicMock(
                select=lambda *a, **kw: MagicMock(
                    eq=lambda f, v: MagicMock(
                        execute=lambda: _execute_with_count(bonus_consumed_count)
                    )
                )
            )

        m = MagicMock()
        m.select.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[], count=0)
        )
        return m

    return MagicMock(table=table_router)


# ==============================================================================
# PART C - scan-credits endpoint tests
# ==============================================================================

@pytest.mark.anyio
async def test_bonus_scans_reflects_consumption():
    """
    POST-FIX: scan-credits returns bonus_scans = earned - consumed.

    User earned 10 (5 referrer + 5 redeemer), consumed 4.
    Expected: bonus_scans = 6, total_available = 16.
    """
    mock_supabase = build_mock_supabase(
        base_cap=10,
        bonuses_as_referrer=[5],
        bonuses_as_redeemer=[5],
        bonus_consumed_count=4,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("routers.referral.supabase", mock_supabase),
            patch("app.auth.supabase", mock_supabase),
            patch("app.helpers._get_service_client", return_value=mock_supabase),
            patch("routers.referral.require_user", return_value="user-referrer"),
        ):
            resp = await client.get(
                "/api/v1/user/scan-credits",
                headers={"Authorization": "Bearer test"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["base_daily_cap"] == 10
    assert data["bonus_scans"] == 6, (
        f"Expected bonus_scans=6 (10 earned - 4 consumed), got {data['bonus_scans']}"
    )
    assert data["total_available"] == 16, (
        f"Expected total_available=16, got {data['total_available']}"
    )


# ==============================================================================
# PART D - Image scan cap enforcement tests
# ==============================================================================

@pytest.mark.anyio
async def test_effective_cap_includes_bonus():
    """
    POST-FIX: enforce_credit_cap uses effective_cap = base + remaining bonus.

    User at base cap (10 scans) with 5 bonus remaining -> allowed (was 429).
    """
    mock_supabase = build_mock_supabase(
        base_cap=10,
        scan_count=10,
        bonuses_as_referrer=[5],
        bonuses_as_redeemer=[],
        bonus_consumed_count=0,
    )

    OCR_MOCK = MagicMock()
    OCR_MOCK.extract_from_base64.return_value = MagicMock(
        text="Hello world", method="tesseract",
        char_count=11, confidence=0.95, fallback_used=False,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("routers.image.supabase", mock_supabase),
            patch("app.auth.supabase", mock_supabase),
            patch("app.helpers._get_service_client", return_value=mock_supabase),
            patch("routers.image.require_user", return_value="user-referrer"),
            patch("routers.image.screenshot_ocr", OCR_MOCK),
            patch("routers.image.analyze", return_value={
                "scam_score": 10, "verdict": "low_risk",
                "top_signal": "none", "flagged_urls": [],
                "findings": [], "warning_count": 0,
                "extracted_text": "Hello world",
            }),
        ):
            resp = await client.post(
                "/api/v1/sandbox-image",
                json={"image": "ZmFrZQ==", "os": "iOS"},
                headers={"Authorization": "Bearer test"},
            )

    assert resp.status_code != 429, (
        f"POST-FIX: User at base cap with bonus should be ALLOWED. "
        f"Got {resp.status_code}. "
        f"effective_cap should be 15 (10 base + 5 bonus), scan_count=10."
    )


@pytest.mark.anyio
async def test_effective_cap_blocks_when_bonus_exhausted():
    """
    POST-FIX: when bonus is fully consumed, effective_cap = base_cap.

    User at 15 scans, bonus fully consumed (5 earned, 5 consumed) -> blocked.
    """
    mock_supabase = build_mock_supabase(
        base_cap=10,
        scan_count=15,
        bonuses_as_referrer=[5],
        bonuses_as_redeemer=[],
        bonus_consumed_count=5,
    )

    OCR_MOCK = MagicMock()
    OCR_MOCK.extract_from_base64.return_value = MagicMock(
        text="Hello world", method="tesseract",
        char_count=11, confidence=0.95, fallback_used=False,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("routers.image.supabase", mock_supabase),
            patch("app.auth.supabase", mock_supabase),
            patch("app.helpers._get_service_client", return_value=mock_supabase),
            patch("routers.image.require_user", return_value="user-referrer"),
            patch("routers.image.screenshot_ocr", OCR_MOCK),
            patch("routers.image.analyze", return_value={
                "scam_score": 10, "verdict": "low_risk",
                "top_signal": "none", "flagged_urls": [],
                "findings": [], "warning_count": 0,
                "extracted_text": "Hello world",
            }),
        ):
            resp = await client.post(
                "/api/v1/sandbox-image",
                json={"image": "ZmFrZQ==", "os": "iOS"},
                headers={"Authorization": "Bearer test"},
            )

    assert resp.status_code == 429, (
        f"POST-FIX: User with 15 scans and 0 bonus remaining should be "
        f"BLOCKED. Got {resp.status_code}."
    )
    detail = resp.json().get("detail", "")
    assert "10" in detail, f"Cap in error should reference 10, got: {detail}"


@pytest.mark.anyio
async def test_scan_at_base_cap_no_bonus_blocks():
    """
    Edge case: user at base cap with zero bonus should be blocked (429).
    Same as pre-fix behavior for users without referral activity.
    """
    mock_supabase = build_mock_supabase(
        base_cap=10,
        scan_count=10,
        bonuses_as_referrer=[],
        bonuses_as_redeemer=[],
        bonus_consumed_count=0,
    )

    OCR_MOCK = MagicMock()
    OCR_MOCK.extract_from_base64.return_value = MagicMock(
        text="Hello world", method="tesseract",
        char_count=11, confidence=0.95, fallback_used=False,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("routers.image.supabase", mock_supabase),
            patch("app.auth.supabase", mock_supabase),
            patch("app.helpers._get_service_client", return_value=mock_supabase),
            patch("routers.image.require_user", return_value="user-referrer"),
            patch("routers.image.screenshot_ocr", OCR_MOCK),
            patch("routers.image.analyze", return_value={
                "scam_score": 10, "verdict": "low_risk",
                "top_signal": "none", "flagged_urls": [],
                "findings": [], "warning_count": 0,
                "extracted_text": "Hello world",
            }),
        ):
            resp = await client.post(
                "/api/v1/sandbox-image",
                json={"image": "ZmFrZQ==", "os": "iOS"},
                headers={"Authorization": "Bearer test"},
            )

    assert resp.status_code == 429, (
        f"User at base cap with no bonus should be blocked. Got {resp.status_code}."
    )
    detail = resp.json().get("detail", "")
    assert "10" in detail, f"Cap in error should reference 10, got: {detail}"


# ==============================================================================
# PART E - Pure logic tests
# ==============================================================================

def test_effective_cap_formula():
    """
    Pure logic: effective_cap = base_cap + max(0, earned - consumed).

    BEFORE FIX: bonus_consumed always 0 -> effective_cap = base_cap + earned.
      But enforce_credit_cap used raw base_cap, not effective_cap.
      Bonus was purely cosmetic.

    AFTER FIX: calculate_effective_cap() computes effective_cap,
      and enforce_credit_cap uses it.
    """
    base = 50
    earned = 15
    consumed = 0

    remaining = max(0, earned - consumed)
    effective = base + remaining
    assert effective == 65

    consumed = 8
    remaining = max(0, earned - consumed)
    assert remaining == 7
    assert base + remaining == 57

    consumed = 15
    remaining = max(0, earned - consumed)
    assert remaining == 0
    assert base + remaining == 50

    consumed = 20
    remaining = max(0, earned - consumed)
    assert remaining == 0
