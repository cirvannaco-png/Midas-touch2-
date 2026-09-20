
@pytest.fixture()
def client():
    """TestClient with Telegram sends mocked; persisted rows are cleared per test."""
    with (
        patch("app.routes.send_telegram_message", new=AsyncMock(return_value=42)),
        patch("app.signal_outbox.send_telegram_message", new=AsyncMock(return_value=42)),
    ):
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