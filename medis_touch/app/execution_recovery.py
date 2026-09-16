"""Durable execution recovery and EA/backend state-parity journal."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
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
                updated_at REAL NOT NULL
            )""")
            # Upgrade databases created by the previous journal version.
            columns = {row[1] for row in db.execute("PRAGMA table_info(execution_recovery)")}
            for name, definition in (("client_order_id", "TEXT"), ("parent_order_id", "TEXT")):
                if name not in columns:
                    db.execute(f"ALTER TABLE execution_recovery ADD COLUMN {name} {definition}")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_execution_recovery_client ON execution_recovery(client_order_id) WHERE client_order_id IS NOT NULL")
            db.execute("CREATE INDEX IF NOT EXISTS idx_execution_recovery_parent ON execution_recovery(parent_order_id)")
            db.execute("""CREATE TABLE IF NOT EXISTS execution_state_events (
                source TEXT NOT NULL, order_id TEXT NOT NULL, decision_id TEXT NOT NULL,
                setup_fingerprint TEXT NOT NULL, status TEXT NOT NULL,
                filled_quantity REAL NOT NULL, average_fill_price REAL,
                sequence INTEGER NOT NULL, created_at REAL NOT NULL,
                PRIMARY KEY(source, order_id, sequence)
            )""")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10.0, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def begin_submission(self, order_id: str, now: float | None = None, *, parent_order_id: str | None = None, client_order_id: str | None = None) -> RecoveryRecord:
        timestamp = time() if now is None else now
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT order_id,state,venue_order_id,filled_quantity,filled_notional,last_error,updated_at,parent_order_id,client_order_id FROM execution_recovery WHERE order_id=?", (order_id,)).fetchone()
            if row is not None:
                db.commit()
                return RecoveryRecord(*row)
            try:
                db.execute("INSERT INTO execution_recovery(order_id,state,client_order_id,parent_order_id,updated_at) VALUES(?,?,?,?,?)", (order_id, "SUBMITTING", client_order_id, parent_order_id, timestamp))
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise ValueError("client_order_id is already bound to another durable order") from exc
            db.commit()
        return RecoveryRecord(order_id, "SUBMITTING", None, 0.0, 0.0, None, timestamp, parent_order_id, client_order_id)

    def child_records(self, parent_order_id: str) -> tuple[RecoveryRecord, ...]:
        with self._connect() as db:
            rows = db.execute("SELECT order_id,state,venue_order_id,filled_quantity,filled_notional,last_error,updated_at,parent_order_id,client_order_id FROM execution_recovery WHERE parent_order_id=? ORDER BY order_id", (parent_order_id,)).fetchall()
        return tuple(RecoveryRecord(*row) for row in rows)

    def mark_unknown(self, order_id: str, error: str, now: float | None = None) -> RecoveryRecord:
        return self._update(order_id, "UNKNOWN", last_error=error, now=now)

    def mark_working(self, order_id: str, venue_order_id: str, now: float | None = None) -> RecoveryRecord:
        return self._update(order_id, "WORKING", venue_order_id=venue_order_id, now=now)

    def mark_fill(self, order_id: str, quantity: float, price: float, now: float | None = None) -> RecoveryRecord:
        if quantity <= 0 or price <= 0:
            raise ValueError("fill quantity and price must be positive")
        timestamp = time() if now is None else now
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,venue_order_id,client_order_id,parent_order_id,filled_quantity,filled_notional,last_error FROM execution_recovery WHERE order_id=?", (order_id,)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError(order_id)
            filled_quantity = row[4] + quantity
            filled_notional = row[5] + quantity * price
            state = "FILLED" if row[0] == "CANCELLED" else "PARTIALLY_FILLED"
            db.execute("UPDATE execution_recovery SET state=?,filled_quantity=?,filled_notional=?,updated_at=? WHERE order_id=?", (state, filled_quantity, filled_notional, timestamp, order_id))
            db.commit()
        return self.get(order_id)

    def mark_cancel_requested(self, order_id: str, now: float | None = None) -> RecoveryRecord:
        return self._update(order_id, "CANCEL_PENDING", now=now)

    def mark_cancelled(self, order_id: str, now: float | None = None) -> RecoveryRecord:
        return self._update(order_id, "CANCELLED", now=now)

    def mark_recovered(self, order_id: str, now: float | None = None) -> RecoveryRecord:
        return self._update(order_id, "RECOVERED", now=now)

    def recover_unknown(self, order_id: str, venue_order_id: str | None, broker_status: str, *, filled_quantity: float = 0.0, filled_notional: float = 0.0, now: float | None = None) -> RecoveryRecord:
        """Resolve UNKNOWN using the existing broker identity; never retry submit."""
        record = self.get(order_id)
        if record.state != "UNKNOWN":
            raise ValueError("only UNKNOWN orders may enter durable recovery")
        if not venue_order_id and not record.client_order_id:
            raise ValueError("venue_order_id or durable client_order_id is required for recovery")
        if filled_quantity < 0 or filled_notional < 0:
            raise ValueError("recovered fill values must be non-negative")
        state = broker_status.upper()
        if state not in {"WORKING", "PARTIALLY_FILLED", "FILLED", "CANCELLED", "EXPIRED", "REJECTED"}:
            raise ValueError("unsupported broker recovery status")
        timestamp = time() if now is None else now
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE execution_recovery SET state=?,venue_order_id=COALESCE(?,venue_order_id),filled_quantity=?,filled_notional=?,last_error=NULL,updated_at=? WHERE order_id=? AND state='UNKNOWN'", (state, venue_order_id, filled_quantity, filled_notional, timestamp, order_id))
            if db.total_changes != 1:
                db.rollback()
                raise RuntimeError("recovery race: UNKNOWN state changed before recovery")
            db.commit()
        return self.get(order_id)

    def recover_unknown_by_client_order_id(self, client_order_id: str, broker_status: str, *, venue_order_id: str | None = None, filled_quantity: float = 0.0, filled_notional: float = 0.0, now: float | None = None) -> RecoveryRecord:
        with self._connect() as db:
            row = db.execute("SELECT order_id FROM execution_recovery WHERE client_order_id=?", (client_order_id,)).fetchone()
        if row is None:
            raise KeyError(client_order_id)
        return self.recover_unknown(row[0], venue_order_id, broker_status, filled_quantity=filled_quantity, filled_notional=filled_notional, now=now)

    def record_state_event(self, event: ExecutionStateEvent) -> None:
        if event.source not in {"EA", "BACKEND"}:
            raise ValueError("source must be EA or BACKEND")
        if event.sequence < 0 or event.filled_quantity < 0:
            raise ValueError("invalid state event")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT decision_id,setup_fingerprint,status,filled_quantity,average_fill_price FROM execution_state_events WHERE source=? AND order_id=? AND sequence=?", (event.source, event.order_id, event.sequence)).fetchone()
            values = (event.decision_id, event.setup_fingerprint, event.status, event.filled_quantity, event.average_fill_price)
            if existing is not None:
                if existing != values:
                    db.rollback()
                    raise ValueError("state sequence reused with different execution identity")
                db.commit()
                return
            db.execute("INSERT INTO execution_state_events VALUES (?,?,?,?,?,?,?,?,?)", (event.source, event.order_id, event.decision_id, event.setup_fingerprint, event.status, event.filled_quantity, event.average_fill_price, event.sequence, event.created_at))
            db.commit()

    def parity(self, order_id: str) -> bool:
        with self._connect() as db:
            ea = db.execute("SELECT decision_id,setup_fingerprint,status,filled_quantity,average_fill_price,sequence FROM execution_state_events WHERE source='EA' AND order_id=? ORDER BY sequence", (order_id,)).fetchall()
            backend = db.execute("SELECT decision_id,setup_fingerprint,status,filled_quantity,average_fill_price,sequence FROM execution_state_events WHERE source='BACKEND' AND order_id=? ORDER BY sequence", (order_id,)).fetchall()
        return ea == backend

    def get(self, order_id: str) -> RecoveryRecord:
        with self._connect() as db:
            row = db.execute("SELECT order_id,state,venue_order_id,filled_quantity,filled_notional,last_error,updated_at,parent_order_id,client_order_id FROM execution_recovery WHERE order_id=?", (order_id,)).fetchone()
        if row is None:
            raise KeyError(order_id)
        return RecoveryRecord(*row)

    def _update(self, order_id: str, state: str, *, venue_order_id: str | None = None, last_error: str | None = None, now: float | None = None) -> RecoveryRecord:
        timestamp = time() if now is None else now
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM execution_recovery WHERE order_id=?", (order_id,)).fetchone() is None:
                db.rollback()
                raise KeyError(order_id)
            if venue_order_id is None:
                db.execute("UPDATE execution_recovery SET state=?,last_error=?,updated_at=? WHERE order_id=?", (state, last_error, timestamp, order_id))
            else:
                db.execute("UPDATE execution_recovery SET state=?,venue_order_id=?,last_error=?,updated_at=? WHERE order_id=?", (state, venue_order_id, last_error, timestamp, order_id))
            db.commit()
        return self.get(order_id)
