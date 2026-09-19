from tools.latency_budget import LatencyBudget, violations


def test_latency_budget_flags_slow_stage():
    result = violations({"decision_latency_ms": 300, "risk_latency_ms": 20}, LatencyBudget())
    assert result == {"decision_latency_ms": 300.0}
