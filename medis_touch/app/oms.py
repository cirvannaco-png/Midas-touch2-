"""Deterministic order-management state machine with idempotency."""
from __future__ import annotations

from dataclasses import replace
from time import time

from .execution_models import ExecutionOrder, OrderStatus


_ALLOWED: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.NEW: {OrderStatus.VALIDATED, OrderStatus.REJECTED},
    OrderStatus.VALIDATED: {OrderStatus.ROUTING, OrderStatus.REJECTED},
    OrderStatus.ROUTING: {OrderStatus.WORKING, OrderStatus.REJECTED, OrderStatus.UNKNOWN},
    OrderStatus.WORKING: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.EXPIRED,
        OrderStatus.UNKNOWN,
    },
    OrderStatus.PARTIALLY_FILLED: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.UNKNOWN,
    },
    OrderStatus.CANCEL_PENDING: {OrderStatus.CANCELLED, OrderStatus.FILLED, OrderStatus.UNKNOWN},
    OrderStatus.UNKNOWN: {
        OrderStatus.WORKING,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.RECOVERY_REQUIRED,
    },
    OrderStatus.RECOVERY_REQUIRED: {
        OrderStatus.WORKING,
        OrderStatus.CANCELLED,
        OrderStatus.FILLED,
        OrderStatus.REJECTED,
    },
    OrderStatus.FILLED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.REJECTED: set(),
    OrderStatus.EXPIRED: set(),
}


class OrderManager:
    """In-memory OMS contract; persistence is supplied by the host service."""

    def __init__(self) -> None:
        self._orders: dict[str, ExecutionOrder] = {}
        self._idempotency: dict[str, str] = {}

    def submit(self, order: ExecutionOrder) -> ExecutionOrder:
        if order.order_id in self._orders:
            return self._orders[order.order_id]
        if order.idempotency_key:
            existing = self._idempotency.get(order.idempotency_key)
            if existing:
                return self._orders[existing]
            self._idempotency[order.idempotency_key] = order.order_id
        stored = replace(order, status=OrderStatus.NEW, updated_at=time())
        self._orders[order.order_id] = stored
        return stored

    def transition(self, order_id: str, status: OrderStatus) -> ExecutionOrder:
        order = self._orders[order_id]
        if status not in _ALLOWED[order.status]:
            raise ValueError(f"invalid OMS transition {order.status.value} -> {status.value}")
        updated = replace(order, status=status, updated_at=time())
        self._orders[order_id] = updated
        return updated

    def get(self, order_id: str) -> ExecutionOrder | None:
        return self._orders.get(order_id)

    def freeze_for_reconciliation(self, order_id: str) -> ExecutionOrder:
        order = self._orders[order_id]
        if order.status in {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED}:
            return order
        return self.transition(order_id, OrderStatus.RECOVERY_REQUIRED)

    def all_orders(self) -> tuple[ExecutionOrder, ...]:
        return tuple(self._orders.values())
