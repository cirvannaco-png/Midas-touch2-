"""Tests for app.copy_trading.can_copy and, critically, for the claim that
signal ingestion (POST /signal) is completely unaffected by the copy-trading
switch in either direction."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.copy_trading import can_copy
from app.database import async_session
from app.models import SUBSCRIBER_STATUS_ACTIVE
from app.settings_store import set_copy_trading_enabled
from app.subscriptions import get_or_create_subscriber
from tests.conftest import VALID_BUY_SIGNAL


@pytest.fixture(autouse=True)
def disable_background_outbox_worker():
    """Keep copy-trading protocol tests independent of asynchronous delivery."""
    with patch("app.main.run_outbox_worker", new=AsyncMock()):
        yield


def _run(coro):
    return asyncio.run(coro)


def _make_entitled_subscriber_sync(user_id: str):
    async def _go():
        async with async_session() as session:
            sub = await get_or_create_subscriber(session, user_id, "trader")
            sub.status = SUBSCRIBER_STATUS_ACTIVE
            sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=10)
            await session.commit()
            return sub.id

    return _run(_go())


def test_can_copy_false_when_switch_off_even_if_entitled(client):
    _make_entitled_subscriber_sync("2001")

    async def _go():
        async with async_session() as session:
            from app.subscriptions import get_subscriber_by_user_id

            sub = await get_subscriber_by_user_id(session, "2001")
            await set_copy_trading_enabled(session, False)
            assert await can_copy(session, sub) is False

    _run(_go())


def test_can_copy_false_when_not_entitled_even_if_switch_on(client):
    async def _go():
        async with async_session() as session:
            sub = await get_or_create_subscriber(session, "2002", "unpaid")
            await set_copy_trading_enabled(session, True)
            assert await can_copy(session, sub) is False

    _run(_go())


def test_can_copy_true_only_when_both_hold(client):
    _make_entitled_subscriber_sync("2003")

    async def _go():
        async with async_session() as session:
            from app.subscriptions import get_subscriber_by_user_id

            sub = await get_subscriber_by_user_id(session, "2003")
            await set_copy_trading_enabled(session, True)
            assert await can_copy(session, sub) is True

    _run(_go())


def test_can_copy_false_for_none_subscriber(client):
    async def _go():
        async with async_session() as session:
            await set_copy_trading_enabled(session, True)
            assert await can_copy(session, None) is False

    _run(_go())


# ---------- the invariant the user actually asked for ----------

def test_signal_ingestion_unaffected_by_copy_trading_off(client, auth_headers):
    async def _off():
        async with async_session() as session:
            await set_copy_trading_enabled(session, False)

    _run(_off())

    resp = client.post(
        "/signal",
        json={**VALID_BUY_SIGNAL, "signal_id": "ct-off-1"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_signal_ingestion_unaffected_by_copy_trading_on(client, auth_headers):
    async def _on():
        async with async_session() as session:
            await set_copy_trading_enabled(session, True)

    _run(_on())

    resp = client.post(
        "/signal",
        json={**VALID_BUY_SIGNAL, "signal_id": "ct-on-1"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
