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

def test_duplicate_fill_replay_after_journal_restart_does_not_double_count(tmp_path):
    path = str(tmp_path / "restart-duplicate-fill.db")
    first = ExecutionRecoveryJournal(path)
    first.begin_submission(
        "restart-fill", client_order_id="restart-fill-client",
        requested_quantity=2.0,
    )
    first.mark_working("restart-fill", "venue-restart-fill")
    original = first.mark_fill(
        "restart-fill", 1.0, 100.0, fill_id="stable-deal-1", now=10.0,
    )

    restarted = ExecutionRecoveryJournal(path)
    replay = restarted.mark_fill(
        "restart-fill", 1.0, 100.0, fill_id="stable-deal-1", now=11.0,
    )

    assert replay.filled_quantity == original.filled_quantity == 1.0
    assert replay.filled_notional == original.filled_notional == 100.0
    assert len(restarted.fill_ledger("restart-fill")) == 1
    assert [row["fill_id"] for row in restarted.fill_ledger("restart-fill")] == [
        "stable-deal-1"
    ]


def test_broker_history_missing_a_previously_recorded_fill_fails_closed(tmp_path):
    journal = ExecutionRecoveryJournal(str(tmp_path / "broker-history-conflict.db"))
    journal.begin_submission("history-conflict", requested_quantity=3.0)
    journal.mark_working("history-conflict", "venue-history-conflict")
    journal.mark_fill(
        "history-conflict", 1.0, 100.0, fill_id="deal-already-recorded",
    )
    journal.mark_unknown("history-conflict", "broker connection lost")

    with pytest.raises(ValueError, match="conflicts with an already recorded fill"):
        journal.recover_unknown(
            "history-conflict",
            "venue-history-conflict",
            "FILLED",
            filled_quantity=3.0,
            filled_notional=302.0,
            fills=[
                {"fill_id": "broker-deal-a", "quantity": 1.0, "price": 101.0},
                {"fill_id": "broker-deal-b", "quantity": 2.0, "price": 100.5},
            ],
        )

    record = journal.get("history-conflict")
    assert record.state == "UNKNOWN"
    assert record.filled_quantity == 1.0
    assert [row["fill_id"] for row in journal.fill_ledger("history-conflict")] == [
        "deal-already-recorded"
    ]
    assert [row.order_id for row in journal.unresolved_records()] == [
        "history-conflict"
    ]


def test_concurrent_broker_recovery_never_adopts_the_same_order_twice(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    journal = ExecutionRecoveryJournal(str(tmp_path / "recovery-race.db"))
    journal.begin_submission(
        "recovery-race", client_order_id="recovery-race-client",
        requested_quantity=1.0,
    )
    journal.mark_unknown("recovery-race", "submit acknowledgement timed out")

    def attempt_recovery():
        try:
            return journal.recover_unknown(
                "recovery-race",
                "venue-recovery-race",
                "FILLED",
                filled_quantity=1.0,
                filled_notional=100.0,
                fills=[{
                    "fill_id": "race-deal-1",
                    "quantity": 1.0,
                    "price": 100.0,
                    "created_at": 12.0,
                }],
            )
        except (RuntimeError, ValueError) as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt_recovery(), range(2)))

    adopted = [result for result in results if not isinstance(result, Exception)]
    rejected = [result for result in results if isinstance(result, Exception)]
    assert len(adopted) == 1
    assert len(rejected) == 1
    assert "recovery race" in str(rejected[0]) or "only UNKNOWN" in str(rejected[0])

    final = journal.get("recovery-race")
    assert final.state == "FILLED"
    assert final.filled_quantity == 1.0
    assert final.filled_notional == 100.0
    assert len(journal.fill_ledger("recovery-race")) == 1
