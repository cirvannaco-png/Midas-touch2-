"""Latency-budget checks layered on top of the existing T0-T7 trace."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class LatencyBudget:
    detection_ms: float = 1000.0
    decision_ms: float = 250.0
    risk_ms: float = 100.0
    submission_ms: float = 300.0
    broker_ms: float = 1500.0
    total_signal_to_fill_ms: float = 5000.0


def violations(latencies: Mapping[str, float | None], budget: LatencyBudget | None = None) -> dict[str, float]:
    b = budget or LatencyBudget()
    limits = {
        "detection_latency_ms": b.detection_ms,
        "decision_latency_ms": b.decision_ms,
        "risk_latency_ms": b.risk_ms,
        "submission_latency_ms": b.submission_ms,
        "broker_latency_ms": b.broker_ms,
        "total_signal_to_fill_ms": b.total_signal_to_fill_ms,
    }
    return {
        key: float(latencies[key])
        for key, limit in limits.items()
        if latencies.get(key) is not None and float(latencies[key]) > limit
    }
