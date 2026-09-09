"""Canonical Dynamic Stop Engine v1 policy identity.

The EA and recalibration registry must describe the same policy using the
same field names and numeric values. This module provides the backend-side
canonical payload and hash input; it does not activate a configuration.
"""
from __future__ import annotations

from collections.abc import Mapping

from app.config_registry import canonical_config, configuration_hash

DYNAMIC_STOP_POLICY_VERSION = "dynamic-stop-v1"
DYNAMIC_STOP_KEYS = (
    "version",
    "activate_at_r",
    "breakeven_at_r",
    "atr_multiplier",
    "min_improvement_points",
    "max_spread_points",
    "min_atr",
    "max_atr",
    "min_modify_interval_sec",
)


def canonical_dynamic_stop_policy(
    *,
    activate_at_r: float = 0.75,
    breakeven_at_r: float = 1.0,
    atr_multiplier: float = 1.5,
    min_improvement_points: float = 2.0,
    max_spread_points: int = 0,
    min_atr: float = 0.0,
    max_atr: float = 0.0,
    min_modify_interval_sec: int = 5,
) -> dict[str, object]:
    """Return the exact identity payload for Dynamic Stop Engine v1."""
    values = {
        "version": DYNAMIC_STOP_POLICY_VERSION,
        "activate_at_r": float(activate_at_r),
        "breakeven_at_r": float(breakeven_at_r),
        "atr_multiplier": float(atr_multiplier),
        "min_improvement_points": float(min_improvement_points),
        "max_spread_points": int(max_spread_points),
        "min_atr": float(min_atr),
        "max_atr": float(max_atr),
        "min_modify_interval_sec": int(min_modify_interval_sec),
    }
    if values["activate_at_r"] < 0 or values["breakeven_at_r"] < values["activate_at_r"]:
        raise ValueError("breakeven_at_r must be >= activate_at_r >= 0")
    if values["atr_multiplier"] <= 0 or values["min_improvement_points"] < 0:
        raise ValueError("ATR multiplier must be positive and improvement threshold non-negative")
    if values["max_spread_points"] < 0 or values["min_atr"] < 0 or values["max_atr"] < 0:
        raise ValueError("protection bounds cannot be negative")
    if values["max_atr"] and values["max_atr"] < values["min_atr"]:
        raise ValueError("max_atr must be >= min_atr when both are set")
    if values["min_modify_interval_sec"] < 0:
        raise ValueError("modification interval cannot be negative")
    return values


def dynamic_stop_policy_hash(policy: Mapping[str, object]) -> str:
    """Hash only a validated, canonical Dynamic Stop policy payload."""
    canonical = canonical_dynamic_stop_policy(
        activate_at_r=policy["activate_at_r"],
        breakeven_at_r=policy["breakeven_at_r"],
        atr_multiplier=policy["atr_multiplier"],
        min_improvement_points=policy["min_improvement_points"],
        max_spread_points=policy["max_spread_points"],
        min_atr=policy["min_atr"],
        max_atr=policy["max_atr"],
        min_modify_interval_sec=policy["min_modify_interval_sec"],
    )
    if policy.get("version") != DYNAMIC_STOP_POLICY_VERSION:
        raise ValueError("unsupported Dynamic Stop policy version")
    return configuration_hash(canonical)


def canonical_dynamic_stop_json(policy: Mapping[str, object]) -> str:
    """Return the deterministic JSON representation used by the hash boundary."""
    return canonical_config(policy)
