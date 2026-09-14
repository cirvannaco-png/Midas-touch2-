"""Deterministic child-order schedules for TWAP, VWAP and POV."""
from __future__ import annotations

import math


def _validate(quantity: float, slices: int) -> None:
    if quantity <= 0 or slices <= 0:
        raise ValueError("quantity and slices must be positive")


def twap_schedule(quantity: float, slices: int) -> tuple[float, ...]:
    _validate(quantity, slices)
    child = quantity / slices
    return tuple(child for _ in range(slices))


def vwap_schedule(quantity: float, volume_profile: list[float]) -> tuple[float, ...]:
    if quantity <= 0 or not volume_profile or any(v < 0 for v in volume_profile):
        raise ValueError("quantity and non-negative volume profile are required")
    total = sum(volume_profile)
    if total <= 0:
        raise ValueError("volume profile must contain positive volume")
    return tuple(quantity * v / total for v in volume_profile)


def pov_schedule(quantity: float, observed_volumes: list[float], participation: float) -> tuple[float, ...]:
    if quantity <= 0 or participation <= 0 or participation > 1 or not observed_volumes:
        raise ValueError("invalid POV parameters")
    remaining = quantity
    result: list[float] = []
    for volume in observed_volumes:
        child = min(remaining, max(0.0, volume) * participation)
        result.append(child)
        remaining -= child
        if remaining <= 1e-12:
            break
    if remaining > 1e-12:
        result.append(remaining)
    return tuple(result)


def adaptive_policy(*, spread_bps: float, volatility: float, fill_probability: float,
                    urgency: float) -> str:
    """Select policy from current observable state only; no future data."""
    if not 0 <= urgency <= 1 or not 0 <= fill_probability <= 1:
        raise ValueError("urgency and fill probability must be in [0, 1]")
    pressure = 0.45 * urgency + 0.25 * volatility + 0.30 * (1.0 - fill_probability)
    if pressure >= 0.75:
        return "MARKET"
    if pressure <= 0.30 and spread_bps <= 3.0:
        return "PASSIVE"
    return "ADAPTIVE"
