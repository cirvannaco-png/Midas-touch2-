"""Regression tests for copy-feed entitlement and subscription enforcement."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.database import async_session
from app.models import SUBSCRIBER_STATUS_ACTIVE
from app.routes import SignalRequest, check_subscriptions, get_copy_feed, receive_signal
from app.settings_store import set_copy_trading_enabled
from app.signal_outbox import deliver_pending_once
from app.subscriptions import get_or_create_subscriber
from tests.conftest import VALID_BUY_SIGNAL


async def _entitled_subscriber(user_id: str) -> str:
    async with async_session() as session:
        sub = await get_or_create_subscriber(session, user_id, "feeduser")
        sub.status = SUBSCRIBER_STATUS_ACTIVE
        sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=10)
        sub.copy_feed_api_key = f"key-{user_id}"
        await session.commit()
        return sub.copy_feed_api_key


@pytest.mark.asyncio
async def test_copy_feed_rejects_unknown_key():
    async with async_session() as session:
        with pytest.raises(HTTPException) as exc:
            await get_copy_feed("not-a-real-key", session)
        assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_copy_feed_rejects_when_switch_off():
    key = await _entitled_subscriber("3001")

    async with async_session() as session:
        await set_copy_trading_enabled(session, False)
        with pytest.raises(HTTPException) as exc:
            await get_copy_feed(key, session)
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_copy_feed_returns_active_signals_when_entitled_and_enabled():
    key = await _entitled_subscriber("3002")

    async with async_session() as session:
        await set_copy_trading_enabled(session, True)
        payload = dict(VALID_BUY_SIGNAL, signal_id="feed-sig-1")
        result = await receive_signal(
            request=None,
            payload=SignalRequest(**payload),
            session=session,
            _auth=True,
            _rate=None,
        )
        assert result.status == "queued"

    # The outbox worker promotes the authoritative Signal row from PENDING to ACTIVE.
    assert await deliver_pending_once() is True

    async with async_session() as session:
        response = await get_copy_feed(key, session)
    assert response.copy_trading_enabled is True
    assert any(signal.signal_id == "feed-sig-1" for signal in response.signals)


@pytest.mark.asyncio
async def test_copy_feed_rejects_lapsed_subscriber():
    async with async_session() as session:
        sub = await get_or_create_subscriber(session, "3003", "lapsed")
        sub.status = SUBSCRIBER_STATUS_ACTIVE
        sub.current_period_end = datetime.now(timezone.utc) - timedelta(days=1)
        sub.copy_feed_api_key = "lapsed-key"
        await set_copy_trading_enabled(session, True)
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await get_copy_feed("lapsed-key", session)
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_check_subscriptions_runs(monkeypatch):
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

    result = await check_subscriptions(_auth=True)
    assert "warned" in result and "expired" in result and "removed" in result
