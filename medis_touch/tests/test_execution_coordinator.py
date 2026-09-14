import pytest

from medis_touch.app.execution_coordinator import GovernedExecutionCoordinator
from medis_touch.app.execution_governance import ExecutionConfig
from medis_touch.app.execution_models import ExecutionOrder, ExecutionPolicy, OrderStatus
from medis_touch.app.pretrade_risk import PreTradeLimits
from medis_touch.app.venue import SimulatedVenue


def _limits() -> PreTradeLimits:
    return PreTradeLimits(1000, 10000, 5000, 100, 5)


def _config(venues: tuple[str, ...] = ("sim",)) -> ExecutionConfig:
    return ExecutionConfig("1", "TWAP", 10000, 5, 0.25, venues, "model-v1")


def _coordinator(config: ExecutionConfig) -> GovernedExecutionCoordinator:
    return GovernedExecutionCoordinator(
        SimulatedVenue("sim", 100.0, 100.2, 1000.0), config,
        approved_hash=config.config_hash, evidence_passed=True,
    )


def test_governed_execution_completes_full_chain() -> None:
    config = _config()
    coordinator = _coordinator(config)
    order = ExecutionOrder(
        "chain-1", "decision-1", "XAUUSD", "BUY", 4.0,
        policy=ExecutionPolicy.TWAP, idempotency_key="chain-idem", metadata={"slices": 2},
    )
    outcome, observation = coordinator.execute(
        order, reference_price=100.0, portfolio_notional=0, symbol_notional=0,
        daily_loss=0, spread_bps=2, limits=_limits(), regime="normal",
    )
    assert outcome.status == OrderStatus.FILLED
    assert outcome.filled_quantity == 4.0
    assert outcome.execution_config_hash == config.config_hash
    assert outcome.reconciled
    assert observation.filled_quantity == 4.0


def test_governance_hash_mismatch_blocks_before_routing() -> None:
    config = _config()
    coordinator = _coordinator(config)
    order = ExecutionOrder("chain-2", "decision-2", "XAUUSD", "BUY", 1.0,
                           metadata={"execution_config_hash": "wrong"})
    with pytest.raises(PermissionError):
        coordinator.execute(order, reference_price=100, portfolio_notional=0, symbol_notional=0,
                             daily_loss=0, spread_bps=1, limits=_limits(), regime="normal")


def test_unauthorized_venue_blocks_before_oms_submission() -> None:
    config = _config(("other-venue",))
    coordinator = _coordinator(config)
    order = ExecutionOrder("chain-3", "decision-3", "XAUUSD", "BUY", 1.0)
    with pytest.raises(PermissionError):
        coordinator.execute(order, reference_price=100, portfolio_notional=0, symbol_notional=0,
                            daily_loss=0, spread_bps=1, limits=_limits(), regime="normal")
    assert coordinator.oms.all_orders() == ()
