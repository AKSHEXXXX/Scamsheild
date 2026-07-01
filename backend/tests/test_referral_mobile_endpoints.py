import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _result(data=None, count=None):
    m = MagicMock()
    m.data = data if data is not None else []
    m.count = count
    return m


def build_mobile_referral_supabase(existing_redeem: bool = False):
    notifications_rows = [
        {
            "id": "n-1",
            "kind": "referral_reward",
            "title": "Referral Reward Earned!",
            "body": "You earned 5 bonus scans!",
            "read": False,
            "created_at": "2026-07-01T10:00:00Z",
        },
        {
            "id": "n-2",
            "kind": "info",
            "title": "Welcome",
            "body": "Thanks for joining",
            "read": True,
            "created_at": "2026-07-01T09:00:00Z",
        },
    ]

    def table_router(name: str):
        if name == "referrals":
            class ReferralsSelectChain:
                def __init__(self):
                    self.field = None
                    self.value = None

                def eq(self, field, value):
                    self.field = field
                    self.value = value
                    return self

                def maybe_single(self):
                    return self

                def execute(self):
                    if self.field == "code" and self.value == "TS-VALID123":
                        return _result({"id": "ref-1", "owner_id": "ref-owner", "code": "TS-VALID123"})
                    if self.field == "id" and self.value == "ref-1":
                        return _result({"id": "ref-1", "owner_id": "ref-owner", "code": "TS-VALID123"})
                    return _result(None)

            return MagicMock(select=lambda *a, **k: ReferralsSelectChain())

        if name == "referral_redemptions":
            class RedemptionsSelectChain:
                def __init__(self):
                    self.field = None
                    self.value = None

                def eq(self, field, value):
                    self.field = field
                    self.value = value
                    return self

                def maybe_single(self):
                    return self

                def execute(self):
                    if self.field == "redeemed_by":
                        if existing_redeem:
                            return _result({
                                "id": "red-1",
                                "referral_id": "ref-1",
                                "redeemed_at": "2026-06-30T10:00:00Z",
                                "scans_credited": 5,
                            })
                        return _result(None)
                    return _result(None)

            return MagicMock(select=lambda *a, **k: RedemptionsSelectChain())

        if name == "notifications":
            class NotificationsSelectChain:
                def __init__(self):
                    self.only_unread = False

                def eq(self, field, value):
                    if field == "read" and value is False:
                        self.only_unread = True
                    return self

                def order(self, *a, **k):
                    return self

                def limit(self, _n):
                    return self

                def execute(self):
                    if self.only_unread:
                        return _result([n for n in notifications_rows if not n["read"]])
                    return _result(notifications_rows)

            class NotificationsUpdateChain:
                def eq(self, *a, **k):
                    return self

                def execute(self):
                    return _result([])

            return MagicMock(
                select=lambda *a, **k: NotificationsSelectChain(),
                update=lambda *a, **k: NotificationsUpdateChain(),
            )

        default = MagicMock()
        default.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = _result(None)
        return default

    return MagicMock(table=table_router)


@pytest.mark.anyio
async def test_validate_referral_can_redeem():
    mock_supabase = build_mobile_referral_supabase(existing_redeem=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("routers.referral.supabase", mock_supabase),
            patch("routers.referral.require_user", return_value="new-user"),
        ):
            resp = await client.get(
                "/api/v1/referral/validate/TS-VALID123",
                headers={"Authorization": "Bearer test"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["can_redeem"] is True
    assert body["reason"] == "ok"


@pytest.mark.anyio
async def test_redemption_status_reports_existing_redemption():
    mock_supabase = build_mobile_referral_supabase(existing_redeem=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("routers.referral.supabase", mock_supabase),
            patch("routers.referral.require_user", return_value="new-user"),
        ):
            resp = await client.get(
                "/api/v1/referral/redemption-status",
                headers={"Authorization": "Bearer test"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["has_redeemed"] is True
    assert body["scans_credited"] == 5
    assert body["referral_code"] == "TS-VALID123"


@pytest.mark.anyio
async def test_notifications_list_and_mark_read():
    mock_supabase = build_mobile_referral_supabase(existing_redeem=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("routers.referral.supabase", mock_supabase),
            patch("routers.referral.require_user", return_value="new-user"),
        ):
            list_resp = await client.get(
                "/api/v1/notifications?unread_only=true",
                headers={"Authorization": "Bearer test"},
            )
            mark_one_resp = await client.post(
                "/api/v1/notifications/n-1/read",
                headers={"Authorization": "Bearer test"},
            )
            mark_all_resp = await client.post(
                "/api/v1/notifications/read-all",
                headers={"Authorization": "Bearer test"},
            )

    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert len(list_body["items"]) == 1
    assert list_body["unread_count"] == 1
    assert mark_one_resp.status_code == 200
    assert mark_one_resp.json()["ok"] is True
    assert mark_all_resp.status_code == 200
    assert mark_all_resp.json()["ok"] is True


@pytest.mark.anyio
async def test_referral_scan_credits_alias_matches_user_scan_credits():
    mock_supabase = MagicMock()

    app_config_chain = MagicMock()
    app_config_chain.eq.return_value.single.return_value.execute.return_value = _result(
        {
            "scan_credit_cap": 50,
            "ad_frequency": 10,
            "sensitivity_threshold": 70,
            "config_version": 1,
        }
    )

    referral_redemptions_chain = MagicMock()
    referral_redemptions_chain.eq.return_value.execute.return_value = _result([])

    bonus_consumptions_chain = MagicMock()
    bonus_consumptions_chain.eq.return_value.execute.return_value = _result([], count=0)

    def table_router(name: str):
        if name == "app_config":
            return MagicMock(select=lambda *a, **k: app_config_chain)
        if name == "referrals":
            return MagicMock(select=lambda *a, **k: MagicMock(eq=lambda *x, **y: MagicMock(execute=lambda: _result([]))))
        if name == "referral_redemptions":
            return MagicMock(select=lambda *a, **k: referral_redemptions_chain)
        if name == "bonus_scan_consumptions":
            return MagicMock(select=lambda *a, **k: bonus_consumptions_chain)
        return MagicMock()

    mock_supabase.table.side_effect = table_router

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("routers.referral.supabase", mock_supabase),
            patch("app.auth.supabase", mock_supabase),
            patch("app.helpers._get_service_client", return_value=mock_supabase),
            patch("routers.referral.require_user", return_value="new-user"),
        ):
            alias_resp = await client.get(
                "/api/v1/referral/scan-credits",
                headers={"Authorization": "Bearer test"},
            )
            base_resp = await client.get(
                "/api/v1/user/scan-credits",
                headers={"Authorization": "Bearer test"},
            )

    assert alias_resp.status_code == 200
    assert base_resp.status_code == 200
    assert alias_resp.json() == base_resp.json()


@pytest.mark.anyio
async def test_public_invite_lookup_valid_code():
    mock_supabase = build_mobile_referral_supabase(existing_redeem=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("routers.referral.supabase", mock_supabase):
            resp = await client.get("/api/v1/invite/TS-VALID123")

    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["referral_code"] == "TS-VALID123"
    assert body["deep_link"] == "trustscan://invite/TS-VALID123"
