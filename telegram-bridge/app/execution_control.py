"""Durable execution admission and reconciliation state management.

This module records execution intent and state. It never sends broker orders.
A caller must complete the existing EA order-check/send/acknowledgement path.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExecutionLedger, PortfolioReservation

LEASE_SECONDS = 30
MAX_PORTFOLIO_HEAT_R = 3.0
TERMINAL_STATES = {"REJECTED", "CANCELLED", "RECONCILED"}
ALLOWED_TRANSITIONS = {
    "RESERVED": {"CHECKED", "REJECTED", "CANCELLED"},
    "CHECKED": {"SENT", "REJECTED", "CANCELLED"},
    "SENT": {"ACKED", "FILLED", "REJECTED", "CANCELLED"},
    "ACKED": {"FILLED", "REJECTED", "CANCELLED"},
    "RECOVERING": {"ACKED", "FILLED", "REJECTED", "CANCELLED", "RECONCILED"},
    "FILLED": {"RECONCILED"},
}


async def _portfolio_lock(session: AsyncSession) -> None:
    """Serialize portfolio admission on PostgreSQL, including an empty book."""
    if session.bind and session.bind.dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('midas-touch-portfolio-admission'))")
        )


def _validate_risk(risk_r: float, volatility: float, factors: dict[str, float]) -> None:
    if not math.isfinite(risk_r) or risk_r <= 0:
        raise ValueError("risk_r must be finite and greater than zero")
    if not math.isfinite(volatility) or volatility < 0:
        raise ValueError("volatility must be finite and non-negative")
    if any(not math.isfinite(value) for value in factors.values()):
        raise ValueError("factor exposures must be finite")


async def reserve_execution(
    session: AsyncSession,
    *,
    request_id: str,
    signal_id: str,
    symbol: str,
    direction: str,
    risk_r: float,
    volatility: float,
    factors: dict[str, float],
    max_heat_r: float = MAX_PORTFOLIO_HEAT_R,
) -> bool:
    """Atomically reserve normalized portfolio heat before execution is sent."""
    _validate_risk(risk_r, volatility, factors)
    if not 0 < max_heat_r <= MAX_PORTFOLIO_HEAT_R:
        raise ValueError(f"max_heat_r must be in (0, {MAX_PORTFOLIO_HEAT_R}]")
    await _portfolio_lock(session)

    existing = await session.scalar(
        select(ExecutionLedger)
        .where(ExecutionLedger.request_id == request_id)
        .with_for_update()
    )
    if existing is not None:
        return False

    active = (
        await session.execute(
            select(PortfolioReservation)
            .where(PortfolioReservation.status == "ACTIVE")
            .with_for_update()
        )
    ).scalars().all()
    current_heat = sum(abs(item.risk_r) for item in active)
    if current_heat + abs(risk_r) > max_heat_r:
        return False

    now = datetime.now(timezone.utc)
    lease_until = now + timedelta(seconds=LEASE_SECONDS)
    session.add(
        ExecutionLedger(
            request_id=request_id,
            signal_id=signal_id,
            symbol=symbol,
            state="RESERVED",
            request_json={
                "direction": direction,
                "risk_r": risk_r,
                "volatility": volatility,
                "factor_exposure": factors,
            },
            created_at=now,
            lease_until=lease_until,
        )
    )
    session.add(
        PortfolioReservation(
            request_id=request_id,
            symbol=symbol,
            direction=direction,
            risk_r=risk_r,
            volatility=volatility,
            factor_exposure=factors,
            status="ACTIVE",
            lease_until=lease_until,
            created_at=now,
        )
    )
    await session.flush()
    return True


async def transition_execution(
    session: AsyncSession,
    *,
    request_id: str,
    state: str,
    result: dict | None = None,
) -> bool:
    """Apply a legal state transition; never permit terminal-state resurrection."""
    row = await session.scalar(
        select(ExecutionLedger)
        .where(ExecutionLedger.request_id == request_id)
        .with_for_update()
    )
    if row is None:
        return False
    if row.state == state:
        # Retries of the same state are idempotent only if the payload agrees.
        return bool(result is None or result == row.result_json)
    if state not in ALLOWED_TRANSITIONS.get(row.state, set()):
        return False

    if state == "ACKED":
        if not result or result.get("broker_acknowledged") is not True:
            return False
        if not (result.get("broker_order_id") or row.broker_order_id):
            return False
    if state == "FILLED":
        if not result or result.get("broker_confirmed_fill") is not True:
            return False
        if not any(result.get(key) for key in ("broker_order_id", "broker_deal_id", "broker_position_id")):
            return False

    # Broker-facing terminal states must carry explicit evidence. A timeout or
    # a local cancel request is not proof that the broker did not fill an order.
    if row.state in {"SENT", "ACKED", "RECOVERING"} and state in {"REJECTED", "CANCELLED"}:
        if not result or result.get("broker_confirmed_terminal") is not True:
            return False
        if not isinstance(result.get("evidence_ref"), str) or not result["evidence_ref"].strip():
            return False
    if state == "RECONCILED":
        if not result or result.get("broker_reconciled") is not True:
            return False
        has_broker_reference = any(
            result.get(key) or getattr(row, key)
            for key in ("broker_order_id", "broker_deal_id", "broker_position_id")
        )
        confirmed_absence = (
            row.state == "RECOVERING"
            and result.get("broker_order_found") is False
            and isinstance(result.get("evidence_ref"), str)
            and bool(result["evidence_ref"].strip())
        )
        if not has_broker_reference and not confirmed_absence:
            return False

    now = datetime.now(timezone.utc)
    row.state = state
    if result is not None:
        row.result_json = result
        for key, column in (
            ("broker_order_id", "broker_order_id"),
            ("broker_deal_id", "broker_deal_id"),
            ("broker_position_id", "broker_position_id"),
        ):
            value = result.get(key)
            if value is not None:
                setattr(row, column, str(value))

    if state == "CHECKED":
        row.checked_at = now
    if state == "SENT":
        row.sent_at = now
    if state in TERMINAL_STATES:
        row.reconciled_at = now
        if row.created_at:
            created = row.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            row.latency_ms = max(0.0, (now - created).total_seconds() * 1000.0)
        reservation = await session.scalar(
            select(PortfolioReservation)
            .where(PortfolioReservation.request_id == request_id)
            .with_for_update()
        )
        if reservation is not None:
            reservation.status = "RELEASED"
    await session.flush()
    return True


async def recover_expired_leases(session: AsyncSession) -> int:
    """Mark ambiguous expired requests for reconciliation without releasing risk."""
    now = datetime.now(timezone.utc)
    rows = (
        await session.execute(
            select(ExecutionLedger)
            .where(
                ExecutionLedger.lease_until < now,
                ExecutionLedger.state.in_({"RESERVED", "CHECKED", "SENT", "ACKED"}),
            )
            .with_for_update()
        )
    ).scalars().all()
    for row in rows:
        # An expired lease is not proof that the broker rejected the order.
        # Keep its portfolio reservation ACTIVE until broker state is reconciled.
        row.state = "RECOVERING"
    await session.flush()
    return len(rows)
