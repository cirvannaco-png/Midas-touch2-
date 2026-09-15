"""Fail-closed pre-trade risk gates and persistent exposure admission."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from math import isfinite
from threading import RLock
from time import time

from .execution_models import ExecutionOrder, RiskDecision


@dataclass(frozen=True)
class PreTradeLimits:
    max_order_notional: float
    max_portfolio_notional: float
    max_symbol_notional: float
    max_daily_loss: float
    max_spread_bps: float


@dataclass(frozen=True)
class RiskReservation:
    reservation_id: str
    portfolio_notional: float
    symbol_notionals: tuple[tuple[str, float], ...]
    created_at: float
    expires_at: float | None


class RiskReservationBook:
    """Process-local atomic exposure reservation ledger.

    Multi-process production deployments must use shared transactional
    persistence such as :class:`PersistentPortfolioAdmission`.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._reservations: dict[str, RiskReservation] = {}

    def reserve(self, reservation_id: str, *, portfolio_notional: float, symbol_notionals: dict[str, float], requested_portfolio_notional: float, requested_symbol_notionals: dict[str, float], limits: PreTradeLimits, ttl_seconds: float | None = 30.0) -> RiskReservation:
        if not reservation_id:
            raise ValueError("reservation_id is required")
        if ttl_seconds is not None and (not isfinite(ttl_seconds) or ttl_seconds <= 0):
            raise ValueError("ttl_seconds must be positive and finite")
        with self._lock:
            self._expire_locked(time())
            requested_symbols = tuple(sorted(requested_symbol_notionals.items()))
            existing = self._reservations.get(reservation_id)
            if existing is not None:
                if existing.portfolio_notional != requested_portfolio_notional or existing.symbol_notionals != requested_symbols:
                    raise ValueError("reservation_id already exists with different exposure identity")
                return existing
            values = (portfolio_notional, requested_portfolio_notional, *symbol_notionals.values(), *requested_symbol_notionals.values())
            if not all(isfinite(value) and value >= 0 for value in values):
                raise ValueError("risk reservation inputs must be finite and non-negative")
            reserved_portfolio = sum(item.portfolio_notional for item in self._reservations.values())
            if portfolio_notional + reserved_portfolio + requested_portfolio_notional > limits.max_portfolio_notional:
                raise PermissionError("portfolio exposure reservation limit")
            merged = dict(symbol_notionals)
            for item in self._reservations.values():
                for symbol, notional in item.symbol_notionals:
                    merged[symbol] = merged.get(symbol, 0.0) + notional
            for symbol, notional in requested_symbol_notionals.items():
                if merged.get(symbol, 0.0) + notional > limits.max_symbol_notional:
                    raise PermissionError(f"symbol exposure reservation limit: {symbol}")
            now = time()
            reservation = RiskReservation(reservation_id, requested_portfolio_notional, requested_symbols, now, None if ttl_seconds is None else now + ttl_seconds)
            self._reservations[reservation_id] = reservation
            return reservation

    def consume(self, reservation_id: str) -> None:
        self.release(reservation_id)

    def release(self, reservation_id: str) -> None:
        with self._lock:
            self._reservations.pop(reservation_id, None)

    def expire(self, now: float | None = None) -> tuple[str, ...]:
        with self._lock:
            return self._expire_locked(time() if now is None else now)

    def _expire_locked(self, now: float) -> tuple[str, ...]:
        expired = tuple(rid for rid, reservation in self._reservations.items() if reservation.expires_at is not None and reservation.expires_at <= now)
        for rid in expired:
            self._reservations.pop(rid, None)
        return expired

    def snapshot(self) -> tuple[RiskReservation, ...]:
        with self._lock:
            self._expire_locked(time())
            return tuple(self._reservations.values())


class PersistentPortfolioAdmission:
    """SQLite-backed transactional reservation and committed-exposure ledger.

    Each admission operation runs in ``BEGIN IMMEDIATE`` and therefore
    serializes competing writers in the same database. Reservations and
    committed exposure are scoped by ``scope_id`` (normally an account or
    portfolio). The transaction is the risk boundary: capacity is checked and
    the reservation is inserted atomically, eliminating check-then-submit
    oversubscription across processes sharing the database.
    """

    def __init__(self, database: str = ":memory:") -> None:
        self.database = database
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10.0, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS portfolio_admission_reservations (
                    reservation_id TEXT PRIMARY KEY,
                    scope_id TEXT NOT NULL,
                    portfolio_notional REAL NOT NULL,
                    symbol_notionals TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL
                );
                CREATE INDEX IF NOT EXISTS idx_admission_res_scope
                    ON portfolio_admission_reservations(scope_id);
                CREATE TABLE IF NOT EXISTS portfolio_admission_exposure (
                    scope_id TEXT PRIMARY KEY,
                    portfolio_notional REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS portfolio_admission_symbol_exposure (
                    scope_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    notional REAL NOT NULL,
                    PRIMARY KEY(scope_id, symbol)
                );
                """
            )

    @staticmethod
    def _validate(values: tuple[float, ...]) -> None:
        if not all(isfinite(value) and value >= 0 for value in values):
            raise ValueError("portfolio admission inputs must be finite and non-negative")

    def reserve(self, reservation_id: str, *, scope_id: str, requested_portfolio_notional: float, requested_symbol_notionals: dict[str, float], limits: PreTradeLimits, ttl_seconds: float | None = 30.0, now: float | None = None) -> RiskReservation:
        if not reservation_id or not scope_id:
            raise ValueError("reservation_id and scope_id are required")
        if ttl_seconds is not None and (not isfinite(ttl_seconds) or ttl_seconds <= 0):
            raise ValueError("ttl_seconds must be positive and finite")
        if any(not symbol for symbol in requested_symbol_notionals):
            raise ValueError("symbol is required")
        self._validate((requested_portfolio_notional, *requested_symbol_notionals.values()))
        created = time() if now is None else now
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM portfolio_admission_reservations WHERE expires_at IS NOT NULL AND expires_at <= ?", (created,))
            existing = db.execute("SELECT scope_id, portfolio_notional, symbol_notionals, created_at, expires_at FROM portfolio_admission_reservations WHERE reservation_id = ?", (reservation_id,)).fetchone()
            symbols_json = json.dumps(sorted(requested_symbol_notionals.items()), separators=(",", ":"))
            if existing:
                if existing[0] != scope_id or existing[1] != requested_portfolio_notional or existing[2] != symbols_json:
                    raise ValueError("reservation_id already exists with different exposure identity")
                return RiskReservation(reservation_id, existing[1], tuple(json.loads(existing[2])), existing[3], existing[4])
            committed_portfolio = db.execute("SELECT portfolio_notional FROM portfolio_admission_exposure WHERE scope_id = ?", (scope_id,)).fetchone()
            committed_portfolio_value = committed_portfolio[0] if committed_portfolio else 0.0
            reserved_portfolio = db.execute("SELECT COALESCE(SUM(portfolio_notional), 0) FROM portfolio_admission_reservations WHERE scope_id = ?", (scope_id,)).fetchone()[0]
            if committed_portfolio_value + reserved_portfolio + requested_portfolio_notional > limits.max_portfolio_notional:
                raise PermissionError("portfolio exposure reservation limit")
            for symbol, requested in requested_symbol_notionals.items():
                committed_symbol = db.execute("SELECT notional FROM portfolio_admission_symbol_exposure WHERE scope_id = ? AND symbol = ?", (scope_id, symbol)).fetchone()
                committed_symbol_value = committed_symbol[0] if committed_symbol else 0.0
                reserved_symbol = db.execute("SELECT COALESCE(SUM(json_extract(value, '$[1]')), 0) FROM portfolio_admission_reservations, json_each(symbol_notionals) WHERE scope_id = ? AND json_extract(value, '$[0]') = ?", (scope_id, symbol)).fetchone()[0]
                if committed_symbol_value + reserved_symbol + requested > limits.max_symbol_notional:
                    raise PermissionError(f"symbol exposure reservation limit: {symbol}")
            expires = None if ttl_seconds is None else created + ttl_seconds
            db.execute("INSERT INTO portfolio_admission_reservations VALUES (?, ?, ?, ?, ?, ?)", (reservation_id, scope_id, requested_portfolio_notional, symbols_json, created, expires))
            db.commit()
            return RiskReservation(reservation_id, requested_portfolio_notional, tuple(sorted(requested_symbol_notionals.items())), created, expires)

    def commit(self, reservation_id: str) -> None:
        """Atomically consume a reservation and commit its exposure."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT scope_id, portfolio_notional, symbol_notionals FROM portfolio_admission_reservations WHERE reservation_id = ?", (reservation_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown reservation: {reservation_id}")
            scope_id, portfolio, symbols_json = row
            db.execute("INSERT INTO portfolio_admission_exposure(scope_id, portfolio_notional) VALUES (?, ?) ON CONFLICT(scope_id) DO UPDATE SET portfolio_notional = portfolio_notional + excluded.portfolio_notional", (scope_id, portfolio))
            for symbol, notional in json.loads(symbols_json):
                db.execute("INSERT INTO portfolio_admission_symbol_exposure(scope_id, symbol, notional) VALUES (?, ?, ?) ON CONFLICT(scope_id, symbol) DO UPDATE SET notional = notional + excluded.notional", (scope_id, symbol, notional))
            db.execute("DELETE FROM portfolio_admission_reservations WHERE reservation_id = ?", (reservation_id,))
            db.commit()

    def release(self, reservation_id: str) -> None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM portfolio_admission_reservations WHERE reservation_id = ?", (reservation_id,))
            db.commit()

    def snapshot(self, scope_id: str) -> tuple[RiskReservation, ...]:
        with self._connect() as db:
            rows = db.execute("SELECT reservation_id, portfolio_notional, symbol_notionals, created_at, expires_at FROM portfolio_admission_reservations WHERE scope_id = ?", (scope_id,)).fetchall()
        return tuple(RiskReservation(rid, portfolio, tuple(json.loads(symbols)), created, expires) for rid, portfolio, symbols, created, expires in rows)


def evaluate(order: ExecutionOrder, *, reference_price: float, portfolio_notional: float, symbol_notional: float, daily_loss: float, spread_bps: float, limits: PreTradeLimits, venue_healthy: bool = True, configuration_authorized: bool = True) -> RiskDecision:
    reasons: list[str] = []
    numeric_inputs = (reference_price, portfolio_notional, symbol_notional, daily_loss, spread_bps, limits.max_order_notional, limits.max_portfolio_notional, limits.max_symbol_notional, limits.max_daily_loss, limits.max_spread_bps, order.quantity)
    if not all(isfinite(value) for value in numeric_inputs):
        reasons.append("non-finite risk input")
    if order.quantity <= 0 or reference_price <= 0:
        reasons.append("invalid quantity/reference price")
    if portfolio_notional < 0 or symbol_notional < 0 or daily_loss < 0 or spread_bps < 0:
        reasons.append("invalid negative risk input")
    if any(limit < 0 for limit in (limits.max_order_notional, limits.max_portfolio_notional, limits.max_symbol_notional, limits.max_daily_loss, limits.max_spread_bps)):
        reasons.append("invalid negative risk limit")
    if order.side.upper() not in {"BUY", "SELL"}:
        reasons.append("invalid order side")
    notional = order.quantity * reference_price
    if notional > limits.max_order_notional:
        reasons.append("order notional limit")
    if portfolio_notional + notional > limits.max_portfolio_notional:
        reasons.append("portfolio exposure limit")
    if symbol_notional + notional > limits.max_symbol_notional:
        reasons.append("symbol exposure limit")
    if daily_loss >= limits.max_daily_loss:
        reasons.append("daily loss limit")
    if spread_bps > limits.max_spread_bps:
        reasons.append("spread limit")
    if not venue_healthy:
        reasons.append("venue unhealthy")
    if not configuration_authorized:
        reasons.append("configuration not authorized")
    return RiskDecision(allowed=not reasons, reasons=tuple(reasons))
