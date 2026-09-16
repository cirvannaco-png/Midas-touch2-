"""Deterministic order-management state machine with idempotency."""
# ruff: noqa: I001

import time
from dataclasses import replace

from .execution_models import ExecutionFill, ExecutionOrder, OrderStatus


_ALLOWED: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.NEW: {OrderStatus.VALIDATED, OrderStatus.REJECTED},
    OrderStatus.VALIDATED: {OrderStatus.ROUTING, OrderStatus.REJECTED},
    OrderStatus.ROUTING: {OrderStatus.WORKING, OrderStatus.REJECTED, OrderStatus.UNKNOWN},
    OrderStatus.WORKING: {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCEL_PENDING, OrderStatus.EXPIRED, OrderStatus.UNKNOWN},
    OrderStatus.PARTIALLY_FILLED: {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCEL_PENDING, OrderStatus.UNKNOWN},
    OrderStatus.CANCEL_PENDING: {OrderStatus.CANCELLED, OrderStatus.FILLED, OrderStatus.UNKNOWN},
    OrderStatus.UNKNOWN: {OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.RECOVERY_REQUIRED},
    OrderStatus.RECOVERY_REQUIRED: {OrderStatus.WORKING, OrderStatus.CANCELLED, OrderStatus.FILLED, OrderStatus.REJECTED},
    OrderStatus.FILLED: set(), OrderStatus.CANCELLED: set(), OrderStatus.REJECTED: set(), OrderStatus.EXPIRED: set(),
}


class OrderManager:
    """In-memory OMS contract; persistence is supplied by the host service."""

    def __init__(self, *, require_governance: bool = False) -> None:
        self._orders: dict[str, ExecutionOrder] = {}
        self._idempotency: dict[str, str] = {}
        self._fingerprints: dict[str, tuple[object, ...]] = {}
        self._fills: dict[str, set[str]] = {}
        self._require_governance = require_governance

    @staticmethod
    def _fingerprint(order: ExecutionOrder) -> tuple[object, ...]:
        return (order.decision_id, order.symbol, order.side.upper(), order.quantity,
                order.order_type, order.limit_price, order.policy.value, order.idempotency_key,
                order.metadata.get("execution_config_hash"), order.metadata.get("execution_model_hash"))

    def submit(self, order: ExecutionOrder) -> ExecutionOrder:
        if self._require_governance and not order.metadata.get("execution_config_hash"):
            raise ValueError("execution configuration hash is required")
        fingerprint = self._fingerprint(order)
        if order.order_id in self._orders:
            if self._fingerprints[order.order_id] != fingerprint:
                raise ValueError("order_id already exists with different order identity")
            return self._orders[order.order_id]
        if order.idempotency_key:
            existing = self._idempotency.get(order.idempotency_key)
            if existing:
                if self._fingerprints[existing] != fingerprint:
                    raise ValueError("idempotency key already exists with different order identity")
                return self._orders[existing]
            self._idempotency[order.idempotency_key] = order.order_id
        stored = replace(order, status=OrderStatus.NEW, updated_at=time.time())
        self._orders[order.order_id] = stored
        self._fingerprints[order.order_id] = fingerprint
        self._fills[order.order_id] = set()
        return stored

    def transition(self, order_id: str, status: OrderStatus) -> ExecutionOrder:
        order = self._orders[order_id]
        if status not in _ALLOWED[order.status]:
            raise ValueError(f"invalid OMS transition {order.status.value} -> {status.value}")
        updated = replace(order, status=status, updated_at=time.time())
        self._orders[order_id] = updated
        return updated

    def record_fill(self, fill: ExecutionFill) -> ExecutionOrder:
        order = self._orders[fill.order_id]
        if fill.fill_id in self._fills[fill.order_id]:
            return order
        if fill.quantity <= 0 or fill.price <= 0:
            raise ValueError("fill quantity and price must be positive")
        if fill.quantity > order.remaining_quantity + 1e-12:
            raise ValueError("fill exceeds remaining order quantity")
        old_qty = order.filled_quantity
        new_qty = old_qty + fill.quantity
        average = fill.price if order.average_fill_price is None else ((order.average_fill_price * old_qty) + (fill.price * fill.quantity)) / new_qty
        status = OrderStatus.FILLED if abs(new_qty - order.quantity) <= 1e-12 else OrderStatus.PARTIALLY_FILLED
        self._fills[fill.order_id].add(fill.fill_id)
        updated = replace(order, filled_quantity=new_qty, average_fill_price=average, status=status, updated_at=time.time())
        self._orders[fill.order_id] = updated
        return updated

    def get(self, order_id: str) -> ExecutionOrder | None:
        return self._orders.get(order_id)

    def freeze_for_reconciliation(self, order_id: str) -> ExecutionOrder:
        order = self._orders[order_id]
        if order.status in {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED}:
            return order
        if order.status == OrderStatus.UNKNOWN:
            return self.transition(order_id, OrderStatus.RECOVERY_REQUIRED)
        return replace(order, status=OrderStatus.RECOVERY_REQUIRED, updated_at=time.time())

    def all_orders(self) -> tuple[ExecutionOrder, ...]:
        return tuple(self._orders.values())
