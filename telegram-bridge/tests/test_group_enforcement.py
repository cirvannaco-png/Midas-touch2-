"""Tests for app.group_enforcement.sweep_subscriber_statuses and
run_subscription_enforcement."""
from datetime import datetime, timedelta, timezone

import pytest

from app.database import async_session
from app.group_enforcement import run_subscription_enforcement, sweep_subscriber_statuses
from app.models import (
    SUBSCRIBER_STATUS_ACTIVE,
    SUBSCRIBER_STATUS_EXPIRED,
    SUBSCRIBER_STATUS_REMOVED,
)
from app.subscriptions import get_or_create_subscriber



async def _make_subscriber(session, user_id, status, period_end, warned_at=None):
    sub = await get_or_create_subscriber(session, user_id, f"user-{user_id}")
    sub.status = status
    sub.current_period_end = period_end
    sub.warned_at = warned_at
    await session.commit()
    return sub


@pytest.mark.asyncio
async def test_active_subscriber_nearing_expiry_gets_warned_once():
    now = datetime.now(timezone.utc)

    async def _go():
        async with async_session() as session:
            await _make_subscriber(session, "4001", SUBSCRIBER_STATUS_ACTIVE, now + timedelta(hours=2))
            result = await sweep_subscriber_statuses(session)
            assert len(result["warn"]) == 1
            assert result["warn"][0].telegram_user_id == "4001"

            # Second sweep must not warn again — warned_at is now set.
            result2 = await sweep_subscriber_statuses(session)
            assert len(result2["warn"]) == 0

    await _go()


@pytest.mark.asyncio
async def test_active_subscriber_past_expiry_becomes_expired():
    now = datetime.now(timezone.utc)

    async def _go():
        async with async_session() as session:
            await _make_subscriber(session, "4002", SUBSCRIBER_STATUS_ACTIVE, now - timedelta(hours=1))
            result = await sweep_subscriber_statuses(session)
            assert any(s.telegram_user_id == "4002" for s in result["expire"])

            from app.subscriptions import get_subscriber_by_user_id
            sub = await get_subscriber_by_user_id(session, "4002")
            assert sub.status == SUBSCRIBER_STATUS_EXPIRED

    await _go()


@pytest.mark.asyncio
async def test_expired_subscriber_within_grace_period_is_not_removed():
    now = datetime.now(timezone.utc)

    async def _go():
        async with async_session() as session:
            # Grace period default is 3 days — 1 day past expiry is still inside it.
            await _make_subscriber(session, "4003", SUBSCRIBER_STATUS_EXPIRED, now - timedelta(days=1))
            result = await sweep_subscriber_statuses(session)
            assert not any(s.telegram_user_id == "4003" for s in result["remove"])

    await _go()


@pytest.mark.asyncio
async def test_expired_subscriber_past_grace_period_is_removed():
    now = datetime.now(timezone.utc)

    async def _go():
        async with async_session() as session:
            await _make_subscriber(session, "4004", SUBSCRIBER_STATUS_EXPIRED, now - timedelta(days=10))
            result = await sweep_subscriber_statuses(session)
            assert any(s.telegram_user_id == "4004" for s in result["remove"])

            from app.subscriptions import get_subscriber_by_user_id
            sub = await get_subscriber_by_user_id(session, "4004")
            assert sub.status == SUBSCRIBER_STATUS_REMOVED

    await _go()


@pytest.mark.asyncio
async def test_enforcement_calls_telegram_helpers_and_never_raises_on_dm_failure(monkeypatch):
    """One subscriber the bot can't DM (blocked it) must not stop the rest
    of the sweep, and must not surface as an exception from the endpoint."""
    from app import telegram
    from app.config import settings

    monkeypatch.setattr(settings, "GROUP_CHAT_ID", "-100999")

    calls = {"dm": [], "ban": [], "unban": []}

    async def _fake_dm(user_id, text):
        calls["dm"].append(user_id)
        return user_id != "4005"  # simulate "bot was blocked by the user"

    async def _fake_ban(chat_id, user_id):
        calls["ban"].append(user_id)
        return True

    async def _fake_unban(chat_id, user_id, only_if_banned=True):
        calls["unban"].append(user_id)
        return True

    monkeypatch.setattr(telegram, "send_dm", _fake_dm)
    monkeypatch.setattr(telegram, "ban_chat_member", _fake_ban)
    monkeypatch.setattr(telegram, "unban_chat_member", _fake_unban)

    now = datetime.now(timezone.utc)

    async def _go():
        async with async_session() as session:
            await _make_subscriber(session, "4005", SUBSCRIBER_STATUS_EXPIRED, now - timedelta(days=10))
            await _make_subscriber(session, "4006", SUBSCRIBER_STATUS_EXPIRED, now - timedelta(days=10))
            result = await run_subscription_enforcement(session)
            assert result["removed"] == 2
            assert set(calls["ban"]) == {"4005", "4006"}
            assert set(calls["unban"]) == {"4005", "4006"}

    await _go()


@pytest.mark.asyncio
async def test_removal_without_group_chat_id_configured_logs_but_does_not_crash(monkeypatch):
    """GROUP_CHAT_ID unset (e.g. a fresh deploy before it's configured)
    must not raise — the subscriber still gets marked REMOVED and DM'd,
    just with no group membership actually changing."""
    from app import telegram
    from app.config import settings

    monkeypatch.setattr(settings, "GROUP_CHAT_ID", "")

    async def _fake_dm(user_id, text):
        return True

    monkeypatch.setattr(telegram, "send_dm", _fake_dm)

    now = datetime.now(timezone.utc)

    async def _go():
        async with async_session() as session:
            await _make_subscriber(session, "4007", SUBSCRIBER_STATUS_EXPIRED, now - timedelta(days=10))
            result = await run_subscription_enforcement(session)
            assert result["removed"] == 1

    await _go()
