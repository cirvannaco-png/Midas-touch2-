"""Broker/OMS reconciliation helpers. Unknown state always fails closed."""
# ruff: noqa: I001

from __future__ import annotations

from math import isfinite

from .execution_models import ExecutionOrder, OrderStatus, ReconciliationResult


_TERMINAL = {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED}


def reconcile(
    expected: ExecutionOrder,
    observed_status: OrderStatus | None,
    observed_filled: float | None = None,
) -> ReconciliationResult:
    """Compare OMS and broker state; missing fill evidence never authorizes resume."""
    def unresolved(action: str, reason: str, status: OrderStatus | None = observed_status) -> ReconciliationResult:
        return ReconciliationResult(expected.order_id, expected.status, status, False, action, reason)

    if not isfinite(expected.quantity) or expected.quantity <= 0:
        return unresolved("FREEZE_AND_RECONCILE", "OMS requested quantity is invalid")
    if not isfinite(expected.filled_quantity) or expected.filled_quantity < 0:
        return unresolved("FREEZE_AND_RECONCILE", "OMS cumulative fill quantity is invalid")
    if expected.filled_quantity > expected.quantity + 1e-9:
        return unresolved("FREEZE_AND_RECONCILE", "OMS cumulative fill exceeds requested quantity")
    if observed_status is None:
        return unresolved("FREEZE_AND_QUERY", "broker state unavailable")
    if observed_status in {OrderStatus.UNKNOWN, OrderStatus.RECOVERY_REQUIRED}:
        return unresolved("FREEZE_AND_QUERY", "broker returned ambiguous state")
    if observed_filled is None:
        return unresolved("FREEZE_AND_QUERY", "broker fill quantity unavailable")
    if not isfinite(observed_filled) or observed_filled < 0:
        return unresolved("FREEZE_AND_RECONCILE", "broker fill quantity is invalid")
    if observed_filled > expected.quantity + 1e-9:
        return unresolved("FREEZE_AND_RECONCILE", "broker cumulative fill exceeds requested quantity")
    if expected.status == OrderStatus.FILLED and expected.filled_quantity < expected.quantity - 1e-9:
        return unresolved("FREEZE_AND_RECONCILE", "OMS says FILLED but its cumulative quantity is incomplete")
    if expected.status == OrderStatus.PARTIALLY_FILLED and not (0 < expected.filled_quantity < expected.quantity - 1e-9):
        return unresolved("FREEZE_AND_RECONCILE", "OMS PARTIALLY_FILLED quantity is inconsistent")
    fill_match = abs(observed_filled - expected.filled_quantity) <= 1e-9
    status_match = expected.status == observed_status
    if status_match and fill_match:
        return ReconciliationResult(
            expected.order_id, expected.status, observed_status, True, "RESUME",
            "status and cumulative fill quantity match",
        )
    action = (
        "FREEZE_AND_RECONCILE"
        if expected.status not in _TERMINAL or observed_status not in _TERMINAL
        else "RECORD_MISMATCH"
    )
    return ReconciliationResult(
        expected.order_id, expected.status, observed_status, False, action,
        "OMS/broker status or cumulative fill quantity mismatch",
    )
