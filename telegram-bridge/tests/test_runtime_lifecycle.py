"""Runtime lifecycle regression tests for failure-isolated shutdown."""

import asyncio

import pytest

import app.main as main_module


@pytest.mark.asyncio
async def test_lifespan_closes_remaining_resources_when_outbox_worker_fails(monkeypatch):
    calls = []

    async def init_http_client():
        calls.append("http_init")

    async def init_bot():
        calls.append("bot_init")

    async def failed_worker(stop_event):
        calls.append("worker_started")
        raise RuntimeError("simulated outbox worker failure")

    async def shutdown_bot():
        calls.append("bot_shutdown")

    async def close_http_client():
        calls.append("http_close")

    monkeypatch.setattr(main_module, "init_http_client", init_http_client)
    monkeypatch.setattr(main_module, "init_bot", init_bot)
    monkeypatch.setattr(main_module, "run_outbox_worker", failed_worker)
    monkeypatch.setattr(main_module, "shutdown_bot", shutdown_bot)
    monkeypatch.setattr(main_module, "close_http_client", close_http_client)

    app = main_module.create_app()
    async with app.router.lifespan_context(app):
        # Let the deliberately failing background task finish before shutdown.
        await asyncio.sleep(0)

    assert calls == [
        "http_init",
        "bot_init",
        "worker_started",
        "bot_shutdown",
        "http_close",
    ]


@pytest.mark.asyncio
async def test_lifespan_continues_http_cleanup_when_bot_shutdown_fails(monkeypatch):
    calls = []

    async def init_http_client():
        calls.append("http_init")

    async def init_bot():
        calls.append("bot_init")

    async def idle_worker(stop_event):
        await stop_event.wait()

    async def failed_shutdown_bot():
        calls.append("bot_shutdown")
        raise RuntimeError("simulated Telegram teardown failure")

    async def close_http_client():
        calls.append("http_close")

    monkeypatch.setattr(main_module, "init_http_client", init_http_client)
    monkeypatch.setattr(main_module, "init_bot", init_bot)
    monkeypatch.setattr(main_module, "run_outbox_worker", idle_worker)
    monkeypatch.setattr(main_module, "shutdown_bot", failed_shutdown_bot)
    monkeypatch.setattr(main_module, "close_http_client", close_http_client)

    app = main_module.create_app()
    async with app.router.lifespan_context(app):
        pass

    assert calls == ["http_init", "bot_init", "bot_shutdown", "http_close"]
