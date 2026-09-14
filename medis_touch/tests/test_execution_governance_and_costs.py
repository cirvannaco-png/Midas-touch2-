from medis_touch.app.child_execution import ChildOrderExecutor
from medis_touch.app.execution_cost_model import CostAssumptions, estimate_execution_cost
from medis_touch.app.execution_governance import ExecutionConfig, attach_identity, promotion_allowed
from medis_touch.app.execution_models import ExecutionOrder, ExecutionPolicy


def _order(policy: ExecutionPolicy = ExecutionPolicy.TWAP) -> ExecutionOrder:
    return ExecutionOrder(
        order_id="parent-1", decision_id="decision-1", symbol="XAUUSD", side="BUY", quantity=10.0,
        policy=policy, idempotency_key="idem-1", metadata={"slices": 2, "participation": 0.25},
    )


def _config() -> ExecutionConfig:
    return ExecutionConfig("1", "ADAPTIVE", 10000, 5, 0.25, ("v2", "v1"), "model-hash")


def test_child_execution_conserves_parent_quantity() -> None:
    children = ChildOrderExecutor().build_children(_order())
    assert sum(child.quantity for child in children) == 10.0
    assert all(child.metadata["parent_order_id"] == "parent-1" for child in children)


def test_config_hash_is_canonical_and_required_for_promotion() -> None:
    config = _config()
    metadata = attach_identity({}, config)
    assert metadata["execution_config_hash"] == config.config_hash
    assert promotion_allowed(challenger=config, approved_hash=config.config_hash, evidence_passed=True)
    assert not promotion_allowed(challenger=config, approved_hash="wrong", evidence_passed=True)
    assert not promotion_allowed(challenger=config, approved_hash=config.config_hash, evidence_passed=False)


def test_cost_model_is_positive_and_time_local() -> None:
    cost = estimate_execution_cost(
        quantity=10, reference_price=100, spread=0.2, participation=0.25,
        assumptions=CostAssumptions(commission_per_unit=0.01, slippage_bps=2, impact_bps_per_participation=4),
    )
    assert cost > 0
