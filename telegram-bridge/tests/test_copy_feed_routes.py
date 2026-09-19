"""Tests for the two new routes.py endpoints: GET /copy/feed and
POST /admin/check-subscriptions."""
import asyncio
from datetime import datetime, timedelta, timezone

from app.database import async_session
from app.models import SUBSCRIBER_STATUS_ACTIVE
from app.settings_store import set_copy_trading_enabled
from app.subscriptions import get_or_create_subscriber
from tests.conftest import VALID_BUY_SIGNAL


def _run(coro):
    return asyncio.run(coro)


def _entitled_subscriber(user_id: str) -> str:
    """Creates an ACTIVE, entitled subscriber and returns their copy-feed key."""
    async def _go():
        async with async_session() as session:
            sub = await get_or_create_subscriber(session, user_id, "feeduser")
            sub.status = SUBSCRIBER_STATUS_ACTIVE
            sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=10)
            sub.copy_feed_api_key = f"key-{user_id}"
            await session.commit()
            return sub.copy_feed_api_key
    return _run(_go())


def test_copy_feed_rejects_unknown_key(client):
    resp = client.get("/copy/feed", headers={"X-Copy-Key": "not-a-real-key"})
    assert resp.status_code == 401


def test_copy_feed_rejects_when_switch_off(client):
    key = _entitled_subscriber("3001")

    async def _off():
        async with async_session() as session:
            await set_copy_trading_enabled(session, False)
    _run(_off())

    resp = client.get("/copy/feed", headers={"X-Copy-Key": key})
    assert resp.status_code == 403


def test_copy_feed_returns_active_signals_when_entitled_and_enabled(client, auth_headers):
    key = _entitled_subscriber("3002")

    async def _on():
        async with async_session() as session:
            await set_copy_trading_enabled(session, True)
    _run(_on())

    client.post("/signal", json={**VALID_BUY_SIGNAL, "signal_id": "feed-sig-1"}, headers=auth_headers)

    # POST /signal durably enqueues delivery; the outbox worker is what
    # promotes the authoritative Signal row from PENDING to ACTIVE.
    from app.signal_outbox import deliver_pending_once
    assert _run(deliver_pending_once()) is True

    resp = client.get("/copy/feed", headers={"X-Copy-Key": key})
    assert resp.status_code == 200
    body = resp.json()
    assert body["copy_trading_enabled"] is True
    assert any(s["signal_id"] == "feed-sig-1" for s in body["signals"])


def test_copy_feed_rejects_lapsed_subscriber(client):
    async def _go():
        async with async_session() as session:
            sub = await get_or_create_subscriber(session, "3003", "lapsed")
            sub.status = SUBSCRIBER_STATUS_ACTIVE
            sub.current_period_end = datetime.now(timezone.utc) - timedelta(days=1)
            sub.copy_feed_api_key = "lapsed-key"
            await set_copy_trading_enabled(session, True)
            await session.commit()
    _run(_go())

    resp = client.get("/copy/feed", headers={"X-Copy-Key": "lapsed-key"})
    assert resp.status_code == 403


def test_admin_check_subscriptions_requires_api_key(client):
    resp = client.post("/admin/check-subscriptions")
    assert resp.status_code in (401, 403, 422)


def test_admin_check_subscriptions_runs(client, auth_headers, monkeypatch):
    from app import telegram

    async def _fake_dm(user_id, text):
        return True

    async def _fake_ban(chat_id, user_id):
        return True

    async def _fake_unban(chat_id, user_id, only_if_banned=True):
        return True

    monkeypatch.setattr(telegram, "send_dm", _fake_dm)
    monkeypatch.setattr(telegram, "ban_chat_member", _fake_ban)
    monkeypatch.setattr(telegram, "unban_chat_member", _fake_unban)

    resp = client.post("/admin/check-subscriptions", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "warned" in body and "expired" in body and "removed" in body
