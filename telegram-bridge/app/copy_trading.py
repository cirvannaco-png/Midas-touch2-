"""
Copy-trading entitlement gate.

INVARIANT, load-bearing: nothing in POST /signal's request path
(app/routes.py:receive_signal, or anything it calls — validator.py,
formatter.py, settings_store.is_broadcast_paused/is_symbol_muted,
send_telegram_message) imports or calls anything in this module.
Signal ingestion, storage, and Telegram broadcast happen exactly as
they did before this module existed, whether copy trading is on or
off, whether zero subscribers or a thousand are entitled. Grep this
repo for "copy_trading" outside this file and app/copytrading_admin.py,
app/subscriptions.py, app/group_enforcement.py, app/routes.py's
/copy/feed handler, and their tests — there should be nothing in
receive_signal()'s call graph.

Entitlement is evaluated at READ time, when a paying subscriber's own
copier script polls GET /copy/feed (see app/routes.py). That endpoint
queries the *existing* signals table live; there is no separate
dispatch/queue/fan-out step that could itself fail or fall behind and
take signal delivery down with it. can_copy() below is the single
choke point both the global switch (settings_store) and per-subscriber
entitlement (subscriptions.is_entitled) pass through.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subscriber
from app.settings_store import is_copy_trading_enabled
from app.subscriptions import is_entitled


async def can_copy(session: AsyncSession, subscriber: Subscriber | None) -> bool:
    """
    True only if BOTH hold:
      1. an admin has turned the global copy-trading switch on
         (settings_store.is_copy_trading_enabled — see
         app/copytrading_admin.py for the "yes"-confirmation flow that
         sets this), and
      2. this specific subscriber's paid period hasn't lapsed
         (subscriptions.is_entitled).

    Fail-closed on both axes: an unset/false global flag or an
    unrecognized/expired subscriber both return False, never an
    exception a caller might mishandle into an accidental allow.
    """
    if subscriber is None:
        return False
    if not is_entitled(subscriber):
        return False
    return await is_copy_trading_enabled(session)
