"""Regression tests for cost-stress, temporal folds, and Monte Carlo diagnostics."""
import csv
from pathlib import Path

import pytest

try:
    from tools.cost_stress_monte_carlo import (
        CostStressError,
        incremental_cost_for_position,
        monte_carlo_drawdown,
        performance_metrics,
        require_explicit_cost_columns,
    )
except ImportError:
    from cost_stress_monte_carlo import (  # type: ignore[no-redef]
        CostStressError,
        incremental_cost_for_position,
        monte_carlo_drawdown,
        performance_metrics,
        require_explicit_cost_columns,
    )


def test_incremental_spread_and_slippage_are_charged_per_executed_side():
    # One lot entered + one lot exited => two lot-sides. Four points of
    # extra full spread cost 2 points per side; one slippage point per side.
    assert incremental_cost_for_position(2.0, 1.0, 4.0, 1.0) == 6.0


def test_invalid_point_value_fails_closed():
    with pytest.raises(CostStressError, match="point value"):
        incremental_cost_for_position(2.0, 0.0, 2.0, 1.0)


def test_cost_analysis_rejects_missing_commission_swap_or_fee_column(tmp_path: Path):
    path = tmp_path / "deals.csv"
    path.write_text("position_id,time,entry,volume,profit,commission,fee\n", encoding="utf-8")
    with pytest.raises(CostStressError, match="swap"):
        require_explicit_cost_columns(path)


def test_cost_analysis_accepts_explicit_zero_cost_fields(tmp_path: Path):
    path = tmp_path / "deals.csv"
    path.write_text("position_id,time,entry,volume,profit,commission,swap,fee\n", encoding="utf-8")
    require_explicit_cost_columns(path)


def test_performance_metrics_capture_drawdown_and_loss_streak():
    result = performance_metrics([10.0, -12.0, -8.0, 4.0], 100.0)
    assert result["net_pnl"] == -6.0
    assert result["max_consecutive_losses"] == 2
    assert result["max_closed_trade_drawdown_cash"] == 20.0
    assert result["max_closed_trade_drawdown_pct"] == pytest.approx(18.181818, abs=1e-5)


def test_monte_carlo_is_reproducible_and_reports_ranges():
    first = monte_carlo_drawdown([10.0, -12.0, -8.0, 4.0], 100.0, 500, 9876)
    second = monte_carlo_drawdown([10.0, -12.0, -8.0, 4.0], 100.0, 500, 9876)
    assert first == second
    assert first["trade_shuffle_without_replacement"]["max_drawdown_cash_p05_p50_p95"][0] <= \
           first["trade_shuffle_without_replacement"]["max_drawdown_cash_p05_p50_p95"][2]
    assert "ending_balance_p05_p50_p95" in first["bootstrap_with_replacement"]


def test_monte_carlo_requires_at_least_100_simulations():
    with pytest.raises(CostStressError, match="at least 100"):
        monte_carlo_drawdown([1.0, -1.0], 100.0, 99, 1)
