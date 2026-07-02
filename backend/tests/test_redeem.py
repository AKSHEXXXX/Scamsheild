"""Tests for POST /api/v1/referral/redeem error codes and response shape."""
import pytest
from fastapi import HTTPException, Header
from routers.referral import redeem_referral, RedeemRequest


class MockResult:
    def __init__(self, data):
        self.data = data


class MockSupabase:
    def __init__(self, scenario):
        self.scenario = scenario
        self.call_count = 0

    def table(self, name):
        return self

    def select(self, *args, **kwargs):
        return self

    def eq(self, key, value):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        self.call_count += 1
        if self.scenario == "invalid_code":
            if self.call_count == 1:
                return MockResult(None)
        elif self.scenario == "own_code":
            if self.call_count == 1:
                return MockResult({"code": "TS-OWNCODE", "owner_id": "user_self"})
        elif self.scenario == "already_redeemed":
            if self.call_count == 1:
                return MockResult({"code": "TS-VALID", "owner_id": "user_other"})
            if self.call_count == 2:
                return MockResult({"id": "existing_redemption"})
        elif self.scenario == "success":
            if self.call_count == 1:
                return MockResult({"id": "ref_uuid", "code": "TS-VALID", "owner_id": "user_other"})
            if self.call_count == 2:
                return MockResult(None)
        return MockResult({})

    def insert(self, data):
        return self

    def __getattr__(self, name):
        return self


def _auth(user_id: str = "user_self"):
    return "Bearer valid"


def test_redeem_invalid_code_returns_404(monkeypatch):
    sb = MockSupabase("invalid_code")
    monkeypatch.setattr("routers.referral.supabase", sb)
    monkeypatch.setattr("routers.referral.require_user", lambda a: "user_self")
    with pytest.raises(HTTPException) as exc:
        redeem_referral(RedeemRequest(referral_code="TS-BADCODE"), "Bearer valid")
    assert exc.value.status_code == 404
    assert "Invalid referral code" in str(exc.value.detail)


def test_redeem_own_code_returns_400(monkeypatch):
    sb = MockSupabase("own_code")
    monkeypatch.setattr("routers.referral.supabase", sb)
    monkeypatch.setattr("routers.referral.require_user", lambda a: "user_self")
    with pytest.raises(HTTPException) as exc:
        redeem_referral(RedeemRequest(referral_code="TS-OWNCODE"), "Bearer valid")
    assert exc.value.status_code == 400
    assert "Cannot redeem your own code" in str(exc.value.detail)


def test_redeem_already_redeemed_returns_409(monkeypatch):
    sb = MockSupabase("already_redeemed")
    monkeypatch.setattr("routers.referral.supabase", sb)
    monkeypatch.setattr("routers.referral.require_user", lambda a: "user_self")
    with pytest.raises(HTTPException) as exc:
        redeem_referral(RedeemRequest(referral_code="TS-USED"), "Bearer valid")
    assert exc.value.status_code == 409
    assert "Already redeemed" in str(exc.value.detail)


def test_redeem_success_response_shape(monkeypatch):
    sb = MockSupabase("success")
    monkeypatch.setattr("routers.referral.supabase", sb)
    monkeypatch.setattr("routers.referral.require_user", lambda a: "user_self")
    result = redeem_referral(RedeemRequest(referral_code="TS-VALID"), "Bearer valid")
    assert "bonus_scans_credited" in result
    assert result["bonus_scans_credited"] == 5
