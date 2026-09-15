"""Durable broker ambiguity, cancellation, late-fill, and child recovery tests."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from medis_touch.app.execution_recovery import ExecutionRecoveryJournal


def test_unknown_survives_restart_and_resolves_without_new_submission(tmp_path) -> None:
    path = str(tmp_path / "recovery.db")
    first = ExecutionRecoveryJournal(path)
    first.begin_submission("o-1")
    first.mark_unknown("o-1", "timeout after submit")
    restarted = ExecutionRecoveryJournal(path)
    record = restarted.get("o-1")
    assert record.state == "UNKNOWN"
    assert record.last_error == "timeout after submit"
    restarted.mark_working("o-1", "broker-77")
    assert restarted.get("o-1").venue_order_id == "broker-77"


def test_partial_fill_cancel_then_late_fill_preserves_quantity(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "recovery.db"))
    journal.begin_submission("o-2")
    journal.mark_working("o-2", "broker-88")
    journal.mark_fill("o-2", 3.0, 100.0)
    journal.mark_cancel_requested("o-2")
    journal.mark_cancelled("o-2")
    final = journal.mark_fill("o-2", 2.0, 101.0)
    assert final.state == "FILLED"
    assert final.filled_quantity == 5.0
    assert final.filled_notional == 502.0


def test_concurrent_recovery_readers_never_lose_fills(tmp_path) -> None:
    path = str(tmp_path / "recovery.db")
    journal = ExecutionRecoveryJournal(path)
    journal.begin_submission("o-3")
    journal.mark_working("o-3", "broker-99")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: journal.mark_fill("o-3", 1.0, 100.0), range(4)))
    assert journal.get("o-3").filled_quantity == 4.0


def test_multiple_children_keep_independent_broker_identities(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "recovery.db"))
    journal.begin_submission("parent", client_order_id="parent-client")
    journal.begin_submission("parent:child:0", parent_order_id="parent", client_order_id="child-client-0")
    journal.begin_submission("parent:child:1", parent_order_id="parent", client_order_id="child-client-1")
    journal.mark_working("parent:child:0", "venue-0")
    journal.mark_working("parent:child:1", "venue-1")
    children = journal.child_records("parent")
    assert {child.venue_order_id for child in children} == {"venue-0", "venue-1"}
    assert {child.client_order_id for child in children} == {"child-client-0", "child-client-1"}


def test_unknown_recovers_by_client_order_id_without_venue_ack(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "recovery.db"))
    journal.begin_submission("child-ambiguous", parent_order_id="parent", client_order_id="client-ambiguous")
    journal.mark_unknown("child-ambiguous", "submit timeout: acknowledgement lost")
    recovered = journal.recover_unknown_by_client_order_id("client-ambiguous", "FILLED", filled_quantity=2.0, filled_notional=202.0)
    assert recovered.state == "FILLED"
    assert recovered.venue_order_id is None
    assert recovered.filled_quantity == 2.0
    with pytest.raises(ValueError):
        journal.recover_unknown_by_client_order_id("client-ambiguous", "FILLED", filled_quantity=2.0, filled_notional=202.0)
