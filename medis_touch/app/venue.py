"""Broker-neutral execution venue contract and deterministic simulator."""

from dataclasses import dataclass, field
from typing import Protocol

from .execution_models import ExecutionFill, ExecutionOrder, VenueQuote


class ExecutionVenue(Protocol):
    name: str

    def quote(self, symbol: str) -> VenueQuote: ...
    def submit(self, order: ExecutionOrder) -> str: ...
    def fill(self, order: ExecutionOrder, venue_order_id: str, price: float) -> ExecutionFill: ...
    def cancel(self, venue_order_id: str) -> bool: ...
    def reconcile(self, venue_order_id: str) -> dict: ...

    def reconcile_by_client_order_id(self, client_order_id: str) -> dict: ...


@dataclass
class SimulatedVenue:
    name: str
    bid: float
    ask: float
    available_volume: float
    latency_ms: float = 10.0
    _submitted_orders: dict[str, ExecutionOrder] = field(default_factory=dict, init=False, repr=False)
    _fills_by_order: dict[str, ExecutionFill] = field(default_factory=dict, init=False, repr=False)
    _client_order_index: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def quote(self, symbol: str) -> VenueQuote:
        return VenueQuote(self.name, symbol, self.bid, self.ask, self.available_volume, self.latency_ms)

    def submit(self, order: ExecutionOrder) -> str:
        if order.quantity <= 0 or order.quantity > self.available_volume:
            raise RuntimeError("simulated venue rejected order")
        if order.venue is not None and order.venue != self.name:
            raise RuntimeError("order routed to the wrong venue")
        venue_order_id = f"{self.name}:{order.order_id}"
        previous = self._submitted_orders.get(venue_order_id)
        if previous is not None:
            if (
                previous.idempotency_key != order.idempotency_key
                or previous.decision_id != order.decision_id
                or previous.quantity != order.quantity
            ):
                raise RuntimeError("simulated venue order identity was reused with different parameters")
            return venue_order_id
        self._submitted_orders[venue_order_id] = order
        self._client_order_index[order.order_id] = venue_order_id
        if order.idempotency_key:
            self._client_order_index[order.idempotency_key] = venue_order_id
        return venue_order_id

    def fill(self, order: ExecutionOrder, venue_order_id: str, price: float) -> ExecutionFill:
        if not venue_order_id or price <= 0 or venue_order_id not in self._submitted_orders:
            raise RuntimeError("invalid simulated fill identity or price")
        existing = self._fills_by_order.get(venue_order_id)
        if existing is not None:
            if existing.quantity != order.quantity or existing.price != price:
                raise RuntimeError("simulated fill identity was replayed with different values")
            return existing
        if order.side.upper() == "BUY" and price < self.ask:
            raise RuntimeError("buy fill is below simulated ask")
        if order.side.upper() == "SELL" and price > self.bid:
            raise RuntimeError("sell fill is above simulated bid")
        fill = ExecutionFill(
            fill_id=f"{venue_order_id}:fill",
            order_id=order.order_id,
            venue_order_id=venue_order_id,
            quantity=order.quantity,
            price=price,
        )
        self._fills_by_order[venue_order_id] = fill
        return fill

    def cancel(self, venue_order_id: str) -> bool:
        return bool(venue_order_id)

    def reconcile(self, venue_order_id: str) -> dict:
        if not venue_order_id or venue_order_id not in self._submitted_orders:
            return {"venue_order_id": venue_order_id, "status": "UNKNOWN"}
        fill = self._fills_by_order.get(venue_order_id)
        if fill is None:
            return {"venue_order_id": venue_order_id, "status": "WORKING", "filled_quantity": 0.0}
        return {
            "venue_order_id": venue_order_id,
            "status": "FILLED",
            "filled_quantity": fill.quantity,
            "average_fill_price": fill.price,
        }

    def reconcile_by_client_order_id(self, client_order_id: str) -> dict:
        if not client_order_id:
            return {"client_order_id": client_order_id, "status": "UNKNOWN"}
        venue_order_id = self._client_order_index.get(client_order_id)
        if venue_order_id is None:
            return {"client_order_id": client_order_id, "status": "UNKNOWN"}
        result = self.reconcile(venue_order_id)
        return {**result, "client_order_id": client_order_id}
