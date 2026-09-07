"""
Subscriber + payment domain logic.

Owns: who's a subscriber, whether their current period is paid up
(is_entitled), and recording a successful Telegram Payments transaction
idempotently. Deliberately does NOT own Telegram API calls (that's
app/payments_bot.py for sending invoices, app/group_enforcement.py for
removing people) or the copy-trading flag itself (that's
app/settings_store.py + app/copy_trading.py) — this module answers "is
this specific person paid up right now", nothing about whether copy
trading is globally switched on.

Every function here takes an already-open AsyncSession, same convention
as app/settings_store.py, for the same reason: lets routes.py and the
bot handlers share one transaction instead of this module opening its
own.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.logger import logger
from app.models import (
    PAYMENT_STATUS_SUCCEEDED,
    SUBSCRIBER_STATUS_ACTIVE,
    SUBSCRIBER_STATUS_PENDING,
    Payment,
    Subscriber,
)


def _generate_copy_feed_key() -> str:
    """
    32 bytes of entropy, URL-safe. Regenerated on every successful
    payment (see record_payment below) rather than reused across
    periods — an old key found in a leaked log or a screenshot from a
    prior, now-lapsed period stops working the moment a new one is
    minted, instead of quietly remaining valid forever.
    """
    return secrets.token_urlsafe(32)


def _as_utc(dt: datetime | None) -> datetime | None:
    """
    SQLite has no native timezone-aware datetime type: a DateTime(timezone=True)
    column round-trips through it as a naive datetime even though every write
    in this module uses datetime.now(timezone.utc). Comparing that naive
    read-back against an aware "now" raises TypeError. This assumes (true
    everywhere in this module) that anything naive we ever see was written as
    UTC in the first place, and is a no-op on Postgres, which preserves the
    offset and hands back an already-aware value.
    """
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def get_subscriber_by_user_id(session: AsyncSession, telegram_user_id: str) -> Subscriber | None:
    return await session.scalar(
        select(Subscriber).where(Subscriber.telegram_user_id == str(telegram_user_id))
    )


async def get_subscriber_by_copy_feed_key(session: AsyncSession, copy_feed_api_key: str) -> Subscriber | None:
    if not copy_feed_api_key:
        return None
    return await session.scalar(
        select(Subscriber).where(Subscriber.copy_feed_api_key == copy_feed_api_key)
    )


async def get_or_create_subscriber(
    session: AsyncSession, telegram_user_id: str, telegram_username: str | None
) -> Subscriber:
    """
    Looks up a subscriber by Telegram user id, creating a PENDING one
    (never paid, no entitlement) if this is the first time this person
    has ever been seen — e.g. their first /subscribe. Updates the stored
    username opportunistically (Telegram usernames change) without
    touching status/entitlement.
    """
    subscriber = await get_subscriber_by_user_id(session, telegram_user_id)
    if subscriber is not None:
        if telegram_username and subscriber.telegram_username != telegram_username:
            subscriber.telegram_username = telegram_username
            await session.commit()
        return subscriber

    subscriber = Subscriber(
        telegram_user_id=str(telegram_user_id),
        telegram_username=telegram_username,
        status=SUBSCRIBER_STATUS_PENDING,
    )
    session.add(subscriber)
    try:
        await session.commit()
    except IntegrityError:
        # Concurrent /subscribe from the same user id (double-tap, retry)
        # raced this insert — same duplicate-as-not-an-error handling as
        # Signal.signal_id / TradeEvent.event_id in routes.py.
        await session.rollback()
        subscriber = await get_subscriber_by_user_id(session, telegram_user_id)
    return subscriber


def is_entitled(subscriber: Subscriber | None) -> bool:
    """
    Pure function, no DB access — pass in an already-loaded Subscriber.
    True only for a subscriber who is ACTIVE *and* whose paid period
    genuinely hasn't lapsed yet. Deliberately does not treat EXPIRED
    (inside the grace period, per SUBSCRIPTION_GRACE_PERIOD_DAYS) as
    entitled: the grace period exists so group_enforcement.py doesn't
    kick someone out of the Telegram group the instant a payment is a
    day late, but /copy/feed access — real trading decisions — cuts off
    the moment the paid period actually ends, not when the grace period
    does. Being slow to remove someone from a group is a UX kindness;
    being slow to cut off a trading feed is a bill nobody agreed to.
    """
    if subscriber is None:
        return False
    if subscriber.status != SUBSCRIBER_STATUS_ACTIVE:
        return False
    if subscriber.current_period_end is None:
        return False
    return _as_utc(subscriber.current_period_end) > datetime.now(timezone.utc)


async def record_payment(
    session: AsyncSession,
    subscriber: Subscriber,
    *,
    telegram_payment_charge_id: str,
    amount: int,
    currency: str,
    invoice_payload: str,
    raw_payload: dict,
    period_days: int | None = None,
) -> Payment | None:
    """
    Idempotently records a successful Telegram Payments transaction and
    extends the subscriber's entitlement window. Returns the new Payment
    row, or None if telegram_payment_charge_id was already recorded
    (Telegram redelivered the same successful_payment update — this must
    not double-extend the period).

    Extension is stacked on top of current_period_end when it's still in
    the future (an early renewal adds on top of remaining time instead
    of discarding it), and from "now" when it's null/past (first payment,
    or renewing after a lapse).
    """
    period_days = period_days or settings.SUBSCRIPTION_PERIOD_DAYS
    payment = Payment(
        telegram_payment_charge_id=telegram_payment_charge_id,
        subscriber_id=subscriber.id,
        amount=amount,
        currency=currency,
        period_days=period_days,
        invoice_payload=invoice_payload,
        status=PAYMENT_STATUS_SUCCEEDED,
        raw_payload=raw_payload,
    )
    session.add(payment)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        # Rollback expires every object tracked by this session, subscriber
        # included, not just the row that failed to insert. Refreshing here
        # (a real awaited query) is what lets the caller safely read
        # subscriber.current_period_end etc. right after this returns —
        # without it, that attribute access would try an implicit lazy
        # reload outside of an awaitable context and blow up with
        # SQLAlchemy's MissingGreenlet, not a clean "already recorded".
        await session.refresh(subscriber)
        logger.info(
            f"Duplicate successful_payment ignored "
            f"(telegram_payment_charge_id={telegram_payment_charge_id})"
        )
        return None

    now = datetime.now(timezone.utc)
    existing_end = _as_utc(subscriber.current_period_end)
    base = existing_end if (existing_end and existing_end > now) else now
    subscriber.current_period_end = base + timedelta(days=period_days)
    subscriber.status = SUBSCRIBER_STATUS_ACTIVE
    subscriber.copy_feed_api_key = _generate_copy_feed_key()
    subscriber.warned_at = None  # fresh period — any prior expiry warning no longer applies

    await session.commit()
    return payment
