from medis_touch.app.execution_research import (
    ExecutionObservation,
    group_by_venue_and_regime,
    stress_shortfall,
    summarize,
)


def test_summary_and_attribution_are_deterministic() -> None:
    observations = [
        ExecutionObservation("v1", "normal", 2, 1.0, 2.0, 1.0),
        ExecutionObservation("v1", "transition", 3, 2.0, 4.0, 2.0),
        ExecutionObservation("v2", "normal", 5, 3.0, 6.0, 3.0),
    ]
    summary = summarize(observations)
    assert summary.observations == 3
    assert summary.total_quantity == 10
    assert summary.total_shortfall == 6
    assert summary.average_slippage_bps == 4
    assert set(group_by_venue_and_regime(observations)) == {
        ("v1", "normal"),
        ("v1", "transition"),
        ("v2", "normal"),
    }


def test_stress_scenario_increases_cost_when_multipliers_increase() -> None:
    observation = ExecutionObservation("v1", "news_shock", 1, 10, 8, 4)
    mild = stress_shortfall(observation, spread_multiplier=1.0, slippage_multiplier=1.0, impact_multiplier=1.0)
    severe = stress_shortfall(observation, spread_multiplier=2.0, slippage_multiplier=3.0, impact_multiplier=2.0)
    assert mild == 10
    assert severe == 70 / 3
