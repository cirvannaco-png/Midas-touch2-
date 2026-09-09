from __future__ import annotations

import pytest

from app.dynamic_stop_policy import (
    DYNAMIC_STOP_POLICY_VERSION,
    canonical_dynamic_stop_json,
    canonical_dynamic_stop_policy,
    dynamic_stop_policy_hash,
)


def test_defaults_are_canonical_and_deterministic() -> None:
    policy = canonical_dynamic_stop_policy()
    assert policy["version"] == DYNAMIC_STOP_POLICY_VERSION
    assert policy["activate_at_r"] == 0.75
    assert policy["breakeven_at_r"] == 1.0
    assert policy["atr_multiplier"] == 1.5
    assert policy["min_modify_interval_sec"] == 5
    assert dynamic_stop_policy_hash(policy) == dynamic_stop_policy_hash(dict(policy))
    assert canonical_dynamic_stop_json(policy) == canonical_dynamic_stop_json(dict(policy))


def test_same_policy_order_cannot_change_hash() -> None:
    a = canonical_dynamic_stop_policy(max_spread_points=30, min_atr=0.5)
    b = {
        "max_atr": 0.0,
        "min_modify_interval_sec": 5,
        "max_spread_points": 30,
        "atr_multiplier": 1.5,
        "breakeven_at_r": 1.0,
        "activate_at_r": 0.75,
        "min_improvement_points": 2.0,
        "min_atr": 0.5,
        "version": DYNAMIC_STOP_POLICY_VERSION,
    }
    assert dynamic_stop_policy_hash(a) == dynamic_stop_policy_hash(b)


def test_invalid_ordering_is_rejected() -> None:
    with pytest.raises(ValueError):
        canonical_dynamic_stop_policy(activate_at_r=1.0, breakeven_at_r=0.75)
    with pytest.raises(ValueError):
        canonical_dynamic_stop_policy(min_atr=2.0, max_atr=1.0)


def test_hash_rejects_unknown_policy_version() -> None:
    policy = canonical_dynamic_stop_policy()
    policy["version"] = "dynamic-stop-v0"
    with pytest.raises(ValueError):
        dynamic_stop_policy_hash(policy)
