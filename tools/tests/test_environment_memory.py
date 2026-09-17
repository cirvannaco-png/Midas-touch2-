from types import SimpleNamespace

from environment_memory import aggregate, wilson_interval


def _row(**overrides):
    values = {
        "symbol": "XAUUSD",
        "strategy": "STRATEGY_MOMENTUM_BREAKOUT",
        "environment_key": "TRENDING|VOL_REGIME_NORMAL|T1",
        "regime": "REGIME_TRENDING",
        "session": "SESSION_LONDON",
        "outcome": "win",
        "realized_r": 1.0,
        "mfe_r": 1.4,
        "mae_r": 0.2,
        "bars_held": 4,
        "received_at": None,
        "environment": {
            "regime": "REGIME_TRENDING",
            "volatility_state": "VOL_REGIME_NORMAL",
            "news_state": "NEWS_NONE",
            "session": "SESSION_LONDON",
            "htf_ob_state": "OB_FRESH",
            "value_area_zone": "VA_ZONE_BELOW",
            "market_phase": "PHASE_DISTRIBUTION",
            "market_structure": "SWEEP_GRADE_A/1/0/0",
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_wilson_interval_is_bounded():
    low, high = wilson_interval(8, 10)
    assert 0.0 <= low <= high <= 1.0


def test_no_fill_and_ambiguous_are_excluded():
    rows = [_row()] * 10 + [_row(outcome="loss", realized_r=-1.0) for _ in range(10)]
    rows += [_row(outcome="no_fill", realized_r=None), _row(outcome="ambiguous", realized_r=None)]
    key, evidence = next(iter(aggregate(rows, min_sample=30).items()))
    assert evidence.trades == 20
    assert evidence.wins == 10
    assert evidence.losses == 10
    assert evidence.status == "UNKNOWN"


def test_positive_environment_strategy_cell_requires_statistical_evidence():
    rows = [_row() for _ in range(30)]
    rows += [_row(outcome="loss", realized_r=-0.5) for _ in range(5)]
    evidence = next(iter(aggregate(rows, min_sample=30).values()))
    assert evidence.trades == 35
    assert evidence.expectancy_r > 0
    assert evidence.status in {"QUALIFIED", "NEUTRAL", "DEGRADED"}


def test_strategy_is_part_of_environment_memory_key():
    rows = [_row() for _ in range(30)] + [_row(strategy="STRATEGY_SMC") for _ in range(30)]
    matrix = aggregate(rows, min_sample=30)
    assert len(matrix) == 2
    assert {key[1] for key in matrix} == {"STRATEGY_MOMENTUM_BREAKOUT", "STRATEGY_SMC"}
