"""Pure canonical signal lifecycle evaluation for Midas Touch.

This module is deliberately side-effect free. It evaluates an already
persisted canonical signal against a market snapshot and returns the next
state. Database writes, Telegram edits, and copy-feed reads belong to their
respective adapters.

Priority is intentional:
1. terminal states remain terminal;
2. expiry cuts off an otherwise-live setup;
3. thesis invalidation cuts off entry;
4. target progression is evaluated only while the setup remains valid.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LifecycleSignal:
    direction: str
    invalidation: float | None
    tp1: float
    tp2: float
    final_tp: float
    expires_at: datetime | None
    status: str


@dataclass(frozen=True)
class LifecycleResult:
    status: str
    reason: str | None = None


TERMINAL = frozenset({"expired", "invalidated", "stale", "completed"})


def evaluate(signal: LifecycleSignal, market_price: float, now: datetime) -> LifecycleResult:
    """Evaluate one signal without performing I/O.

    Missing invalidation is fail-closed: a signal that cannot express its
    thesis boundary is not eligible to remain actionable. This prevents an
    older EA payload from accidentally receiving the same copy semantics as
    a fully canonical setup.
    """
    status = signal.status.lower()
    if status in TERMINAL:
        return LifecycleResult(status=status)

    if signal.expires_at is not None and now >= signal.expires_at:
        return LifecycleResult(status="expired", reason="SIGNAL_EXPIRY_REACHED")

    if signal.invalidation is None:
        return LifecycleResult(status="stale", reason="MISSING_THESIS_INVALIDATION")

    if signal.direction == "BUY" and market_price <= signal.invalidation:
        return LifecycleResult(status="invalidated", reason="PRICE_CROSSED_THESIS_INVALIDATION")
    if signal.direction == "SELL" and market_price >= signal.invalidation:
        return LifecycleResult(status="invalidated", reason="PRICE_CROSSED_THESIS_INVALIDATION")

    # Do not invent fill semantics here. Target progression is only reported
    # when the signal is already known to be actionable; actual fill/partial
    # close events remain the EA's source of truth.
    return LifecycleResult(status=status)


def is_copy_actionable(result: LifecycleResult) -> bool:
    """Only fully valid/live states can cross into copy execution."""
    return result.status in {"active", "tp1_reached", "tp2_reached"}
