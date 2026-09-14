"""Deterministic order-management state machine with idempotency."""

import time
from dataclasses import replace

from .execution_models import ExecutionOrder, OrderStatus


_ALLOWED: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.NEW: {OrderStatus.VALIDATED, OrderStatus.REJECTED},
    OrderStatus.VALIDATED: {OrderStatus.ROUTING, OrderStatus.REJECTED},
    OrderStatus.ROUTING: {OrderStatus.WORKING, OrderStatus.REJECTED, OrderStatus.UNKNOWN},
    OrderStatus.WORKING: {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCEL_PENDING, OrderStatus.UNKNOWN},
    OrderStatus.PARTIALLY_FILLED: {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCEL_PENDING, OrderStatus.UNKNOWN},
    OrderStatus.CANCEL_PENDING: {OrderStatus.CANCELLED, OrderStatus.FILLED, OrderStatus.UNKNOWN},
    OrderStatus.UNKNOWN: {OrderStatus.RECOVERY_REQUIRED},
    OrderStatus.RECOVERY_REQUIRED: {OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED},
    OrderStatus.FILLED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.REJECTED: set(),
    OrderStatus.EXPIRED: set(),
}


class OMS:
    """Idempotent order state machine with fail-closed ambiguity handling."""

    def __init__(self) -> None:
        self._orders: dict[str, ExecutionOrder] = {}
        self._idempotency: dict[str, str] = {}
        self._frozen = False

    def submit(self, order: ExecutionOrder) -> ExecutionOrder:
        if self._frozen:
            raise RuntimeError("OMS frozen for reconciliation")
        key = order.idempotency_key or order.order_id
        existing_id = self._idempotency.get(key)
        if existing_id is not None:
            return self._orders[existing_id]
        if order.order_id in self._orders:
            raise ValueError(f"duplicate order_id: {order.order_id}")
        now = time.time()
        stored = replace(order, updated_at=now)
        self._orders[stored.order_id] = stored
        self._idempotency[key] = stored.order_id
        return stored

    def transition(self, order_id: str, status: OrderStatus) -> ExecutionOrder:
        order = self._orders[order_id]
        if status not in _ALLOWED[order.status]:
            raise ValueError(f"invalid transition {order.status} -> {status}")
        if status == OrderStatus.UNKNOWN:
            status = OrderStatus.RECOVERY_REQUIRED
        updated = replace(order, status=status, updated_at=time.time())
        self._orders[order_id] = updated
        return updated

    def get(self, order_id: str) -> ExecutionOrder:
        return self._orders[order_id]

    def freeze_for_reconciliation(self) -> None:
        self._frozen = True

    def all_orders(self) -> tuple[ExecutionOrder, ...]:
        return tuple(self._orders.values())
