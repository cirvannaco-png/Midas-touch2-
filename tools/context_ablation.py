"""Observed confluence attribution for HTF OB, value area and environment state."""
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
    return ContextMetrics(
        n=len(values),
        expectancy_r=mean(values),
        win_rate=wins / len(values),
        profit_factor=gross_profit / gross_loss if gross_loss else (inf if gross_profit else 0.0),
    )


def observed_slices(rows, *, min_sample: int = 30) -> dict[str, ContextMetrics]:
    """Return four observed slices; no causal claim is made.

    Base+HTF-OB and Base+VA are conditional subsets. A genuine causal
    confluence test requires Strategy Tester replay with the feature toggled
    while spread, commission, slippage and execution assumptions remain fixed.
    """
    resolved = [r for r in rows if getattr(r, "outcome", None) in {"win", "loss", "scratch"}]
    htf = [r for r in resolved if bool(_environment(r).get("htf_ob_aligned") or _environment(r).get("htf_ob_state") not in (None, "OB_MITIGATED"))]
    va = [r for r in resolved if _environment(r).get("value_area_zone") not in (None, "VA_ZONE_UNDEFINED")]
    both_ids = {getattr(r, "signal_id", id(r)) for r in htf} & {getattr(r, "signal_id", id(r)) for r in va}
    both = [r for r in resolved if getattr(r, "signal_id", id(r)) in both_ids]
    return {
        "base": _metrics(resolved),
        "base_plus_htf_ob": _metrics(htf) if len(htf) >= min_sample else ContextMetrics(len(htf), None, None, None),
        "base_plus_value_area": _metrics(va) if len(va) >= min_sample else ContextMetrics(len(va), None, None, None),
        "base_plus_both": _metrics(both) if len(both) >= min_sample else ContextMetrics(len(both), None, None, None),
    }
