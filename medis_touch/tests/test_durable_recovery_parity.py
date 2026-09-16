"""Durable recovery and EA/backend parity contract tests."""

from medis_touch.app.execution_recovery import ExecutionRecoveryJournal, ExecutionStateEvent


def test_unknown_recovery_uses_existing_broker_identity(tmp_path) -> None:
    path = str(tmp_path / "recovery.db")
    journal = ExecutionRecoveryJournal(path)
    journal.begin_submission("order-1")
    journal.mark_unknown("order-1", "ack timeout")
    restarted = ExecutionRecoveryJournal(path)
    recovered = restarted.recover_unknown("order-1", "venue-1", "PARTIALLY_FILLED", filled_quantity=2, filled_notional=201)
    assert recovered.state == "PARTIALLY_FILLED"
    assert recovered.venue_order_id == "venue-1"
    assert recovered.filled_quantity == 2


def test_unknown_recovery_cannot_be_replayed(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "recovery.db"))
    journal.begin_submission("order-2")
    journal.mark_unknown("order-2", "timeout")
    journal.recover_unknown("order-2", "venue-2", "WORKING")
    try:
        journal.recover_unknown("order-2", "venue-2", "FILLED", filled_quantity=1, filled_notional=100)
    except ValueError as exc:
        assert "UNKNOWN" in str(exc)
    else:
        raise AssertionError("recovery was replayed after leaving UNKNOWN")


def test_partial_cancel_late_fill_is_durable(tmp_path) -> None:
    path = str(tmp_path / "recovery.db")
    journal = ExecutionRecoveryJournal(path)
    journal.begin_submission("order-3")
    journal.mark_working("order-3", "venue-3")
    journal.mark_fill("order-3", 3, 100)
    journal.mark_cancel_requested("order-3")
    journal.mark_cancelled("order-3")
    journal.mark_fill("order-3", 2, 101)
    restarted = ExecutionRecoveryJournal(path)
    record = restarted.get("order-3")
    assert record.state == "FILLED"
    assert record.filled_quantity == 5
    assert record.filled_notional == 502


def test_ea_backend_state_sequences_are_identical(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "parity.db"))
    states = ((0, "VALIDATED", 0.0, None), (1, "WORKING", 0.0, None), (2, "PARTIALLY_FILLED", 2.0, 100.5), (3, "FILLED", 5.0, 100.8))
    for sequence, status, quantity, price in states:
        for source in ("EA", "BACKEND"):
            journal.record_state_event(ExecutionStateEvent(source, "order-4", "decision-4", "setup-sha256", status, quantity, price, sequence, float(sequence)))
    assert journal.parity("order-4")


def test_parity_rejects_identity_or_state_divergence(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "parity.db"))
    journal.record_state_event(ExecutionStateEvent("EA", "order-5", "decision-5", "setup-a", "FILLED", 1, 100, 0, 0))
    journal.record_state_event(ExecutionStateEvent("BACKEND", "order-5", "decision-5", "setup-b", "FILLED", 1, 100, 0, 0))
    assert not journal.parity("order-5")
