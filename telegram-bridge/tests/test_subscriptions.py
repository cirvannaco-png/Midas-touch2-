"""Tests for app.subscriptions: entitlement, idempotent payment recording,
period-stacking on renewal."""
import asyncio
from datetime import datetime, timedelta, timezone

from app.database import async_session
from app.models import SUBSCRIBER_STATUS_ACTIVE, SUBSCRIBER_STATUS_PENDING
from app.subscriptions import (
    get_or_create_subscriber,
    is_entitled,
    record_payment,
)


def _run(coro, client=None):
    if client is not None:
        assert client.portal is not None
        async def _await_coro(coro):
            return await coro
        return client.portal.call(_await_coro, coro)
    return asyncio.run(coro)


def test_get_or_create_subscriber_is_idempotent(client):
    async def _go():
        async with async_session() as session:
            a = await get_or_create_subscriber(session, "111", "alice")
            b = await get_or_create_subscriber(session, "111", "alice")
            assert a.id == b.id
            assert a.status == SUBSCRIBER_STATUS_PENDING

    _run(_go(), client=client)


def test_get_or_create_subscriber_updates_username(client):
    async def _go():
        async with async_session() as session:
            await get_or_create_subscriber(session, "222", "old_name")
            updated = await get_or_create_subscriber(session, "222", "new_name")
            assert updated.telegram_username == "new_name"

    _run(_go(), client=client)


def test_fresh_subscriber_is_not_entitled(client):
    async def _go():
        async with async_session() as session:
            sub = await get_or_create_subscriber(session, "333", "bob")
            assert is_entitled(sub) is False

    _run(_go(), client=client)


def test_record_payment_grants_entitlement(client):
    async def _go():
        async with async_session() as session:
            sub = await get_or_create_subscriber(session, "444", "carol")
            payment = await record_payment(
                session,
                sub,
                telegram_payment_charge_id="charge-1",
                amount=500,
                currency="XTR",
                invoice_payload="medistouch_sub:444",
                raw_payload={"total_amount": 500},
            )
            assert payment is not None
            assert sub.status == SUBSCRIBER_STATUS_ACTIVE
            assert is_entitled(sub) is True
            assert sub.copy_feed_api_key  # a key was minted

    _run(_go(), client=client)


def test_duplicate_charge_id_is_ignored(client):
    """Telegram redelivering the same successful_payment update must not
    double-extend the subscriber's period."""
    async def _go():
        async with async_session() as session:
            sub = await get_or_create_subscriber(session, "555", "dave")
            first = await record_payment(
                session, sub, telegram_payment_charge_id="dup-charge",
                amount=500, currency="XTR", invoice_payload="p", raw_payload={},
            )
            end_after_first = sub.current_period_end
            second = await record_payment(
                session, sub, telegram_payment_charge_id="dup-charge",
                amount=500, currency="XTR", invoice_payload="p", raw_payload={},
            )
            assert first is not None
            assert second is None
            # SQLite round-trips DateTime(timezone=True) as naive; compare
            # wall-clock value, not tzinfo identity (see subscriptions._as_utc).
            assert sub.current_period_end.replace(tzinfo=None) == end_after_first.replace(tzinfo=None)

    _run(_go(), client=client)


def test_early_renewal_stacks_on_remaining_time(client):
    async def _go():
        async with async_session() as session:
            sub = await get_or_create_subscriber(session, "666", "erin")
            sub.status = SUBSCRIBER_STATUS_ACTIVE
            sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=10)
            await session.commit()

            await record_payment(
                session, sub, telegram_payment_charge_id="renew-1",
                amount=500, currency="XTR", invoice_payload="p", raw_payload={},
                period_days=30,
            )
            expected_min = datetime.now(timezone.utc) + timedelta(days=39)
            assert sub.current_period_end > expected_min

    _run(_go(), client=client)


def test_lapsed_subscriber_is_not_entitled(client):
    async def _go():
        async with async_session() as session:
            sub = await get_or_create_subscriber(session, "777", "frank")
            sub.status = SUBSCRIBER_STATUS_ACTIVE
            sub.current_period_end = datetime.now(timezone.utc) - timedelta(days=1)
            await session.commit()
            assert is_entitled(sub) is False

    _run(_go(), client=client)
