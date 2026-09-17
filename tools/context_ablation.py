"""Observed confluence attribution for HTF OB and environment state.

These are attribution diagnostics, not causal claims. Causal feature value is
validated by Strategy Tester replays with identical execution assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import inf
from statistics import mean


@dataclass(frozen=True)
class ContextMetrics:
    n: int
    expectancy_r: float | None
    win_rate: float | None
    profit_factor: float | None


@dataclass(frozen=True)
class ContextEffect:
    present: ContextMetrics
    absent: ContextMetrics
    expectancy_delta_r: float | None
    enough_data: bool


def _environment(row) -> dict:
    value = getattr(row, "environment", None)
    return value if isinstance(value, dict) else {}


def _metrics(rows) -> ContextMetrics:
    values = [r.realized_r for r in rows if r.realized_r is not None]
    if not values:
        return ContextMetrics(0, None, None, None)
    wins = sum(v > 0 for v in values)
    gross_profit = sum(v for v in values if v > 0)
    gross_loss = -sum(v for v in values if v < 0)
    return ContextMetrics(len(values), mean(values), wins / len(values), gross_profit / gross_loss if gross_loss else (inf if gross_profit else 0.0))


def _effect(rows, predicate, min_sample: int) -> ContextEffect:
    present_rows = [r for r in rows if predicate(_environment(r))]
    absent_rows = [r for r in rows if not predicate(_environment(r))]
    present = _metrics(present_rows) if len(present_rows) >= min_sample else ContextMetrics(len(present_rows), None, None, None)
    absent = _metrics(absent_rows) if len(absent_rows) >= min_sample else ContextMetrics(len(absent_rows), None, None, None)
    delta = None if present.expectancy_r is None or absent.expectancy_r is None else present.expectancy_r - absent.expectancy_r
    return ContextEffect(present, absent, delta, delta is not None)


def observed_slices(rows, *, min_sample: int = 30) -> dict[str, ContextMetrics]:
    resolved = [r for r in rows if getattr(r, "outcome", None) in {"win", "loss", "scratch"}]
    htf = [r for r in resolved if bool(_environment(r).get("htf_ob_aligned") or _environment(r).get("htf_ob_state") not in (None, "OB_MITIGATED"))]
    va = [r for r in resolved if _environment(r).get("value_area_zone") not in (None, "VA_ZONE_UNDEFINED")]
    htf_ids = {getattr(r, "signal_id", id(r)) for r in htf}
    va_ids = {getattr(r, "signal_id", id(r)) for r in va}
    both = [r for r in resolved if getattr(r, "signal_id", id(r)) in htf_ids & va_ids]
    def gated(items):
        return _metrics(items) if len(items) >= min_sample else ContextMetrics(len(items), None, None, None)
    return {"base": _metrics(resolved), "base_plus_htf_ob": gated(htf), "base_plus_value_area": gated(va), "base_plus_both": gated(both)}


def context_effects(rows, *, min_sample: int = 30) -> dict[str, ContextEffect]:
    """Measure present-vs-absent expectancy for each environment context."""
    resolved = [r for r in rows if getattr(r, "outcome", None) in {"win", "loss", "scratch"}]
    predicates = {
        "htf_order_block": lambda e: bool(e.get("htf_ob_aligned") or e.get("htf_ob_state") not in (None, "OB_MITIGATED")),
        "value_area": lambda e: e.get("value_area_zone") not in (None, "VA_ZONE_UNDEFINED"),
        "liquidity": lambda e: float(e.get("liquidity_score") or 0.0) > 0.0 or int(e.get("liquidity_bucket") or 0) > 0,
        "market_structure": lambda e: bool(e.get("market_structure")),
        "volatility": lambda e: e.get("volatility_state") not in (None, "VOL_REGIME_UNDEFINED"),
        "news_clear": lambda e: e.get("news_state") in (None, "NEWS_NONE"),
    }
    return {name: _effect(resolved, predicate, min_sample) for name, predicate in predicates.items()}
