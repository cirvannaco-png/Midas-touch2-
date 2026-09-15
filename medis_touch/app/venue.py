"""Broker-neutral execution venue contract and deterministic simulator."""

from dataclasses import dataclass
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

    def quote(self, symbol: str) -> VenueQuote:
        return VenueQuote(self.name, symbol, self.bid, self.ask, self.available_volume, self.latency_ms)

    def submit(self, order: ExecutionOrder) -> str:
        if order.quantity <= 0 or order.quantity > self.available_volume:
            raise RuntimeError("simulated venue rejected order")
        if order.venue is not None and order.venue != self.name:
            raise RuntimeError("order routed to the wrong venue")
        return f"{self.name}:{order.order_id}"

    def fill(self, order: ExecutionOrder, venue_order_id: str, price: float) -> ExecutionFill:
        if not venue_order_id or price <= 0:
            raise RuntimeError("invalid simulated fill")
        if order.side.upper() == "BUY" and price < self.ask:
            raise RuntimeError("buy fill is below simulated ask")
        if order.side.upper() == "SELL" and price > self.bid:
            raise RuntimeError("sell fill is above simulated bid")
        return ExecutionFill(fill_id=f"{venue_order_id}:fill", order_id=order.order_id, venue_order_id=venue_order_id, quantity=order.quantity, price=price)

    def cancel(self, venue_order_id: str) -> bool:
        return bool(venue_order_id)

    def reconcile(self, venue_order_id: str) -> dict:
        if not venue_order_id:
            return {"status": "UNKNOWN"}
        return {"venue_order_id": venue_order_id, "status": "FILLED"}

    def reconcile_by_client_order_id(self, client_order_id: str) -> dict:
        if not client_order_id:
            return {"status": "UNKNOWN"}
        return {"client_order_id": client_order_id, "venue_order_id": f"{self.name}:{client_order_id}", "status": "FILLED"}
