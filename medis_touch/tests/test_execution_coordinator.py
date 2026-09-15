# ruff: noqa: I001

import pytest

from medis_touch.app.execution_coordinator import GovernedExecutionCoordinator
from medis_touch.app.execution_governance import ExecutionConfig
from medis_touch.app.execution_models import ExecutionOrder, ExecutionPolicy, OrderStatus
from medis_touch.app.execution_recovery import ExecutionRecoveryJournal
from medis_touch.app.institutional_control import ControlInputs
from medis_touch.app.pretrade_risk import PreTradeLimits
from medis_touch.app.venue import SimulatedVenue


def _limits() -> PreTradeLimits:
    return PreTradeLimits(1000, 10000, 5000, 100, 5)


def _config(venues: tuple[str, ...] = ("sim",)) -> ExecutionConfig:
    return ExecutionConfig("1", "TWAP", 10000, 5, 0.25, venues, "model-v1")


def _coordinator(config: ExecutionConfig, recovery: ExecutionRecoveryJournal | None = None) -> GovernedExecutionCoordinator:
    return GovernedExecutionCoordinator(SimulatedVenue("sim", 100.0, 100.2, 1000.0), config, approved_hash=config.config_hash, evidence_passed=True, recovery_journal=recovery)


def test_governed_execution_completes_full_chain() -> None:
    config = _config()
    coordinator = _coordinator(config)
    order = ExecutionOrder("chain-1", "decision-1", "XAUUSD", "BUY", 4.0, policy=ExecutionPolicy.TWAP, idempotency_key="chain-idem", metadata={"slices": 2})
    outcome, observation = coordinator.execute(order, reference_price=100.0, portfolio_notional=0, symbol_notional=0, daily_loss=0, spread_bps=2, limits=_limits(), regime="normal")
    assert outcome.status == OrderStatus.FILLED
    assert outcome.filled_quantity == 4.0
    assert outcome.execution_config_hash == config.config_hash
    assert outcome.reconciled
    assert observation.filled_quantity == 4.0


def test_control_plane_restriction_blocks_before_reservation() -> None:
    config = _config()
    coordinator = _coordinator(config)
    order = ExecutionOrder("restricted-1", "decision-1", "XAUUSD", "BUY", 1.0)
    with pytest.raises(PermissionError, match="institutional control state"):
        coordinator.execute(order, reference_price=100.0, portfolio_notional=0, symbol_notional=0, daily_loss=0, spread_bps=2, limits=_limits(), regime="normal", control_inputs=ControlInputs(True, True, True, True, True, model_drift=True))
    assert coordinator.oms.all_orders() == ()


def test_durable_parent_identity_is_bound_before_execution(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "recovery.db"))
    coordinator = _coordinator(_config(), journal)
    order = ExecutionOrder("durable-parent-1", "decision-1", "XAUUSD", "BUY", 1.0, idempotency_key="parent-client-1")
    outcome, _ = coordinator.execute(order, reference_price=100.0, portfolio_notional=0, symbol_notional=0, daily_loss=0, spread_bps=2, limits=_limits(), regime="normal")
    parent = journal.get(outcome.order_id)
    assert parent.client_order_id == "parent-client-1"
    assert parent.state == "RECOVERED"
    assert journal.child_records(outcome.order_id)


def test_governance_hash_mismatch_blocks_before_routing() -> None:
    config = _config()
    coordinator = _coordinator(config)
    order = ExecutionOrder("chain-2", "decision-2", "XAUUSD", "BUY", 1.0, metadata={"execution_config_hash": "wrong"})
    with pytest.raises(PermissionError):
        coordinator.execute(order, reference_price=100, portfolio_notional=0, symbol_notional=0, daily_loss=0, spread_bps=1, limits=_limits(), regime="normal")


def test_unauthorized_venue_blocks_before_oms_submission() -> None:
    config = _config(("other-venue",))
    coordinator = _coordinator(config)
    order = ExecutionOrder("chain-3", "decision-3", "XAUUSD", "BUY", 1.0)
    with pytest.raises(PermissionError):
        coordinator.execute(order, reference_price=100, portfolio_notional=0, symbol_notional=0, daily_loss=0, spread_bps=1, limits=_limits(), regime="normal")
    assert coordinator.oms.all_orders() == ()


def test_multiple_trades_share_portfolio_and_symbol_risk_capacity() -> None:
    coordinator = _coordinator(_config())
    orders = (
        ExecutionOrder("multi-1", "decision-1", "XAUUSD", "BUY", 4.0, idempotency_key="multi-idem-1"),
        ExecutionOrder("multi-2", "decision-2", "EURUSD", "SELL", 4.0, idempotency_key="multi-idem-2"),
    )
    results = coordinator.execute_many(orders, reference_prices={"XAUUSD": 100.0, "EURUSD": 100.0}, portfolio_notional=0, symbol_notionals={}, daily_loss=0, spread_bps={"XAUUSD": 2.0, "EURUSD": 2.0}, limits=_limits(), regime="normal")
    assert len(results) == 2
    assert all(outcome.status == OrderStatus.FILLED for outcome, _ in results)
    assert {outcome.order_id for outcome, _ in results} == {"multi-1", "multi-2"}
    assert len(coordinator.oms.all_orders()) == 2


def test_multiple_trades_are_preflighted_before_any_submission() -> None:
    limits = PreTradeLimits(1000, 1000, 5000, 100, 5)
    coordinator = _coordinator(_config())
    orders = (
        ExecutionOrder("batch-1", "decision-1", "XAUUSD", "BUY", 6.0, idempotency_key="batch-idem-1"),
        ExecutionOrder("batch-2", "decision-2", "EURUSD", "SELL", 6.0, idempotency_key="batch-idem-2"),
    )
    with pytest.raises(PermissionError, match="portfolio exposure limit"):
        coordinator.execute_many(orders, reference_prices={"XAUUSD": 100.0, "EURUSD": 100.0}, portfolio_notional=0, symbol_notionals={}, daily_loss=0, spread_bps={"XAUUSD": 2.0, "EURUSD": 2.0}, limits=limits, regime="normal")
    assert coordinator.oms.all_orders() == ()


def test_multiple_trades_enforce_existing_symbol_exposure() -> None:
    coordinator = _coordinator(_config())
    order = ExecutionOrder("symbol-1", "decision-1", "XAUUSD", "BUY", 4.0)
    with pytest.raises(PermissionError, match="symbol exposure limit"):
        coordinator.execute_many((order,), reference_prices={"XAUUSD": 100.0}, portfolio_notional=0, symbol_notionals={"XAUUSD": 4900.0}, daily_loss=0, spread_bps={"XAUUSD": 2.0}, limits=_limits(), regime="normal")
    assert coordinator.oms.all_orders() == ()
