"""Structural regression tests for the staged Phase B API seams."""


def test_phase_b_boundary_modules_import_without_registering_routes():
    from app.api import admin, outcomes, signals, trades, webhook

    assert admin.__all__ == []
    assert callable(signals.validate_signal_request)
    assert callable(trades.validate_trade_request)
    assert callable(webhook.validate_telegram_webhook_secret)
    assert outcomes.OUTCOME_MODEL.__name__ == "SignalOutcome"


def test_copy_feed_boundary_preserves_existing_http_status_contract():
    from unittest.mock import AsyncMock

    import pytest
    from fastapi import HTTPException

    from app.api.copy_feed import (
        authorize_copy_feed_request,
    )
    from app.services.copy_authorization import (
        CopyFeedKeyUnknown,
        CopyFeedNotEntitled,
    )

    async def _unknown(*_args):
        raise CopyFeedKeyUnknown()

    async def _denied(*_args):
        raise CopyFeedNotEntitled()

    async def _check(fn, expected):
        import app.api.copy_feed as boundary
        original = boundary.authorize_copy_feed
        boundary.authorize_copy_feed = fn
        try:
            with pytest.raises(HTTPException) as exc:
                await authorize_copy_feed_request(AsyncMock(), "key")
            assert exc.value.status_code == expected
        finally:
            boundary.authorize_copy_feed = original

    import asyncio
    asyncio.run(_check(_unknown, 401))
    asyncio.run(_check(_denied, 403))
