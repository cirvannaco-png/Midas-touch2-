"""
Read/write helpers for app.models.BotSetting.

This backs the operator controls exposed via Telegram (/mute, /unmute,
/pause, /resume) and consulted by POST /signal before it broadcasts a new
signal to CHAT_ID. Kept as a tiny module of its own, rather than folding
straight into routes.py or bot_handlers.py, so both can import the same
read path without a circular import (routes.py needs it to gate
broadcasting; bot_handlers.py needs it to report/change state).

Every function opens nothing itself - callers pass in an already-open
AsyncSession (the same pattern used throughout routes.py/bot_handlers.py)
so this stays transaction-agnostic and testable.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotSetting

_KEY_MUTED_SYMBOLS = "muted_symbols"
_KEY_BROADCAST_PAUSED = "broadcast_paused"

# --- Copy-trading master switch ----------------------------------------
#
# This flag gates GET /copy/feed (see app/copy_trading.py) and NOTHING
# else. POST /signal (routes.py:receive_signal) never reads this key,
# directly or indirectly — signal generation/ingestion/broadcast is
# unaffected by whether copy trading is on or off, by construction, not
# by a runtime check. Off by default (fail-closed): a fresh deploy, or
# one where this key was never set, never dispatches real money.
_KEY_COPY_TRADING_ENABLED = "copy_trading_enabled"
# Holds at most one pending "turn copy trading ON" request awaiting the
# literal text "yes" from the same admin who requested it. Turning it
# OFF never goes through this — see set_copy_trading_enabled() below for
# why the safe direction doesn't need a confirmation step.
_KEY_COPY_TRADING_PENDING_ON = "copy_trading_pending_on"


async def _get(session: AsyncSession, key: str, default):
    row = await session.get(BotSetting, key)
    return row.value if row is not None else default


async def _set(session: AsyncSession, key: str, value) -> None:
    row = await session.get(BotSetting, key)
    if row is None:
        session.add(BotSetting(key=key, value=value))
    else:
        row.value = value
    await session.commit()


async def get_muted_symbols(session: AsyncSession) -> set[str]:
    return set(await _get(session, _KEY_MUTED_SYMBOLS, []))


async def get_signal_broadcast_controls(session: AsyncSession) -> tuple[bool, set[str]]:
    """Read both signal broadcast controls in one database round-trip.

    This remains read-through to PostgreSQL rather than process-cached so
    operator pause/mute changes take effect immediately across instances.
    """
    result = await session.execute(
        select(BotSetting).where(
            BotSetting.key.in_((_KEY_BROADCAST_PAUSED, _KEY_MUTED_SYMBOLS))
        )
    )
    values = {row.key: row.value for row in result.scalars()}
    return bool(values.get(_KEY_BROADCAST_PAUSED, False)), set(
        values.get(_KEY_MUTED_SYMBOLS, []) or []
    )


async def mute_symbol(session: AsyncSession, symbol: str) -> set[str]:
    symbols = await get_muted_symbols(session)
    symbols.add(symbol.upper())
    await _set(session, _KEY_MUTED_SYMBOLS, sorted(symbols))
    return symbols


async def unmute_symbol(session: AsyncSession, symbol: str) -> set[str]:
    symbols = await get_muted_symbols(session)
    symbols.discard(symbol.upper())
    await _set(session, _KEY_MUTED_SYMBOLS, sorted(symbols))
    return symbols


async def is_symbol_muted(session: AsyncSession, symbol: str) -> bool:
    return symbol.upper() in await get_muted_symbols(session)


async def is_broadcast_paused(session: AsyncSession) -> bool:
    return bool(await _get(session, _KEY_BROADCAST_PAUSED, False))


async def set_broadcast_paused(session: AsyncSession, paused: bool) -> None:
    await _set(session, _KEY_BROADCAST_PAUSED, paused)


# --- Copy-trading master switch ----------------------------------------

async def is_copy_trading_enabled(session: AsyncSession) -> bool:
    return bool(await _get(session, _KEY_COPY_TRADING_ENABLED, False))


async def set_copy_trading_enabled(session: AsyncSession, enabled: bool) -> None:
    """
    Direct, unconditional flip of the flag GET /copy/feed reads.

    Turning copy trading OFF calls this directly (see
    app/copytrading_admin.py:copytrading_command) — no "yes" confirmation
    required, on purpose: OFF is the fail-closed direction, so there is
    no accidental-real-money risk to guard against, only the risk of
    hesitating to hit the kill switch. Turning it ON never calls this
    function directly; it must go through request_copy_trading_on() and
    confirm_copy_trading_on() below.
    """
    await _set(session, _KEY_COPY_TRADING_ENABLED, enabled)
    if not enabled:
        # An in-flight "turn it on" confirmation shouldn't survive an
        # explicit /copytrading off — otherwise a stray "yes" sent
        # moments later would silently re-enable it.
        await _set(session, _KEY_COPY_TRADING_PENDING_ON, None)


async def request_copy_trading_on(session: AsyncSession, user_id: str, ttl_seconds: int) -> None:
    """
    Records "user_id asked to turn copy trading on" with an expiry.
    Nothing is enabled yet — see confirm_copy_trading_on().
    """
    now = datetime.now(timezone.utc)
    await _set(
        session,
        _KEY_COPY_TRADING_PENDING_ON,
        {
            "requested_by": str(user_id),
            "requested_at": now.isoformat(),
            "expires_at": (now.timestamp() + ttl_seconds),
        },
    )


async def get_pending_copy_trading_on(session: AsyncSession) -> dict | None:
    return await _get(session, _KEY_COPY_TRADING_PENDING_ON, None)


async def confirm_copy_trading_on(session: AsyncSession, user_id: str) -> bool:
    """
    Applies a pending ON request if-and-only-if `user_id` matches whoever
    requested it and the request hasn't expired. Returns True (and
    enables the flag) or False (and clears the stale/mismatched pending
    request either way, so a leftover pending state can't be confirmed
    later by surprise).
    """
    pending = await get_pending_copy_trading_on(session)
    await _set(session, _KEY_COPY_TRADING_PENDING_ON, None)
    if pending is None:
        return False
    if str(pending.get("requested_by")) != str(user_id):
        return False
    if datetime.now(timezone.utc).timestamp() > float(pending.get("expires_at", 0)):
        return False
    await _set(session, _KEY_COPY_TRADING_ENABLED, True)
    return True