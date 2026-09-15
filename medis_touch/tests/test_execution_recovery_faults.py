import pytest

from medis_touch.app.execution_coordinator import GovernedExecutionCoordinator
from medis_touch.app.execution_governance import ExecutionConfig
from medis_touch.app.execution_models import ExecutionOrder, ExecutionPolicy
from medis_touch.app.execution_recovery import ExecutionRecoveryJournal
from medis_touch.app.pretrade_risk import PreTradeLimits
from medis_touch.app.venue import SimulatedVenue


class FailingOmsVenue(SimulatedVenue):
    def submit(self, order):
        raise RuntimeError("OMS boundary failure")


def _limits():
    return PreTradeLimits(1000, 10000, 5000, 100, 5)


def _config():
    return ExecutionConfig("1", ExecutionPolicy.TWAP, 10000, 5, 0.25, ("sim",), "model-v1")


def test_oms_submit_failure_closes_durable_parent_and_releases_reservation(tmp_path):
    journal = ExecutionRecoveryJournal(str(tmp_path / "recovery.db"))
    config = _config()
    coordinator = GovernedExecutionCoordinator(
        FailingOmsVenue("sim", 100.0, 100.2, 1000.0),
        config,
        approved_hash=config.config_hash,
        evidence_passed=True,
        recovery_journal=journal,
    )
    order = ExecutionOrder("oms-fail", "decision-1", "XAUUSD", "BUY", 1.0, policy=ExecutionPolicy.TWAP, idempotency_key="oms-fail-client")
    with pytest.raises(RuntimeError, match="OMS boundary failure"):
        coordinator.execute(order, reference_price=100.0, portfolio_notional=0.0, symbol_notional=0.0, daily_loss=0.0, spread_bps=2.0, limits=_limits(), regime="normal")
    assert journal.get("oms-fail").state == "CANCELLED"
    assert coordinator._local_reservations.reserved_portfolio_notional == 0.0
