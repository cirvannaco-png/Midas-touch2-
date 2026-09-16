from medis_touch.app.execution_calibration import record_from_outcome
from medis_touch.app.execution_models import ExecutionOutcome, OrderStatus, TCAResult
from medis_touch.app.execution_outcome import to_observation


def _outcome() -> ExecutionOutcome:
    return ExecutionOutcome(
        order_id="o1", decision_id="d1", symbol="XAUUSD", side="BUY",
        requested_quantity=10, filled_quantity=7, average_fill_price=100.1,
        status=OrderStatus.FILLED,
        tca=TCAResult("o1", 100, 100, 100.1, 10, slippage_cost=0.7, market_impact_cost=0.2, implementation_shortfall=1),
        execution_config_hash="cfg", execution_model_hash="model", reconciled=True,
    )


def test_execution_outcome_becomes_calibration_record_without_alpha_contamination():
    outcome = _outcome()
    observation = to_observation(outcome, regime="transition", policy="ADAPTIVE", venue="sim")
    record = record_from_outcome(observation)
    assert record.filled_ratio == 0.7
    assert record.regime == "transition"
    assert record.policy == "ADAPTIVE"
    assert record.implementation_shortfall == 1
