import asyncio
import os

# Must be set before app.config.settings is constructed.
os.environ.setdefault("BOT_TOKEN", "123456:test-token")
os.environ.setdefault("CHAT_ID", "-1000000000")
os.environ.setdefault("ADMIN_CHAT_ID", "777000777")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("WEBHOOK_SECRET_TOKEN", "test-webhook-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_signals.db")
os.environ.setdefault("RATE_LIMIT_MAX_REQUESTS", "5")
os.environ.setdefault("RATE_LIMIT_WINDOW_SECONDS", "60")

from unittest.mock import AsyncMock, patch

import pytest

VALID_BUY_SIGNAL = {
    "signal_id": "test-signal-1", "symbol": "EURUSD", "direction": "BUY",
    "entry": 1.1000, "sl": 1.0950, "tp1": 1.1050, "tp2": 1.1100,
    "confidence": 80, "reasons": ["structure break confirmed", "liquidity sweep"], "timeframe": "M15",
}

VALID_TRADE_OPENED = {
    "event_id": "1000123:opened", "trade_id": "1000123", "signal_id": "test-signal-1",
    "symbol": "EURUSD", "direction": "BUY", "event": "opened", "volume": 0.10,
    "price": 1.1002, "sl": 1.0950, "tp1": 1.1050, "tp2": 1.1100,
}


@pytest.fixture(scope="session", autouse=True)
def _create_test_tables():
    """Create a deterministic, isolated SQLite schema for the test session.

    The CI script runs each test_*.py as a separate pytest process, so this
    session-scoped fixture fires once per file. Deleting the DB file before
    create_all avoids stale SQLite indexes surviving across processes.
    """
    import app.models  # noqa: F401 - register all models on Base.metadata
    from app.database import Base, engine

    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("sqlite"):
        db_path = db_url.split("///", 1)[-1]
        if db_path and db_path != ":memory:" and os.path.exists(db_path):
            os.remove(db_path)

    async def _setup():
        await engine.dispose()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_setup())


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from app.ratelimit import rate_limiter
    rate_limiter._buckets.clear()
    yield
    rate_limiter._buckets.clear()


@pytest.fixture()
def forced_rate_limit():
    from app.ratelimit import rate_limiter
    original = (rate_limiter.enabled, rate_limiter.max_requests, rate_limiter.window_seconds)
    rate_limiter.enabled = True
    rate_limiter.max_requests = 5
    rate_limiter.window_seconds = 60
    rate_limiter._buckets.clear()
    try:
        yield rate_limiter
    finally:
        rate_limiter.enabled, rate_limiter.max_requests, rate_limiter.window_seconds = original
        rate_limiter._buckets.clear()


@pytest.fixture()
def client():
    """TestClient with Telegram sends mocked; persisted rows are cleared per test."""
    with patch("app.routes.send_telegram_message", new=AsyncMock(return_value=42)), patch("app.signal_outbox.send_telegram_message", new=AsyncMock(return_value=42)):
        from fastapi.testclient import TestClient

        import app.bot as bot_module
        import app.main as main_module
        from app.config_evaluation_model import ConfigurationEvaluation
        from app.config_registry_model import ConfigurationRegistry
        from app.config_sync_state_model import ConfigSyncState
        from app.database import engine
        from app.main import app

        async def _offline_init_bot():
            # Build the real handler graph, but do not initialize the Telegram
            # client or call api.telegram.org. CI tests the webhook routing and
            # handlers; Telegram transport is covered by isolated mocks.
            bot_module.application = bot_module._build_application()

        async def _offline_shutdown_bot():
            bot_module.application = None

        main_module.check_bot_token = AsyncMock(return_value=True)
        main_module.init_bot = _offline_init_bot
        main_module.shutdown_bot = _offline_shutdown_bot
        from app.models import BotSetting, Payment, Signal, SignalDeliveryOutbox, Subscriber, TradeEvent

        with TestClient(app) as c:
            yield c

        async def _truncate():
            await engine.dispose()
            async with engine.begin() as conn:
                for model in (
                    ConfigurationEvaluation, ConfigSyncState, ConfigurationRegistry,
                    Signal, SignalDeliveryOutbox, TradeEvent, BotSetting, Payment, Subscriber,
                ):
                    await conn.run_sync(lambda sync_conn, table=model.__table__: sync_conn.execute(table.delete()))
            await engine.dispose()

        asyncio.run(_truncate())


@pytest.fixture()
def auth_headers():
    return {"X-API-Key": os.environ["SECRET_KEY"]}
