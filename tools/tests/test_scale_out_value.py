import pytest

from tools.research.scale_out_value import compare_scale_out_policies


def _rows():
    return [
        {"trade_id": "1", "policy": "full_exit", "realized_r": 1.0, "mfe_r": 2.0, "source": "STRATEGY_TESTER_REPLAY"},
        {"trade_id": "2", "policy": "full_exit", "realized_r": -0.5, "mfe_r": 0.5, "source": "STRATEGY_TESTER_REPLAY"},
        {"trade_id": "1", "policy": "half_at_1r", "realized_r": 1.2, "mfe_r": 2.0, "source": "STRATEGY_TESTER_REPLAY"},
        {"trade_id": "2", "policy": "half_at_1r", "realized_r": -0.1, "mfe_r": 0.5, "source": "STRATEGY_TESTER_REPLAY"},
    ]


def test_scale_out_compares_paired_policies():
    report = compare_scale_out_policies(_rows(), benchmark_policy="full_exit")
    assert report.paired_expectancy_delta_r["half_at_1r"] == pytest.approx(0.4)
    assert report.paired_outperformance_fraction["half_at_1r"] == 0.5


def test_scale_out_rejects_unpaired_policy():
    rows = _rows() + [
        {
            "trade_id": "3",
            "policy": "half_at_1r",
            "realized_r": 0.2,
            "source": "STRATEGY_TESTER_REPLAY",
        }
    ]
    with pytest.raises(ValueError, match="not paired"):
        compare_scale_out_policies(rows, benchmark_policy="full_exit")
