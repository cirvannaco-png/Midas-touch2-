"""Canonical institutional execution domain models.

The models are broker-agnostic and deliberately small.  They define the
contract shared by OMS, pre-trade risk, routing, TCA, and reconciliation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any


class OrderStatus(str, Enum):
    NEW = "NEW"
    VALIDATED = "VALIDATED"
    ROUTING = "ROUTING"
    WORKING = "WORKING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class ExecutionPolicy(str, Enum):
    MARKET = "MARKET"
    PASSIVE = "PASSIVE"
    TWAP = "TWAP"
    VWAP = "VWAP"
    POV = "POV"
    ADAPTIVE = "ADAPTIVE"


@dataclass(frozen=True)
class VenueQuote:
    venue: str
    symbol: str
    bid: float
    ask: float
    available_volume: float
    latency_ms: float
    fill_rate: float = 1.0
    rejection_rate: float = 0.0
    historical_slippage_bps: float = 0.0
    healthy: bool = True

    @property
    def spread(self) -> float:
        return max(0.0, self.ask - self.bid)


@dataclass
class ExecutionOrder:
    order_id: str
    decision_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str = "MARKET"
    limit_price: float | None = None
    policy: ExecutionPolicy = ExecutionPolicy.MARKET
    status: OrderStatus = OrderStatus.NEW
    venue: str | None = None
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    idempotency_key: str | None = None
    created_at: float = field(default_factory=time)
    updated_at: float = field(default_factory=time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def remaining_quantity(self) -> float:
        return max(0.0, self.quantity - self.filled_quantity)


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class TCAResult:
    order_id: str
    decision_price: float
    arrival_price: float
    average_fill_price: float | None
    quantity: float
    spread_cost: float = 0.0
    slippage_cost: float = 0.0
    market_impact_cost: float = 0.0
    implementation_shortfall: float | None = None


@dataclass(frozen=True)
class ReconciliationResult:
    order_id: str
    expected_status: OrderStatus
    observed_status: OrderStatus | None
    matched: bool
    action: str
    reason: str
