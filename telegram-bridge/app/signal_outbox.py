"""Durable asynchronous Telegram delivery worker.

Signal acceptance never waits on Telegram. The database outbox is the durable
boundary; this worker drains it and updates the authoritative Signal row only
after Telegram acknowledges delivery.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import async_session
from app.formatter import format_signal_message
from app.logger import logger
from app.models import Signal, SignalDeliveryOutbox, SignalStatus
from app.telegram import NonRetryableError, send_telegram_message

MAX_ATTEMPTS = 3
POLL_SECONDS = 0.25


async def deliver_pending_once() -> bool:
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        row = await session.scalar(
            select(SignalDeliveryOutbox)
            .where(
                SignalDeliveryOutbox.status.in_(("pending", "processing")),
                SignalDeliveryOutbox.next_attempt_at <= now,
            )
            .order_by(SignalDeliveryOutbox.created_at)
            .limit(1)
        )
        if row is None:
            return False

        row.status = "processing"
        row.attempts += 1
        row.next_attempt_at = now + timedelta(seconds=60)
        await session.commit()
        payload = dict(row.payload)
        signal_id = row.signal_id

        try:
            message_id = await send_telegram_message(format_signal_message(payload))
        except NonRetryableError as exc:
            row.status = "failed"
            row.last_error = str(exc)
            row.next_attempt_at = now + timedelta(minutes=5)
            await session.commit()
            logger.error("Permanent Telegram delivery failure for %s: %s", signal_id, exc)
            return True
        except Exception as exc:
            if row.attempts >= MAX_ATTEMPTS:
                row.status = "failed"
                row.next_attempt_at = now + timedelta(minutes=5)
            else:
                row.status = "pending"
                row.next_attempt_at = now + timedelta(seconds=2 ** row.attempts)
            row.last_error = f"{type(exc).__name__}: {exc}"
            await session.commit()
            logger.warning("Telegram delivery retry scheduled for %s: %s", signal_id, exc)
            return True

        row.status = "sent"
        row.sent_at = datetime.now(timezone.utc)
        row.last_error = None
        signal = await session.scalar(select(Signal).where(Signal.signal_id == signal_id))
        if signal is not None:
            signal.telegram_message_id = message_id
            signal.status = SignalStatus.ACTIVE
            signal.error_message = None
        await session.commit()
        logger.info("Telegram delivery completed for %s", signal_id)
        return True


async def run_outbox_worker(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await deliver_pending_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Signal outbox worker error (%s): %s", type(exc).__name__, exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_SECONDS)
        except asyncio.TimeoutError:
            pass
