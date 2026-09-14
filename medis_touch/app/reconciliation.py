"""Broker/OMS reconciliation helpers. Unknown state always fails closed."""

from __future__ import annotations

from .execution_models import ExecutionOrder, OrderStatus, ReconciliationResult


_TERMINAL = {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED}


def reconcile(order: ExecutionOrder, broker_status: OrderStatus | None) -> ReconciliationResult:
    """Compare broker and OMS state; ambiguity freezes the order for recovery."""
    if broker_status is None or broker_status == OrderStatus.UNKNOWN:
        return ReconciliationResult(order.order_id, False, True, "FREEZE_AND_QUERY")
    if broker_status == order.status:
        return ReconciliationResult(order.order_id, True, False, "RESUME")
    if order.status in _TERMINAL and broker_status in _TERMINAL:
        return ReconciliationResult(order.order_id, False, True, "FREEZE_AND_QUERY")
    return ReconciliationResult(order.order_id, False, True, "FREEZE_AND_RECONCILE")
