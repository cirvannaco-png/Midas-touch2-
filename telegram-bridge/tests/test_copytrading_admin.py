"""Tests for app.copytrading_admin handlers and confirmation gates."""
import os

import pytest

from app.copytrading_admin import checkpayments_command, confirm_text_handler, copytrading_command
from app.database import async_session
from app.settings_store import is_copy_trading_enabled, set_copy_trading_enabled

AUTHORIZED_USER_ID = int(os.environ["ADMIN_CHAT_ID"])
UNAUTHORIZED_USER_ID = 999999999


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


async def _flag_is_enabled() -> bool:
    async with async_session() as session:
        return await is_copy_trading_enabled(session)


async def _reset_copy_state():
    async with async_session() as session:
        await set_copy_trading_enabled(session, False)


@pytest.mark.asyncio
async def test_status_when_off_by_default():
    await _reset_copy_state()
    update = _FakeUpdate()
    await copytrading_command(update, _FakeContext(["status"]))
    assert update.message.replies and "OFF" in update.message.replies[0]


@pytest.mark.asyncio
async def test_on_requires_confirmation_not_enabled_immediately():
    await _reset_copy_state()
    update = _FakeUpdate()
    await copytrading_command(update, _FakeContext(["on"]))
    assert update.message.replies and "yes" in update.message.replies[0].lower()
    assert await _flag_is_enabled() is False


@pytest.mark.asyncio
async def test_yes_from_same_admin_confirms():
    await _reset_copy_state()
    await copytrading_command(_FakeUpdate(), _FakeContext(["on"]))
    update = _FakeUpdate(text="yes")
    await confirm_text_handler(update, None)
    assert update.message.replies and "ON" in update.message.replies[0]
    assert await _flag_is_enabled() is True


@pytest.mark.asyncio
async def test_yes_without_pending_request_is_a_silent_noop():
    await _reset_copy_state()
    update = _FakeUpdate(text="yes")
    await confirm_text_handler(update, None)
    assert update.message.replies == []
    assert await _flag_is_enabled() is False


@pytest.mark.asyncio
async def test_unrelated_text_does_not_confirm_pending_request():
    await _reset_copy_state()
    await copytrading_command(_FakeUpdate(), _FakeContext(["on"]))

    update = _FakeUpdate(text="sure thing")
    await confirm_text_handler(update, None)
    assert update.message.replies == []
    assert await _flag_is_enabled() is False

    update_yes = _FakeUpdate(text="YES")
    await confirm_text_handler(update_yes)
    assert update_yes.message.replies and "ON" in update_yes.message.replies[0]


@pytest.mark.asyncio
async def test_yes_from_different_user_does_not_confirm():
    await _reset_copy_state()
    await copytrading_command(_FakeUpdate(AUTHORIZED_USER_ID), _FakeContext(["on"]))

    update = _FakeUpdate(UNAUTHORIZED_USER_ID, text="yes")
    await confirm_text_handler(update, None)
    assert update.message.replies == []
    assert await _flag_is_enabled() is False


@pytest.mark.asyncio
async def test_off_applies_immediately_no_confirmation():
    await _reset_copy_state()
    await copytrading_command(_FakeUpdate(), _FakeContext(["on"]))
    await confirm_text_handler(_FakeUpdate(text="yes"), None)
    assert await _flag_is_enabled() is True

    update = _FakeUpdate()
    await copytrading_command(update, _FakeContext(["off"]))
    assert update.message.replies and "OFF" in update.message.replies[0]
    assert await _flag_is_enabled() is False


@pytest.mark.asyncio
async def test_off_clears_any_pending_on_request():
    await _reset_copy_state()
    await copytrading_command(_FakeUpdate(), _FakeContext(["on"]))
    await copytrading_command(_FakeUpdate(), _FakeContext(["off"]))

    update = _FakeUpdate(text="yes")
    await confirm_text_handler(update, None)
    assert update.message.replies == []
    assert await _flag_is_enabled() is False


@pytest.mark.asyncio
async def test_unauthorized_user_cannot_toggle():
    await _reset_copy_state()
    update = _FakeUpdate(UNAUTHORIZED_USER_ID)
    await copytrading_command(update, _FakeContext(["on"]))
    assert update.message.replies == []
    assert await _flag_is_enabled() is False


@pytest.mark.asyncio
async def test_checkpayments_command_runs_and_reports(monkeypatch):
    from app import telegram

    async def _noop_true(*_args, **_kwargs):
        return True

    monkeypatch.setattr(telegram, "send_dm", _noop_true)
    monkeypatch.setattr(telegram, "ban_chat_member", _noop_true)
    monkeypatch.setattr(telegram, "unban_chat_member", _noop_true)

    update = _FakeUpdate()
    await checkpayments_command(update, _FakeContext())
    assert len(update.message.replies) == 2
    assert "Active subscribers" in update.message.replies[1]
