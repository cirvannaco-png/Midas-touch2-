from dataclasses import dataclass

from regime_allocation import RegimeAllocationThresholds, build_regime_allocations, propose_multiplier


@dataclass
class Row:
    regime: str
    outcome: str
    realized_r: float | None


def test_small_sample_holds_allocation():
    thresholds = RegimeAllocationThresholds(min_trades=50)
    value, reason = propose_multiplier(
        {"trades": 49, "wins": 40, "avg_r": 0.5, "max_drawdown_r": 2},
        0.5,
        thresholds,
    )
    assert value == 0.5
    assert "sample" in reason


def test_weak_regime_cannot_increase_allocation():
    thresholds = RegimeAllocationThresholds(min_trades=50)
    value, reason = propose_multiplier(
        {"trades": 80, "wins": 42, "avg_r": 0.20, "max_drawdown_r": 2},
        0.5,
        thresholds,
    )
    assert value == 0.5
    assert "Wilson" in reason


def test_drawdown_gate_holds_even_with_good_win_rate():
    thresholds = RegimeAllocationThresholds(min_trades=50)
    value, reason = propose_multiplier(
        {"trades": 100, "wins": 70, "avg_r": 0.3, "max_drawdown_r": 8},
        0.5,
        thresholds,
    )
    assert value == 0.5
    assert "drawdown" in reason


def test_qualified_regime_can_increase_discretely():
    thresholds = RegimeAllocationThresholds(min_trades=50)
    value, reason = propose_multiplier(
        {"trades": 200, "wins": 140, "avg_r": 0.40, "max_drawdown_r": 3},
        0.5,
        thresholds,
    )
    assert value > 0.5
    assert value <= 1.0
    assert reason.startswith("INCREASE:")


def test_build_allocations_carries_previous_value_for_weak_regime():
    rows = [
        Row("TRENDING", "win", 1.0),
        Row("TRENDING", "loss", -1.0),
        Row("RANGING", "win", 1.0),
    ]
    result = build_regime_allocations(
        rows,
        previous={"TRENDING": 0.70, "RANGING": 0.40},
        thresholds=RegimeAllocationThresholds(min_trades=50),
    )
    assert result["TRENDING"]["risk_multiplier"] == 0.70
    assert result["RANGING"]["risk_multiplier"] == 0.40
    assert not result["TRENDING"]["statistically_qualified"]


def test_build_allocations_ignores_unresolved_and_missing_r():
    rows = [
        Row("TRENDING", "win", 1.0),
        Row("TRENDING", "no_fill", None),
        Row("TRENDING", "ambiguous", None),
        Row("TRENDING", "loss", None),
    ]
    result = build_regime_allocations(rows, thresholds=RegimeAllocationThresholds(min_trades=1))
    # Only the resolved row with a realized R is evidence. The missing-R
    # loss must not be silently treated as zero expectancy.
    assert result["TRENDING"]["metrics"]["trades"] == 1
    assert result["TRENDING"]["metrics"]["avg_r"] == 1.0
