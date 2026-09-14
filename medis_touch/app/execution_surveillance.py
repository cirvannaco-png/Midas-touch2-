"""Deterministic execution-health surveillance signals."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurveillanceAlert:
    code: str
    severity: str
    message: str


def inspect(*, rejection_rate: float, slippage_bps: float, p99_latency_ms: float,
            duplicate_order_count: int = 0, venue_healthy: bool = True) -> tuple[SurveillanceAlert, ...]:
    alerts: list[SurveillanceAlert] = []
    if not venue_healthy:
        alerts.append(SurveillanceAlert("VENUE_UNHEALTHY", "CRITICAL", "execution venue is unhealthy"))
    if rejection_rate > 0.20:
        alerts.append(SurveillanceAlert("REJECTION_SPIKE", "HIGH", "order rejection rate exceeds 20%"))
    if slippage_bps > 10.0:
        alerts.append(SurveillanceAlert("SLIPPAGE_SPIKE", "HIGH", "execution slippage exceeds 10 bps"))
    if p99_latency_ms > 1000.0:
        alerts.append(SurveillanceAlert("LATENCY_SPIKE", "HIGH", "p99 execution latency exceeds 1 second"))
    if duplicate_order_count > 0:
        alerts.append(SurveillanceAlert("DUPLICATE_ORDER", "CRITICAL", "duplicate order activity detected"))
    return tuple(alerts)
