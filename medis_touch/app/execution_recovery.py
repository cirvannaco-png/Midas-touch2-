"""Durable execution recovery journal for ambiguous broker boundaries."""

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


class ExecutionRecoveryJournal:
    """Durable, idempotent execution state journal.

    The journal is deliberately independent of broker adapters. A submission
    that may have reached a broker is persisted as UNKNOWN before recovery
    decisions are made, preventing an ambiguous call from being retried as a
    fresh order after a process restart.
    """

    def __init__(self, database: str = ":memory:") -> None:
        self.database = database
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS execution_recovery (
                order_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                venue_order_id TEXT,
                filled_quantity REAL NOT NULL DEFAULT 0,
                filled_notional REAL NOT NULL DEFAULT 0,
                last_error TEXT,
                updated_at REAL NOT NULL
            )""")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database, timeout=10.0, isolation_level=None)

    def begin_submission(self, order_id: str, now: float | None = None) -> RecoveryRecord:
        timestamp = time() if now is None else now
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT order_id,state,venue_order_id,filled_quantity,filled_notional,last_error,updated_at FROM execution_recovery WHERE order_id=?", (order_id,)).fetchone()
            if row is not None:
                db.commit()
                return RecoveryRecord(*row)
            db.execute("INSERT INTO execution_recovery(order_id,state,updated_at) VALUES(?,?,?)", (order_id, "SUBMITTING", timestamp))
            db.commit()
        return RecoveryRecord(order_id, "SUBMITTING", None, 0.0, 0.0, None, timestamp)

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
            row = db.execute("SELECT state,venue_order_id,filled_quantity,filled_notional,last_error FROM execution_recovery WHERE order_id=?", (order_id,)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError(order_id)
            filled_quantity = row[2] + quantity
            filled_notional = row[3] + quantity * price
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

    def get(self, order_id: str) -> RecoveryRecord:
        with self._connect() as db:
            row = db.execute("SELECT order_id,state,venue_order_id,filled_quantity,filled_notional,last_error,updated_at FROM execution_recovery WHERE order_id=?", (order_id,)).fetchone()
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
