"""
The "remove people who don't pay" pipeline.

Two halves, deliberately separated:

  sweep_subscriber_statuses() — pure DB state transitions (warn-eligible /
  expire / remove-eligible), no network calls, trivially unit-testable
  with a fake clock via subscriber rows alone.

  run_subscription_enforcement() — takes that pass's output and performs
  the actual Telegram side effects (DM warnings, kick from
  GROUP_CHAT_ID), via app.telegram's best-effort helpers so one
  unreachable user (blocked the bot, already left) can never abort the
  rest of the sweep.

Invoked from two places, both wired deliberately outside the request
path of anything trading-related:
  - POST /admin/check-subscriptions (app/routes.py) — same X-API-Key
    admin auth as POST /admin/run-cycle, meant to be hit by an external
    scheduled CI job for the
    same free-tier-Render-sleeps reason documented on that endpoint.
  - /checkpayments (app/copytrading_admin.py) — manual trigger from
    Telegram, for when you don't want to wait for the next cron tick.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import telegram
from app.config import settings
from app.logger import logger
from app.models import (
    SUBSCRIBER_STATUS_ACTIVE,
    SUBSCRIBER_STATUS_EXPIRED,
    SUBSCRIBER_STATUS_REMOVED,
    Subscriber,
)


async def sweep_subscriber_statuses(session: AsyncSession) -> dict[str, list[Subscriber]]:
    now = datetime.now(timezone.utc)
    warning_cutoff = now + timedelta(hours=settings.SUBSCRIPTION_WARNING_HOURS_BEFORE_EXPIRY)
    grace_cutoff = now - timedelta(days=settings.SUBSCRIPTION_GRACE_PERIOD_DAYS)

    # 1. Still active, but about to lapse and never warned for this
    #    period (warned_at is cleared on every fresh payment — see
    #    subscriptions.record_payment — so this can't skip a warning for
    #    someone who's since renewed).
    to_warn = (
        await session.execute(
            select(Subscriber).where(
                Subscriber.status == SUBSCRIBER_STATUS_ACTIVE,
                Subscriber.current_period_end.is_not(None),
                Subscriber.current_period_end <= warning_cutoff,
                Subscriber.current_period_end > now,
                Subscriber.warned_at.is_(None),
            )
        )
    ).scalars().all()
    for s in to_warn:
        s.warned_at = now

    # 2. Active period has actually lapsed -> EXPIRED. Still a group
    #    member during the grace period; already loses /copy/feed access
    #    immediately (subscriptions.is_entitled checks current_period_end
    #    directly, not status alone, so this transition isn't even what
    #    cuts off the feed — see app/copy_trading.py).
    to_expire = (
        await session.execute(
            select(Subscriber).where(
                Subscriber.status == SUBSCRIBER_STATUS_ACTIVE,
                Subscriber.current_period_end.is_not(None),
                Subscriber.current_period_end <= now,
            )
        )
    ).scalars().all()
    for s in to_expire:
        s.status = SUBSCRIBER_STATUS_EXPIRED

    # 3. Already EXPIRED and the grace period has also run out -> remove.
    to_remove = (
        await session.execute(
            select(Subscriber).where(
                Subscriber.status == SUBSCRIBER_STATUS_EXPIRED,
                Subscriber.current_period_end.is_not(None),
                Subscriber.current_period_end <= grace_cutoff,
            )
        )
    ).scalars().all()
    for s in to_remove:
        s.status = SUBSCRIBER_STATUS_REMOVED

    await session.commit()
    return {"warn": to_warn, "expire": to_expire, "remove": to_remove}


async def run_subscription_enforcement(session: AsyncSession) -> dict:
    result = await sweep_subscriber_statuses(session)

    warned = 0
    for s in result["warn"]:
        deadline = s.current_period_end.strftime("%Y-%m-%d %H:%M UTC")
        sent = await telegram.send_dm(
            s.telegram_user_id,
            f"⏳ Your Medis Touch access expires {deadline} — send /subscribe to renew "
            f"before then and avoid any interruption.",
        )
        warned += int(sent)

    removed = 0
    for s in result["remove"]:
        if settings.GROUP_CHAT_ID:
            await telegram.ban_chat_member(settings.GROUP_CHAT_ID, s.telegram_user_id)
            await telegram.unban_chat_member(settings.GROUP_CHAT_ID, s.telegram_user_id)
        else:
            logger.warning(
                f"GROUP_CHAT_ID not set — subscriber {s.telegram_user_id} marked REMOVED "
                f"but no group membership actually changed."
            )
        await telegram.send_dm(
            s.telegram_user_id,
            "Your Medis Touch subscription lapsed and the grace period has ended, so you've "
            "been removed from the group. Send /subscribe any time to rejoin.",
        )
        removed += 1

    return {
        "warned": warned,
        "expired": len(result["expire"]),
        "removed": removed,
    }
