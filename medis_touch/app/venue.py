"""Broker-neutral execution venue contract and deterministic simulator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .execution_models import ExecutionOrder, VenueQuote


class ExecutionVenue(Protocol):
    name: str

    def quote(self, symbol: str) -> VenueQuote: ...
    def submit(self, order: ExecutionOrder) -> str: ...
    def cancel(self, venue_order_id: str) -> bool: ...
    def reconcile(self, venue_order_id: str) -> dict: ...


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
        return f"{self.name}:{order.order_id}"

    def cancel(self, venue_order_id: str) -> bool:
        return bool(venue_order_id)

    def reconcile(self, venue_order_id: str) -> dict:
        return {"venue_order_id": venue_order_id, "status": "WORKING"}
