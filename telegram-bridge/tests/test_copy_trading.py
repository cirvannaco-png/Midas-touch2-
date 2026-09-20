"""Tests for copy-trading gating and signal-ingestion independence."""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.copy_trading import can_copy
from app.database import async_session
from app.models import SUBSCRIBER_STATUS_ACTIVE
from app.settings_store import set_copy_trading_enabled
from app.subscriptions import get_or_create_subscriber
from tests.conftest import VALID_BUY_SIGNAL


def _run(coro):
    return asyncio.run(coro)


@contextmanager
def _http_client():
    """Create the HTTP client only after DB state is prepared."""
    from fastapi.testclient import TestClient

    import app.bot as bot_module
    import app.main as main_module

    async def _offline_init_bot():
        bot_module.application = bot_module._build_application()

    async def _offline_shutdown_bot():
        bot_module.application = None

    with (
        patch("app.routes.send_telegram_message", new=AsyncMock(return_value=42)),
        patch("app.signal_outbox.send_telegram_message", new=AsyncMock(return_value=42)),
        patch.object(main_module, "init_bot", new=_offline_init_bot),
        patch.object(main_module, "shutdown_bot", new=_offline_shutdown_bot),
        patch.object(main_module, "run_outbox_worker", new=AsyncMock()),
        TestClient(main_module.app) as client,
    ):
        yield client


def _make_entitled_subscriber_sync(user_id: str):
    async def _go():
        async with async_session() as session:
            sub = await get_or_create_subscriber(session, user_id, "trader")
            sub.status = SUBSCRIBER_STATUS_ACTIVE
            sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=10)
            await session.commit()
            return sub.id

    return _run(_go())


def test_can_copy_false_when_switch_off_even_if_entitled():
    _make_entitled_subscriber_sync("2001")

    async def _go():
        async with async_session() as session:
            from app.subscriptions import get_subscriber_by_user_id

            sub = await get_subscriber_by_user_id(session, "2001")
            await set_copy_trading_enabled(session, False)
            assert await can_copy(session, sub) is False

    _run(_go())


def test_can_copy_false_when_not_entitled_even_if_switch_on():
    async def _go():
        async with async_session() as session:
            sub = await get_or_create_subscriber(session, "2002", "unpaid")
            await set_copy_trading_enabled(session, True)
            assert await can_copy(session, sub) is False

    _run(_go())


def test_can_copy_true_only_when_both_hold():
    _make_entitled_subscriber_sync("2003")

    async def _go():
        async with async_session() as session:
            from app.subscriptions import get_subscriber_by_user_id

            sub = await get_subscriber_by_user_id(session, "2003")
            await set_copy_trading_enabled(session, True)
            assert await can_copy(session, sub) is True

    _run(_go())


def test_can_copy_false_for_none_subscriber():
    async def _go():
        async with async_session() as session:
            await set_copy_trading_enabled(session, True)
            assert await can_copy(session, None) is False

    _run(_go())


# ---------- the invariant the user actually asked for ----------

def test_signal_ingestion_unaffected_by_copy_trading_off():
    async def _off():
        async with async_session() as session:
            await set_copy_trading_enabled(session, False)

    _run(_off())

    with _http_client() as client:
        resp = client.post(
            "/signal",
            json={**VALID_BUY_SIGNAL, "signal_id": "ct-off-1"},
            headers={"X-API-Key": "test-secret-key"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_signal_ingestion_unaffected_by_copy_trading_on():
    async def _on():
        async with async_session() as session:
            await set_copy_trading_enabled(session, True)

    _run(_on())

    with _http_client() as client:
        resp = client.post(
            "/signal",
            json={**VALID_BUY_SIGNAL, "signal_id": "ct-on-1"},
            headers={"X-API-Key": "test-secret-key"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"