"""Durable execution recovery and EA/backend state-parity journal."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from math import isfinite
from time import time


@dataclass(frozen=True)
class RecoveryRecord:
    order_id: str
    state: str
    venue_order_id: str | None
    filled_quantity: float
    filled_notional: float
    last_error: str | None
    updated_at: float
    parent_order_id: str | None = None
    client_order_id: str | None = None
    requested_quantity: float | None = None
    fill_ledger_complete: bool = True


@dataclass(frozen=True)
class ExecutionStateEvent:
    source: str
    order_id: str
    decision_id: str
    setup_fingerprint: str
    status: str
    filled_quantity: float
    average_fill_price: float | None
    sequence: int
    created_at: float


class ExecutionRecoveryJournal:
    """Durable, idempotent execution/recovery state journal.

    Parent and child broker identities are persisted separately. A child is
    journaled before its broker boundary is crossed, so multiple child orders
    cannot overwrite one another's venue identity. Parent state is an
    aggregate compatibility record; authoritative broker recovery is child
    scoped. Client-order identity is durable even when venue acknowledgement
    does not return a venue order id.
    """

    def __init__(self, database: str = ":memory:") -> None:
        self.database = database
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS execution_recovery (
                order_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                venue_order_id TEXT,
                client_order_id TEXT,
                parent_order_id TEXT,
                filled_quantity REAL NOT NULL DEFAULT 0,
                filled_notional REAL NOT NULL DEFAULT 0,
                last_error TEXT,
                updated_at REAL NOT NULL,
                requested_quantity REAL,
                fill_ledger_complete INTEGER NOT NULL DEFAULT 1
            )""")
            # Upgrade databases created by the previous journal version.
            columns = {row[1] for row in db.execute("PRAGMA table_info(execution_recovery)")}
            for name, definition in (("client_order_id", "TEXT"), ("parent_order_id", "TEXT"), ("requested_quantity", "REAL")):
                if name not in columns:
                    db.execute(f"ALTER TABLE execution_recovery ADD COLUMN {name} {definition}")
            # Aggregate-only rows from old journals must not be mistaken for a
            # complete broker deal ledger. Fresh tables default to complete/empty.
            columns = {row[1] for row in db.execute("PRAGMA table_info(execution_recovery)")}
            if "fill_ledger_complete" not in columns:
                db.execute("ALTER TABLE execution_recovery ADD COLUMN fill_ledger_complete INTEGER NOT NULL DEFAULT 0")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_execution_recovery_client ON execution_recovery(client_order_id) WHERE client_order_id IS NOT NULL")
            db.execute("CREATE INDEX IF NOT EXISTS idx_execution_recovery_parent ON execution_recovery(parent_order_id)")
            db.execute("""CREATE TABLE IF NOT EXISTS execution_state_events (
                source TEXT NOT NULL, order_id TEXT NOT NULL, decision_id TEXT NOT NULL,
                setup_fingerprint TEXT NOT NULL, status TEXT NOT NULL,
                filled_quantity REAL NOT NULL, average_fill_price REAL,
                sequence INTEGER NOT NULL, created_at REAL NOT NULL,
                PRIMARY KEY(source, order_id, sequence)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS execution_recovery_fills (
                order_id TEXT NOT NULL, fill_id TEXT NOT NULL, quantity REAL NOT NULL,
                price REAL NOT NULL, created_at REAL NOT NULL,
                PRIMARY KEY(order_id, fill_id)
            )""")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10.0, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def begin_submission(
        self, order_id: str, now: float | None = None, *,
        parent_order_id: str | None = None, client_order_id: str | None = None,
        requested_quantity: float | None = None, reject_existing: bool = False,
    ) -> RecoveryRecord:
        if not order_id.strip():
            raise ValueError("order_id is required")
        if parent_order_id is not None and (not parent_order_id.strip() or parent_order_id == order_id):
            raise ValueError("parent_order_id must be non-empty and cannot equal order_id")
        if client_order_id is not None and not client_order_id.strip():
            raise ValueError("client_order_id must be non-empty when supplied")
        if requested_quantity is not None and (not isfinite(requested_quantity) or requested_quantity <= 0):
            raise ValueError("requested_quantity must be finite and positive")
        timestamp = time() if now is None else now
        if not isfinite(timestamp):
            raise ValueError("timestamp must be finite")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT order_id,state,venue_order_id,filled_quantity,filled_notional,last_error,updated_at,parent_order_id,client_order_id,requested_quantity "
                "FROM execution_recovery WHERE order_id=?", (order_id,),
            ).fetchone()
            if row is not None:
                if reject_existing:
                    db.rollback()
                    raise ValueError("durable order identity already exists; duplicate broker submission blocked")
                _, _, _, filled, _, _, _, parent_existing, client_existing, quantity_existing = row
                if parent_order_id is not None and parent_existing not in (None, parent_order_id):
                    db.rollback()
                    raise ValueError("order_id is already bound to a different parent_order_id")
                if client_order_id is not None and client_existing not in (None, client_order_id):
                    db.rollback()
                    raise ValueError("order_id is already bound to a different client_order_id")
                if requested_quantity is not None:
                    if quantity_existing is not None and abs(quantity_existing - requested_quantity) > 1e-9:
                        db.rollback()
                        raise ValueError("order_id is already bound to a different requested_quantity")
                    if filled > requested_quantity + 1e-9:
                        db.rollback()
                        raise ValueError("requested_quantity is below already-recorded fills")
                try:
                    db.execute(
                        "UPDATE execution_recovery SET parent_order_id=COALESCE(parent_order_id, ?), "
                        "client_order_id=COALESCE(client_order_id, ?), requested_quantity=COALESCE(requested_quantity, ?) "
                        "WHERE order_id=?",
                        (parent_order_id, client_order_id, requested_quantity, order_id),
                    )
                except sqlite3.IntegrityError as exc:
                    db.rollback()
                    raise ValueError("client_order_id is already bound to another durable order") from exc
                db.commit()
                return self.get(order_id)
            try:
                db.execute(
                    "INSERT INTO execution_recovery(order_id,state,client_order_id,parent_order_id,requested_quantity,updated_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (order_id, "SUBMITTING", client_order_id, parent_order_id, requested_quantity, timestamp),
                )
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise ValueError("client_order_id is already bound to another durable order") from exc
            db.commit()
        return RecoveryRecord(order_id, "SUBMITTING", None, 0.0, 0.0, None, timestamp, parent_order_id, client_order_id, requested_quantity)

    def child_records(self, parent_order_id: str) -> tuple[RecoveryRecord, ...]:
        with self._connect() as db:
            rows = db.execute("SELECT order_id,state,venue_order_id,filled_quantity,filled_notional,last_error,updated_at,parent_order_id,client_order_id,requested_quantity,fill_ledger_complete FROM execution_recovery WHERE parent_order_id=? ORDER BY order_id", (parent_order_id,)).fetchall()
        return tuple(RecoveryRecord(*row[:10], fill_ledger_complete=bool(row[10])) for row in rows)

    def unresolved_records(self) -> tuple[RecoveryRecord, ...]:
        """List orders whose durable states still require broker reconciliation."""
        states = (
            "SUBMITTING", "UNKNOWN", "WORKING", "PARTIALLY_FILLED",
            "CANCEL_PENDING", "RECOVERY_REQUIRED",
        )
        placeholders = ",".join("?" for _ in states)
        with self._connect() as db:
            rows = db.execute(
                "SELECT order_id,state,venue_order_id,filled_quantity,filled_notional,"
                "last_error,updated_at,parent_order_id,client_order_id,requested_quantity,fill_ledger_complete "
                "FROM execution_recovery WHERE state IN (?,?,?,?,?,?) "
                "OR (state='FILLED' AND fill_ledger_complete=0) ORDER BY updated_at,order_id",
                states,
            ).fetchall()
        return tuple(RecoveryRecord(*row[:10], fill_ledger_complete=bool(row[10])) for row in rows)

    def mark_unknown(self, order_id: str, error: str, now: float | None = None) -> RecoveryRecord:
        return self._update(order_id, "UNKNOWN", last_error=error, now=now)

    def mark_working(self, order_id: str, venue_order_id: str, now: float | None = None) -> RecoveryRecord:
        return self._update(order_id, "WORKING", venue_order_id=venue_order_id, now=now)

    def mark_fill(
        self, order_id: str, quantity: float, price: float, now: float | None = None, *,
        fill_id: str | None = None,
    ) -> RecoveryRecord:
        if not isfinite(quantity) or not isfinite(price) or quantity <= 0 or price <= 0:
            raise ValueError("fill quantity and price must be finite and positive")
        if fill_id is not None and not fill_id.strip():
            raise ValueError("fill_id must be non-empty when supplied")
        timestamp = time() if now is None else now
        if not isfinite(timestamp):
            raise ValueError("timestamp must be finite")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT state,filled_quantity,filled_notional,requested_quantity,fill_ledger_complete FROM execution_recovery WHERE order_id=?",
                (order_id,),
            ).fetchone()
            if row is None:
                db.rollback()
                raise KeyError(order_id)
            state_before, existing_quantity, existing_notional, requested_quantity, ledger_complete = row
            if fill_id is not None:
                prior_fill = db.execute(
                    "SELECT quantity,price FROM execution_recovery_fills WHERE order_id=? AND fill_id=?",
                    (order_id, fill_id),
                ).fetchone()
                if prior_fill is not None:
                    if abs(prior_fill[0] - quantity) > 1e-12 or abs(prior_fill[1] - price) > 1e-12:
                        db.rollback()
                        raise ValueError("fill_id was reused with different quantity or price")
                    db.commit()
                    return self.get(order_id)
            if state_before == "FILLED":
                db.rollback()
                raise ValueError("cannot add a new fill to an already FILLED order")
            if state_before in {"REJECTED", "EXPIRED", "RECOVERED"}:
                db.rollback()
                raise ValueError(f"cannot add a fill while order state is {state_before}")
            new_quantity = existing_quantity + quantity
            new_notional = existing_notional + quantity * price
            if requested_quantity is not None and new_quantity > requested_quantity + 1e-9:
                db.rollback()
                raise ValueError("cumulative fill quantity exceeds requested_quantity")
            if fill_id is not None:
                db.execute(
                    "INSERT INTO execution_recovery_fills(order_id,fill_id,quantity,price,created_at) VALUES(?,?,?,?,?)",
                    (order_id, fill_id, quantity, price, timestamp),
                )
            new_state = (
                "FILLED"
                if requested_quantity is not None and new_quantity >= requested_quantity - 1e-9
                else "PARTIALLY_FILLED"
            )
            db.execute(
                "UPDATE execution_recovery SET state=?,filled_quantity=?,filled_notional=?,fill_ledger_complete=?,last_error=NULL,updated_at=? WHERE order_id=?",
                (new_state, new_quantity, new_notional, int(bool(ledger_complete) and fill_id is not None), timestamp, order_id),
            )
            db.commit()
        return self.get(order_id)

    def mark_cancel_requested(self, order_id: str, now: float | None = None) -> RecoveryRecord:
        return self._update(order_id, "CANCEL_PENDING", now=now)

    def mark_cancelled(self, order_id: str, now: float | None = None) -> RecoveryRecord:
        return self._update(order_id, "CANCELLED", now=now)

    def mark_recovered(self, order_id: str, now: float | None = None) -> RecoveryRecord:
        return self._update(order_id, "RECOVERED", now=now)

    def recover_unknown(
        self, order_id: str, venue_order_id: str | None, broker_status: str, *,
        filled_quantity: float = 0.0, filled_notional: float = 0.0, now: float | None = None,
        fills: list[dict[str, object]] | tuple[dict[str, object], ...] | None = None,
    ) -> RecoveryRecord:
        """Resolve UNKNOWN using a broker query; never resubmit the exposure."""
        if not isfinite(filled_quantity) or not isfinite(filled_notional) or filled_quantity < 0 or filled_notional < 0:
            raise ValueError("recovered fill values must be finite and non-negative")
        if (filled_quantity == 0) != (filled_notional == 0):
            raise ValueError("recovered quantity and notional must both be zero or both be positive")
        state = broker_status.upper()
        if state not in {"WORKING", "PARTIALLY_FILLED", "FILLED", "CANCELLED", "EXPIRED", "REJECTED"}:
            raise ValueError("unsupported broker recovery status")
        if state in {"PARTIALLY_FILLED", "FILLED"} and filled_quantity <= 0:
            raise ValueError(f"{state} requires a positive recovered fill quantity")
        timestamp = time() if now is None else now
        if not isfinite(timestamp):
            raise ValueError("timestamp must be finite")
        record = self.get(order_id)
        if record.state != "UNKNOWN":
            raise ValueError("only UNKNOWN orders may enter durable recovery")
        if not venue_order_id and not record.client_order_id:
            raise ValueError("venue_order_id or durable client_order_id is required for recovery")
        if record.requested_quantity is not None:
            if filled_quantity > record.requested_quantity + 1e-9:
                raise ValueError("recovered fill quantity exceeds requested_quantity")
            if state == "FILLED" and filled_quantity < record.requested_quantity - 1e-9:
                raise ValueError("broker status FILLED conflicts with recovered quantity")
            if state == "PARTIALLY_FILLED" and filled_quantity >= record.requested_quantity - 1e-9:
                raise ValueError("broker status PARTIALLY_FILLED conflicts with requested_quantity")

        # An aggregate broker snapshot is not itself an authoritative deal ledger.
        # Stable deal IDs and exact aggregate reconciliation are required to promote
        # recovered fills to ledger-complete status.
        normalized_fills: list[tuple[str, float, float, float]] | None = None
        if fills is not None:
            by_id: dict[str, tuple[float, float, float]] = {}
            for item in fills:
                fill_id = str(item.get("fill_id", "")).strip()
                quantity = item.get("quantity")
                price = item.get("price")
                fill_time = item.get("created_at", timestamp)
                if not fill_id:
                    raise ValueError("authoritative recovery fills require a non-empty fill_id")
                if not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or not isfinite(float(quantity)) or float(quantity) <= 0:
                    raise ValueError("authoritative fill quantity must be finite and positive")
                if not isinstance(price, (int, float)) or isinstance(price, bool) or not isfinite(float(price)) or float(price) <= 0:
                    raise ValueError("authoritative fill price must be finite and positive")
                if not isinstance(fill_time, (int, float)) or isinstance(fill_time, bool) or not isfinite(float(fill_time)):
                    raise ValueError("authoritative fill timestamp must be finite")
                candidate = (float(quantity), float(price), float(fill_time))
                previous = by_id.get(fill_id)
                if previous is not None:
                    if abs(previous[0] - candidate[0]) > 1e-12 or abs(previous[1] - candidate[1]) > 1e-12:
                        raise ValueError("authoritative fill_id reused with conflicting quantity or price")
                    continue
                by_id[fill_id] = candidate
            normalized_fills = [(key, value[0], value[1], value[2]) for key, value in sorted(by_id.items())]
            ledger_quantity = sum(item[1] for item in normalized_fills)
            ledger_notional = sum(item[1] * item[2] for item in normalized_fills)
            if abs(ledger_quantity - filled_quantity) > max(1e-9, abs(filled_quantity) * 1e-9):
                raise ValueError("authoritative deal history quantity does not reconcile with broker aggregate")
            if abs(ledger_notional - filled_notional) > max(1e-7, abs(filled_notional) * 1e-9):
                raise ValueError("authoritative deal history notional does not reconcile with broker aggregate")

        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if normalized_fills is not None:
                # Previously observed unique fills must also exist unchanged in the
                # broker's authoritative history before the ledger can be replaced.
                existing = db.execute(
                    "SELECT fill_id,quantity,price FROM execution_recovery_fills WHERE order_id=?",
                    (order_id,),
                ).fetchall()
                authoritative = {fill_id: (quantity, price) for fill_id, quantity, price, _ in normalized_fills}
                for fill_id, quantity, price in existing:
                    observed = authoritative.get(fill_id)
                    if observed is None or abs(observed[0] - quantity) > 1e-12 or abs(observed[1] - price) > 1e-12:
                        db.rollback()
                        raise ValueError("authoritative broker history conflicts with an already recorded fill")
            else:
                existing = db.execute(
                    "SELECT COALESCE(SUM(quantity),0),COALESCE(SUM(quantity*price),0) FROM execution_recovery_fills WHERE order_id=?",
                    (order_id,),
                ).fetchone()
                history_matches = (
                    bool(record.fill_ledger_complete)
                    and abs(existing[0] - filled_quantity) <= max(1e-9, abs(filled_quantity) * 1e-9)
                    and abs(existing[1] - filled_notional) <= max(1e-7, abs(filled_notional) * 1e-9)
                )
            ledger_complete = normalized_fills is not None or (
                filled_quantity == 0 and filled_notional == 0
            ) or (fills is None and history_matches)
            cursor = db.execute(
                "UPDATE execution_recovery SET state=?,venue_order_id=COALESCE(?,venue_order_id),filled_quantity=?,filled_notional=?,fill_ledger_complete=?,last_error=NULL,updated_at=? "
                "WHERE order_id=? AND state='UNKNOWN'",
                (state, venue_order_id, filled_quantity, filled_notional, int(ledger_complete), timestamp, order_id),
            )
            if cursor.rowcount != 1:
                db.rollback()
                raise RuntimeError("recovery race: UNKNOWN state changed before recovery")
            if normalized_fills is not None:
                db.execute("DELETE FROM execution_recovery_fills WHERE order_id=?", (order_id,))
                db.executemany(
                    "INSERT INTO execution_recovery_fills(order_id,fill_id,quantity,price,created_at) VALUES(?,?,?,?,?)",
                    [(order_id, fill_id, quantity, price, created_at) for fill_id, quantity, price, created_at in normalized_fills],
                )
            db.commit()
        return self.get(order_id)

    def recover_unknown_by_client_order_id(self, client_order_id: str, broker_status: str, *, venue_order_id: str | None = None, filled_quantity: float = 0.0, filled_notional: float = 0.0, now: float | None = None, fills: list[dict[str, object]] | tuple[dict[str, object], ...] | None = None) -> RecoveryRecord:
        with self._connect() as db:
            row = db.execute("SELECT order_id FROM execution_recovery WHERE client_order_id=?", (client_order_id,)).fetchone()
        if row is None:
            raise KeyError(client_order_id)
        return self.recover_unknown(row[0], venue_order_id, broker_status, filled_quantity=filled_quantity, filled_notional=filled_notional, now=now, fills=fills)

    def fill_ledger(self, order_id: str) -> tuple[dict[str, object], ...]:
        """Return the durable unique fill ledger in deterministic event order."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT fill_id,quantity,price,created_at FROM execution_recovery_fills WHERE order_id=? ORDER BY created_at,fill_id",
                (order_id,),
            ).fetchall()
        return tuple(
            {"fill_id": row[0], "quantity": row[1], "price": row[2], "created_at": row[3]}
            for row in rows
        )

    def record_state_event(self, event: ExecutionStateEvent) -> None:
        if event.source not in {"EA", "BACKEND"}:
            raise ValueError("source must be EA or BACKEND")
        if not event.order_id.strip() or not event.decision_id.strip() or not event.setup_fingerprint.strip():
            raise ValueError("order_id, decision_id, and setup_fingerprint are required")
        if not event.status.strip():
            raise ValueError("status is required")
        if event.sequence < 0 or not isfinite(event.filled_quantity) or event.filled_quantity < 0 or not isfinite(event.created_at):
            raise ValueError("invalid state event quantity, sequence, or timestamp")
        if event.average_fill_price is not None and (not isfinite(event.average_fill_price) or event.average_fill_price <= 0):
            raise ValueError("average_fill_price must be finite and positive when supplied")
        if event.filled_quantity > 0 and event.average_fill_price is None:
            raise ValueError("positive filled quantity requires average_fill_price")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT decision_id,setup_fingerprint,status,filled_quantity,average_fill_price "
                "FROM execution_state_events WHERE source=? AND order_id=? AND sequence=?",
                (event.source, event.order_id, event.sequence),
            ).fetchone()
            values = (event.decision_id, event.setup_fingerprint, event.status, event.filled_quantity, event.average_fill_price)
            if existing is not None:
                if existing != values:
                    db.rollback()
                    raise ValueError("state sequence reused with different execution identity")
                db.commit()
                return
            previous = db.execute(
                "SELECT sequence,decision_id,setup_fingerprint,filled_quantity FROM execution_state_events "
                "WHERE source=? AND order_id=? ORDER BY sequence DESC LIMIT 1",
                (event.source, event.order_id),
            ).fetchone()
            if previous is not None:
                last_sequence, previous_decision_id, previous_fingerprint, last_filled = previous
                if event.sequence <= last_sequence:
                    db.rollback()
                    raise ValueError("state event sequence must increase monotonically")
                if event.decision_id != previous_decision_id or event.setup_fingerprint != previous_fingerprint:
                    db.rollback()
                    raise ValueError("decision identity/fingerprint cannot change within an order")
                if event.filled_quantity + 1e-9 < last_filled:
                    db.rollback()
                    raise ValueError("cumulative filled quantity cannot decrease")
            db.execute(
                "INSERT INTO execution_state_events VALUES (?,?,?,?,?,?,?,?,?)",
                (event.source, event.order_id, event.decision_id, event.setup_fingerprint, event.status, event.filled_quantity, event.average_fill_price, event.sequence, event.created_at),
            )
            db.commit()

    def parity(self, order_id: str) -> bool:
        with self._connect() as db:
            ea = db.execute("SELECT decision_id,setup_fingerprint,status,filled_quantity,average_fill_price,sequence FROM execution_state_events WHERE source='EA' AND order_id=? ORDER BY sequence", (order_id,)).fetchall()
            backend = db.execute("SELECT decision_id,setup_fingerprint,status,filled_quantity,average_fill_price,sequence FROM execution_state_events WHERE source='BACKEND' AND order_id=? ORDER BY sequence", (order_id,)).fetchall()
        return bool(ea and backend and ea == backend)

    def get(self, order_id: str) -> RecoveryRecord:
        with self._connect() as db:
            row = db.execute("SELECT order_id,state,venue_order_id,filled_quantity,filled_notional,last_error,updated_at,parent_order_id,client_order_id,requested_quantity,fill_ledger_complete FROM execution_recovery WHERE order_id=?", (order_id,)).fetchone()
        if row is None:
            raise KeyError(order_id)
        return RecoveryRecord(*row[:10], fill_ledger_complete=bool(row[10]))

    def _update(self, order_id: str, state: str, *, venue_order_id: str | None = None, last_error: str | None = None, now: float | None = None) -> RecoveryRecord:
        timestamp = time() if now is None else now
        if not isfinite(timestamp):
            raise ValueError("timestamp must be finite")
        transitions = {
            "SUBMITTING": {"SUBMITTING", "WORKING", "UNKNOWN", "CANCELLED", "REJECTED", "EXPIRED", "RECOVERED"},
            "UNKNOWN": {"UNKNOWN", "WORKING", "PARTIALLY_FILLED", "FILLED", "CANCEL_PENDING", "CANCELLED", "REJECTED", "EXPIRED"},
            "WORKING": {"WORKING", "UNKNOWN", "PARTIALLY_FILLED", "FILLED", "CANCEL_PENDING", "CANCELLED", "REJECTED", "EXPIRED", "RECOVERED"},
            "PARTIALLY_FILLED": {"PARTIALLY_FILLED", "UNKNOWN", "FILLED", "CANCEL_PENDING", "CANCELLED", "RECOVERED"},
            "CANCEL_PENDING": {"CANCEL_PENDING", "UNKNOWN", "PARTIALLY_FILLED", "FILLED", "CANCELLED"},
            "CANCELLED": {"CANCELLED"},
            # Reconciliation may discover that an apparently terminal fill
            # conflicts with broker truth; retain a fail-closed path to UNKNOWN.
            "FILLED": {"FILLED", "UNKNOWN"},
            "REJECTED": {"REJECTED"},
            "EXPIRED": {"EXPIRED"},
            "RECOVERED": {"RECOVERED"},
        }
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,venue_order_id FROM execution_recovery WHERE order_id=?", (order_id,)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError(order_id)
            current_state, existing_venue_id = row
            if state not in transitions.get(current_state, set()):
                db.rollback()
                raise ValueError(f"illegal execution recovery transition {current_state} -> {state}")
            if venue_order_id is not None and existing_venue_id not in (None, venue_order_id):
                db.rollback()
                raise ValueError("venue_order_id cannot change after it is bound")
            db.execute(
                "UPDATE execution_recovery SET state=?,venue_order_id=COALESCE(venue_order_id,?),last_error=?,updated_at=? WHERE order_id=?",
                (state, venue_order_id, last_error, timestamp, order_id),
            )
            db.commit()
        return self.get(order_id)
