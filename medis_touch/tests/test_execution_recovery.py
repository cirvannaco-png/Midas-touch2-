"""Durable broker ambiguity, cancellation, late-fill, and child recovery tests."""

# ruff: noqa: I001

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
    journal.begin_submission("o-2", requested_quantity=5.0)
    journal.mark_working("o-2", "broker-88")
    journal.mark_fill("o-2", 3.0, 100.0, fill_id="fill-1")
    journal.mark_cancel_requested("o-2")
    journal.mark_cancelled("o-2")
    final = journal.mark_fill("o-2", 2.0, 101.0, fill_id="fill-2")
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

def test_replayed_fill_id_is_idempotent_and_conflicting_reuse_is_rejected(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "recovery.db"))
    journal.begin_submission("o-fill", requested_quantity=3.0)
    journal.mark_working("o-fill", "venue-fill")
    first = journal.mark_fill("o-fill", 1.0, 100.0, fill_id="broker-fill-1")
    replay = journal.mark_fill("o-fill", 1.0, 100.0, fill_id="broker-fill-1")
    assert replay.filled_quantity == first.filled_quantity == 1.0
    assert replay.filled_notional == first.filled_notional == 100.0
    with pytest.raises(ValueError, match="fill_id was reused"):
        journal.mark_fill("o-fill", 2.0, 100.0, fill_id="broker-fill-1")
    assert journal.get("o-fill").filled_quantity == 1.0

def test_late_fill_after_cancel_remains_partial_below_requested_quantity(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "recovery.db"))
    journal.begin_submission("o-late", requested_quantity=5.0)
    journal.mark_working("o-late", "venue-late")
    journal.mark_fill("o-late", 2.0, 100.0, fill_id="late-fill-1")
    journal.mark_cancel_requested("o-late")
    journal.mark_cancelled("o-late")
    record = journal.mark_fill("o-late", 1.0, 101.0, fill_id="late-fill-2")
    assert record.state == "PARTIALLY_FILLED"
    assert record.filled_quantity == 3.0
    assert record.filled_notional == 301.0

def test_recovery_rejects_identity_and_requested_quantity_rebinding(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "recovery.db"))
    journal.begin_submission("o-identity", parent_order_id="parent-1", client_order_id="client-1", requested_quantity=2.0)
    with pytest.raises(ValueError, match="different client_order_id"):
        journal.begin_submission("o-identity", client_order_id="client-2")
    with pytest.raises(ValueError, match="different requested_quantity"):
        journal.begin_submission("o-identity", requested_quantity=3.0)

def test_empty_ea_backend_parity_is_not_treated_as_success(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "recovery.db"))
    assert journal.parity("never-seen") is False




def test_aggregate_only_recovery_is_not_claimed_as_authoritative_deal_history(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "aggregate-only.db"))
    journal.begin_submission("aggregate-only", requested_quantity=2.0, client_order_id="client-aggregate")
    journal.mark_unknown("aggregate-only", "acknowledgement lost")
    recovered = journal.recover_unknown(
        "aggregate-only", None, "FILLED",
        filled_quantity=2.0, filled_notional=202.0,
    )
    assert recovered.state == "FILLED"
    assert recovered.filled_quantity == 2.0
    assert recovered.fill_ledger_complete is False
    assert journal.fill_ledger("aggregate-only") == ()
    # Filled aggregate-only recoveries must keep the recovery gate closed until
    # their authoritative broker deal ledger has been reconstructed.
    assert [row.order_id for row in journal.unresolved_records()] == ["aggregate-only"]


def test_recovery_rebuilds_authoritative_fill_ledger_and_replay_is_idempotent(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "authoritative-ledger.db"))
    journal.begin_submission("ledger-order", requested_quantity=3.0, client_order_id="ledger-client")
    journal.mark_unknown("ledger-order", "acknowledgement lost")
    fills = [
        {"fill_id": "deal-1", "quantity": 1.0, "price": 100.0, "created_at": 10.0},
        {"fill_id": "deal-2", "quantity": 2.0, "price": 101.0, "created_at": 11.0},
    ]
    recovered = journal.recover_unknown(
        "ledger-order", "venue-order", "FILLED",
        filled_quantity=3.0, filled_notional=302.0, now=12.0, fills=fills,
    )
    assert recovered.fill_ledger_complete is True
    assert recovered.filled_quantity == 3.0
    assert recovered.filled_notional == 302.0
    assert [row["fill_id"] for row in journal.fill_ledger("ledger-order")] == ["deal-1", "deal-2"]

    replay = journal.mark_fill("ledger-order", 1.0, 100.0, fill_id="deal-1")
    assert replay.filled_quantity == 3.0
    assert replay.filled_notional == 302.0
    assert len(journal.fill_ledger("ledger-order")) == 2


def test_recovery_rejects_fill_ledger_that_does_not_match_broker_aggregate(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "bad-ledger.db"))
    journal.begin_submission("bad-ledger", requested_quantity=2.0)
    journal.mark_unknown("bad-ledger", "history query pending")
    with pytest.raises(ValueError, match="quantity does not reconcile"):
        journal.recover_unknown(
            "bad-ledger", "venue-bad", "FILLED",
            filled_quantity=2.0, filled_notional=201.0,
            fills=[{"fill_id": "deal-1", "quantity": 1.0, "price": 100.0},
                   {"fill_id": "deal-2", "quantity": 0.5, "price": 101.0}],
        )
    assert journal.get("bad-ledger").state == "UNKNOWN"
    assert journal.get("bad-ledger").filled_quantity == 0.0
    assert journal.fill_ledger("bad-ledger") == ()


def test_partial_recovery_can_continue_without_double_counting_recovered_fills(tmp_path) -> None:
    journal = ExecutionRecoveryJournal(str(tmp_path / "partial-recovered.db"))
    journal.begin_submission("part-ledger", requested_quantity=3.0)
    journal.mark_unknown("part-ledger", "connection lost after partial fill")
    recovered = journal.recover_unknown(
        "part-ledger", "venue-part", "PARTIALLY_FILLED",
        filled_quantity=1.5, filled_notional=150.0,
        fills=[{"fill_id": "deal-part-1", "quantity": 1.5, "price": 100.0}],
    )
    assert recovered.fill_ledger_complete is True
    assert recovered.state == "PARTIALLY_FILLED"
    next_state = journal.mark_fill("part-ledger", 1.5, 101.0, fill_id="deal-part-2")
    assert next_state.state == "FILLED"
    assert next_state.filled_quantity == 3.0
    assert next_state.filled_notional == 301.5
    assert len(journal.fill_ledger("part-ledger")) == 2
