"""Tests for app.copytrading_admin: the on/off/status command, the
"yes"-confirmation gate for turning it ON, and /checkpayments.

Mirrors tests/test_settings_store.py's direct-handler-invocation pattern
(fake Update/Context) rather than going through the real Telegram webhook,
for the same reason documented there.
"""
import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

from app.copytrading_admin import checkpayments_command, confirm_text_handler, copytrading_command
from app.database import async_session
from app.settings_store import is_copy_trading_enabled

AUTHORIZED_USER_ID = int(os.environ["ADMIN_CHAT_ID"])
UNAUTHORIZED_USER_ID = 999999999


@pytest.fixture(autouse=True)
def disable_background_outbox_worker():
    """Keep direct Telegram-admin protocol tests independent of the delivery worker."""
    with patch("app.main.run_outbox_worker", new=AsyncMock()):
        yield


class _FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.replies: list[str] = []

    async def reply_text(self, text):
        self.replies.append(text)


class _FakeChat:
    def __init__(self, chat_id):
        self.id = chat_id


class _FakeUser:
    def __init__(self, user_id):
        self.id = user_id


class _FakeUpdate:
    def __init__(self, user_id=AUTHORIZED_USER_ID, text=""):
        self.effective_chat = _FakeChat(user_id)
        self.effective_user = _FakeUser(user_id)
        self.message = _FakeMessage(text)


class _FakeContext:
    def __init__(self, args=None):
        self.args = args or []


def _run(handler, update, context=None):
    asyncio.run(handler(update, context))
    return update.message.replies


def _flag_is_enabled() -> bool:
    async def _go():
        async with async_session() as session:
            return await is_copy_trading_enabled(session)

    return asyncio.run(_go())


def test_status_when_off_by_default(client):
    replies = _run(copytrading_command, _FakeUpdate(), _FakeContext(["status"]))
    assert replies and "OFF" in replies[0]


def test_on_requires_confirmation_not_enabled_immediately(client):
    replies = _run(copytrading_command, _FakeUpdate(), _FakeContext(["on"]))
    assert replies and "yes" in replies[0].lower()
    assert _flag_is_enabled() is False


def test_yes_from_same_admin_confirms(client):
    _run(copytrading_command, _FakeUpdate(), _FakeContext(["on"]))
    replies = _run(confirm_text_handler, _FakeUpdate(text="yes"))
    assert replies and "ON" in replies[0]
    assert _flag_is_enabled() is True


def test_yes_without_pending_request_is_a_silent_noop(client):
    replies = _run(confirm_text_handler, _FakeUpdate(text="yes"))
    assert replies == []
    assert _flag_is_enabled() is False


def test_unrelated_text_does_not_confirm_pending_request(client):
    _run(copytrading_command, _FakeUpdate(), _FakeContext(["on"]))
    replies = _run(confirm_text_handler, _FakeUpdate(text="sure thing"))
    assert replies == []
    assert _flag_is_enabled() is False

    # The pending request is still alive — a correct "yes" afterwards still works.
    replies2 = _run(confirm_text_handler, _FakeUpdate(text="YES"))
    assert replies2 and "ON" in replies2[0]


def test_yes_from_different_user_does_not_confirm(client):
    _run(copytrading_command, _FakeUpdate(AUTHORIZED_USER_ID), _FakeContext(["on"]))
    # confirm_text_handler itself only proceeds for the authorized admin id
    # (settings.authorized_user_id) — a different id is rejected before
    # even checking the pending request, matching every other admin
    # control in this bot.
    replies = _run(confirm_text_handler, _FakeUpdate(UNAUTHORIZED_USER_ID, text="yes"))
    assert replies == []
    assert _flag_is_enabled() is False


def test_off_applies_immediately_no_confirmation(client):
    _run(copytrading_command, _FakeUpdate(), _FakeContext(["on"]))
    _run(confirm_text_handler, _FakeUpdate(text="yes"))
    assert _flag_is_enabled() is True

    replies = _run(copytrading_command, _FakeUpdate(), _FakeContext(["off"]))
    assert replies and "OFF" in replies[0]
    assert _flag_is_enabled() is False


def test_off_clears_any_pending_on_request(client):
    _run(copytrading_command, _FakeUpdate(), _FakeContext(["on"]))
    _run(copytrading_command, _FakeUpdate(), _FakeContext(["off"]))

    # A stray "yes" after the fact must not re-enable it.
    replies = _run(confirm_text_handler, _FakeUpdate(text="yes"))
    assert replies == []
    assert _flag_is_enabled() is False


def test_unauthorized_user_cannot_toggle(client):
    replies = _run(copytrading_command, _FakeUpdate(UNAUTHORIZED_USER_ID), _FakeContext(["on"]))
    assert replies == []
    assert _flag_is_enabled() is False


def test_checkpayments_command_runs_and_reports(client, monkeypatch):
    from app import telegram

    monkeypatch.setattr(telegram, "send_dm", lambda *a, **k: _noop_true())
    monkeypatch.setattr(telegram, "ban_chat_member", lambda *a, **k: _noop_true())
    monkeypatch.setattr(telegram, "unban_chat_member", lambda *a, **k: _noop_true())

    replies = _run(checkpayments_command, _FakeUpdate(), _FakeContext())
    assert len(replies) == 2
    assert "Active subscribers" in replies[1]


async def _noop_true():
    return True
