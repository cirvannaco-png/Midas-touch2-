"""Regression tests for copy-trading entitlement and signal-isolation invariants."""
from datetime import datetime, timedelta, timezone

import pytest

from app.copy_trading import can_copy
from app.database import async_session
from app.models import SUBSCRIBER_STATUS_ACTIVE
from app.routes import SignalRequest, receive_signal
from app.settings_store import set_copy_trading_enabled
from app.subscriptions import get_or_create_subscriber, get_subscriber_by_user_id
from tests.conftest import VALID_BUY_SIGNAL


async def _make_entitled_subscriber(user_id: str):
    async with async_session() as session:
        sub = await get_or_create_subscriber(session, user_id, "trader")
        sub.status = SUBSCRIBER_STATUS_ACTIVE
        sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=10)
        await session.commit()


@pytest.mark.asyncio
async def test_can_copy_false_when_switch_off_even_if_entitled():
    await _make_entitled_subscriber("2001")

    async with async_session() as session:
        sub = await get_subscriber_by_user_id(session, "2001")
        await set_copy_trading_enabled(session, False)
        assert await can_copy(session, sub) is False


@pytest.mark.asyncio
async def test_can_copy_false_when_not_entitled_even_if_switch_on():
    async with async_session() as session:
        sub = await get_or_create_subscriber(session, "2002", "unpaid")
        await set_copy_trading_enabled(session, True)
        assert await can_copy(session, sub) is False


@pytest.mark.asyncio
async def test_can_copy_true_only_when_both_hold():
    await _make_entitled_subscriber("2003")

    async with async_session() as session:
        sub = await get_subscriber_by_user_id(session, "2003")
        await set_copy_trading_enabled(session, True)
        assert await can_copy(session, sub) is True


@pytest.mark.asyncio
async def test_can_copy_false_for_none_subscriber():
    async with async_session() as session:
        await set_copy_trading_enabled(session, True)
        assert await can_copy(session, None) is False


async def _receive_test_signal(session, signal_id: str) -> str:
    """Exercise the real receive_signal coroutine without HTTP-client/event-loop nesting."""
    payload = SignalRequest(**{**VALID_BUY_SIGNAL, "signal_id": signal_id})
    result = await receive_signal(
        request=None,
        payload=payload,
        session=session,
        _auth=True,
        _rate=None,
    )
    return result.status


@pytest.mark.asyncio
async def test_signal_ingestion_unaffected_by_copy_trading_off():
    async with async_session() as session:
        await set_copy_trading_enabled(session, False)
        assert await _receive_test_signal(session, "ct-off-1") == "queued"


@pytest.mark.asyncio
async def test_signal_ingestion_unaffected_by_copy_trading_on():
    async with async_session() as session:
        await set_copy_trading_enabled(session, True)
        assert await _receive_test_signal(session, "ct-on-1") == "queued"
