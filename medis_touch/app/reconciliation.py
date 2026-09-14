"""Broker/OMS reconciliation helpers. Unknown state always fails closed."""
from __future__ import annotations

from .execution_models import ExecutionOrder, OrderStatus, ReconciliationResult


_TERMINAL = {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED}


def reconcile(
    expected: ExecutionOrder,
    observed_status: OrderStatus | None,
    observed_filled: float | None = None,
) -> ReconciliationResult:
    if observed_status is None:
        return ReconciliationResult(
            expected.order_id, expected.status, None, False, "FREEZE_AND_QUERY", "broker state unavailable"
        )
    if observed_status == OrderStatus.UNKNOWN:
        return ReconciliationResult(
            expected.order_id,
            expected.status,
            observed_status,
            False,
            "FREEZE_AND_QUERY",
            "broker returned ambiguous state",
        )
    fill_match = observed_filled is None or abs(observed_filled - expected.filled_quantity) < 1e-12
    status_match = expected.status == observed_status
    if status_match and fill_match:
        return ReconciliationResult(
            expected.order_id, expected.status, observed_status, True, "RESUME", "state matches"
        )
    action = (
        "FREEZE_AND_RECONCILE"
        if expected.status not in _TERMINAL or observed_status not in _TERMINAL
        else "RECORD_MISMATCH"
    )
    return ReconciliationResult(
        expected.order_id, expected.status, observed_status, False, action, "OMS/broker state mismatch"
    )
