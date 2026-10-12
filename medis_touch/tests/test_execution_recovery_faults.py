import pytest
from medis_touch.app.execution_coordinator import GovernedExecutionCoordinator
from medis_touch.app.execution_governance import ExecutionConfig
from medis_touch.app.execution_models import ExecutionOrder, ExecutionPolicy
from medis_touch.app.execution_recovery import ExecutionRecoveryJournal
from medis_touch.app.pretrade_risk import PreTradeLimits
from medis_touch.app.venue import SimulatedVenue


def _limits():
    return PreTradeLimits(1000, 10000, 5000, 100, 5)


def _config():
    return ExecutionConfig("1", ExecutionPolicy.TWAP, 10000, 5, 0.25, ("sim",), "model-v1")


def test_oms_submit_failure_closes_durable_parent_and_releases_reservation(tmp_path, monkeypatch):
    journal = ExecutionRecoveryJournal(str(tmp_path / "recovery.db"))
    config = _config()
    coordinator = GovernedExecutionCoordinator(
        SimulatedVenue("sim", 100.0, 100.2, 1000.0),
        config,
        approved_hash=config.config_hash,
        evidence_passed=True,
        recovery_journal=journal,
    )

    def fail_submit(_order):
        raise RuntimeError("OMS boundary failure")

    monkeypatch.setattr(coordinator.oms, "submit", fail_submit)
    order = ExecutionOrder("oms-fail", "decision-1", "XAUUSD", "BUY", 1.0, policy=ExecutionPolicy.TWAP, idempotency_key="oms-fail-client")
    with pytest.raises(RuntimeError, match="OMS boundary failure"):
        coordinator.execute(order, reference_price=100.0, portfolio_notional=0.0, symbol_notional=0.0, daily_loss=0.0, spread_bps=2.0, limits=_limits(), regime="normal")
    assert journal.get("oms-fail").state == "CANCELLED"
    assert coordinator._local_reservations.snapshot() == ()

def test_existing_durable_order_cannot_be_resubmitted_on_recovery_path(tmp_path):
    journal = ExecutionRecoveryJournal(str(tmp_path / "recovery.db"))
    journal.begin_submission("duplicate-order", client_order_id="stable-client-id", requested_quantity=2.0)
    journal.mark_unknown("duplicate-order", "submit acknowledgement timeout")
    with pytest.raises(ValueError, match="already exists"):
        journal.begin_submission(
            "duplicate-order", client_order_id="stable-client-id",
            requested_quantity=2.0, reject_existing=True,
        )
    assert journal.get("duplicate-order").state == "UNKNOWN"


def test_unresolved_durable_orders_are_visible_after_restart(tmp_path):
    path = str(tmp_path / "recovery.db")
    journal = ExecutionRecoveryJournal(path)
    journal.begin_submission("ambiguous-order", client_order_id="client-ambiguous", requested_quantity=1.0)
    journal.mark_unknown("ambiguous-order", "venue acknowledgement lost")
    restarted = ExecutionRecoveryJournal(path)
    unresolved = restarted.unresolved_records()
    assert [(record.order_id, record.state) for record in unresolved] == [
        ("ambiguous-order", "UNKNOWN")
    ]


def test_recovery_journal_rejects_non_finite_and_overfills(tmp_path):
    journal = ExecutionRecoveryJournal(str(tmp_path / "recovery.db"))
    journal.begin_submission("bounded-order", requested_quantity=1.0)
    journal.mark_working("bounded-order", "venue-bounded")
    with pytest.raises(ValueError, match="finite and positive"):
        journal.mark_fill("bounded-order", float("nan"), 100.0)
    with pytest.raises(ValueError, match="exceeds requested_quantity"):
        journal.mark_fill("bounded-order", 1.1, 100.0)
    assert journal.get("bounded-order").filled_quantity == 0.0
