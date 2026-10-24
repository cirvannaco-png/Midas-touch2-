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
    "CHECKED": {"SENT", "FILLED", "RECOVERING", "REJECTED", "CANCELLED"},
    "SENT": {"ACKED", "FILLED", "RECOVERING", "REJECTED", "CANCELLED"},
    "ACKED": {"FILLED", "RECOVERING", "REJECTED", "CANCELLED"},
    "RECOVERING": {"ACKED", "FILLED", "REJECTED", "CANCELLED", "RECONCILED"},
    "FILLED": {"RECONCILED"},
}


async def _portfolio_lock(session: AsyncSession, portfolio_key: str) -> None:
    """Serialize admission per account portfolio, including an empty book."""
    if session.bind and session.bind.dialect.name == "postgresql":
        await session.execute(
            text(
                "SELECT pg_advisory_xact_lock(hashtext('midas-touch-portfolio-admission:' || :portfolio_key))"
            ),
            {"portfolio_key": portfolio_key},
        )


def _validate_risk(
    risk_r: float,
    volatility: float,
    factors: dict[str, float],
    *,
    allow_zero: bool = False,
) -> None:
    lower_bound_invalid = risk_r < 0 if allow_zero else risk_r <= 0
    if not math.isfinite(risk_r) or lower_bound_invalid:
        if allow_zero:
            raise ValueError("risk_r must be finite and non-negative")
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
    portfolio_key: str = "legacy-unscoped",
) -> bool:
    """Atomically reserve normalized heat inside one account portfolio."""
    if not portfolio_key or len(portfolio_key) > 128:
        raise ValueError("portfolio_key must be 1-128 characters")
    _validate_risk(risk_r, volatility, factors)
    if not 0 < max_heat_r <= MAX_PORTFOLIO_HEAT_R:
        raise ValueError(f"max_heat_r must be in (0, {MAX_PORTFOLIO_HEAT_R}]")
    await _portfolio_lock(session, portfolio_key)

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
            .where(
                PortfolioReservation.status == "ACTIVE",
                PortfolioReservation.portfolio_key == portfolio_key,
            )
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
            portfolio_key=portfolio_key,
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
            portfolio_key=portfolio_key,
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
        # A duplicate broker callback may add identifiers that were not available
        # in the first response. Merge only non-conflicting broker identities.
        if result is None:
            return True
        current = dict(row.result_json or {})
        for key in ("broker_order_id", "broker_deal_id", "broker_position_id"):
            old_id = getattr(row, key)
            new_id = result.get(key)
            if old_id and new_id and str(old_id) != str(new_id):
                return False
            if new_id and not old_id:
                setattr(row, key, str(new_id))
        for key in ("broker_acknowledged", "broker_confirmed_fill", "broker_reconciled"):
            if current.get(key) is True and result.get(key) is False:
                return False
        current.update(result)
        row.result_json = current
        await session.flush()
        return True
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
        evidence_ref = result.get("evidence_ref") if result else None
        # A durable local assertion that no broker API call was attempted is
        # sufficient only for that narrow case. Once a send was attempted,
        # release still requires broker-confirmed terminal evidence.
        proven_not_submitted = (
            result is not None
            and result.get("submission_attempted") is False
            and isinstance(evidence_ref, str)
            and bool(evidence_ref.strip())
        )
        broker_terminal_confirmed = (
            result is not None
            and result.get("broker_confirmed_terminal") is True
            and isinstance(evidence_ref, str)
            and bool(evidence_ref.strip())
        )
        if not proven_not_submitted and not broker_terminal_confirmed:
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



async def _lookup_broker_record(
    session: AsyncSession,
    *,
    portfolio_key: str,
    broker_position_id: str | None = None,
    broker_order_id: str | None = None,
) -> ExecutionLedger | None:
    if broker_position_id:
        row = await session.scalar(
            select(ExecutionLedger)
            .where(
                ExecutionLedger.portfolio_key == portfolio_key,
                ExecutionLedger.broker_position_id == broker_position_id,
            )
            .with_for_update()
        )
        if row is not None:
            return row
    if broker_order_id:
        return await session.scalar(
            select(ExecutionLedger)
            .where(
                ExecutionLedger.portfolio_key == portfolio_key,
                ExecutionLedger.broker_order_id == broker_order_id,
            )
            .with_for_update()
        )
    return None


async def _upsert_active_reservation(
    session: AsyncSession,
    *,
    request_id: str,
    portfolio_key: str,
    symbol: str,
    direction: str,
    risk_r: float,
    volatility: float,
    factors: dict[str, float],
) -> None:
    now = datetime.now(timezone.utc)
    lease_until = now + timedelta(seconds=LEASE_SECONDS)
    reservation = await session.scalar(
        select(PortfolioReservation)
        .where(PortfolioReservation.request_id == request_id)
        .with_for_update()
    )
    if reservation is None:
        reservation = PortfolioReservation(
            request_id=request_id,
            portfolio_key=portfolio_key,
            symbol=symbol,
            direction=direction,
            risk_r=risk_r,
            volatility=volatility,
            factor_exposure=factors,
            status="ACTIVE",
            lease_until=lease_until,
            created_at=now,
        )
        session.add(reservation)
    else:
        if reservation.portfolio_key != portfolio_key:
            raise ValueError("reservation portfolio does not match broker portfolio")
        reservation.symbol = symbol
        reservation.direction = direction
        reservation.risk_r = risk_r
        reservation.volatility = volatility
        reservation.factor_exposure = factors
        reservation.status = "ACTIVE"
        reservation.lease_until = lease_until


async def reconcile_open_position(
    session: AsyncSession,
    *,
    portfolio_key: str,
    request_id: str,
    broker_position_id: str,
    broker_order_id: str | None,
    broker_deal_id: str | None,
    symbol: str,
    direction: str,
    risk_r: float,
    volatility: float,
    factors: dict[str, float],
    evidence_ref: str,
) -> tuple[str, float, bool]:
    """Import or refresh an observed broker position without dropping other risk."""
    if not portfolio_key or len(portfolio_key) > 128:
        raise ValueError("portfolio_key must be 1-128 characters")
    if not request_id or len(request_id) > 128:
        raise ValueError("request_id must be 1-128 characters")
    if not broker_position_id or not evidence_ref:
        raise ValueError("broker_position_id and evidence_ref are required")
    _validate_risk(risk_r, volatility, factors, allow_zero=True)
    await _portfolio_lock(session, portfolio_key)

    row = await _lookup_broker_record(
        session,
        portfolio_key=portfolio_key,
        broker_position_id=broker_position_id,
        broker_order_id=broker_order_id,
    )
    if row is None:
        by_request = await session.scalar(
            select(ExecutionLedger)
            .where(ExecutionLedger.request_id == request_id)
            .with_for_update()
        )
        if by_request is not None:
            if by_request.portfolio_key != portfolio_key:
                raise ValueError("request_id already belongs to another portfolio")
            if by_request.broker_position_id and by_request.broker_position_id != broker_position_id:
                raise ValueError("request_id is already bound to a different broker position")
            row = by_request

    now = datetime.now(timezone.utc)
    if row is None:
        row = ExecutionLedger(
            request_id=request_id,
            portfolio_key=portfolio_key,
            signal_id=None,
            symbol=symbol,
            state="FILLED",
            broker_order_id=broker_order_id,
            broker_deal_id=broker_deal_id,
            broker_position_id=broker_position_id,
            request_json={
                "origin": "broker_snapshot_adoption",
                "direction": direction,
                "risk_r": risk_r,
                "volatility": volatility,
                "factor_exposure": factors,
            },
            result_json={},
            created_at=now,
            checked_at=now,
            sent_at=now,
            lease_until=now + timedelta(seconds=LEASE_SECONDS),
        )
        session.add(row)
    else:
        if row.portfolio_key != portfolio_key:
            raise ValueError("broker record portfolio does not match")
        # The currently observed broker position is authoritative. This also
        # repairs a previous local timeout / RECOVERING state after restart.
        row.state = "FILLED"
        row.broker_position_id = broker_position_id
        if broker_order_id:
            row.broker_order_id = broker_order_id
        if broker_deal_id:
            row.broker_deal_id = broker_deal_id
        row.symbol = symbol
        row.lease_until = now + timedelta(seconds=LEASE_SECONDS)
        row.reconciled_at = None

    merged = dict(row.result_json or {})
    merged.update(
        {
            "broker_confirmed_fill": True,
            "broker_reconciled": True,
            "broker_position_id": broker_position_id,
            "evidence_ref": evidence_ref,
            "snapshot_observed_at": now.isoformat(),
        }
    )
    if broker_order_id:
        merged["broker_order_id"] = broker_order_id
    if broker_deal_id:
        merged["broker_deal_id"] = broker_deal_id
    row.result_json = merged

    await _upsert_active_reservation(
        session,
        request_id=row.request_id,
        portfolio_key=portfolio_key,
        symbol=symbol,
        direction=direction,
        risk_r=risk_r,
        volatility=volatility,
        factors=factors,
    )
    await session.flush()

    active = (
        await session.execute(
            select(PortfolioReservation).where(
                PortfolioReservation.portfolio_key == portfolio_key,
                PortfolioReservation.status == "ACTIVE",
            )
        )
    ).scalars().all()
    total_heat = sum(abs(item.risk_r) for item in active)
    return row.request_id, total_heat, total_heat > MAX_PORTFOLIO_HEAT_R


async def update_position_risk(
    session: AsyncSession,
    *,
    portfolio_key: str,
    broker_position_id: str,
    direction: str,
    risk_r: float,
    volatility: float,
    factors: dict[str, float],
    evidence_ref: str,
) -> bool:
    _validate_risk(risk_r, volatility, factors, allow_zero=True)
    if not evidence_ref:
        raise ValueError("evidence_ref is required")
    await _portfolio_lock(session, portfolio_key)
    row = await _lookup_broker_record(
        session, portfolio_key=portfolio_key, broker_position_id=broker_position_id
    )
    if row is None:
        return False
    if row.state in {"REJECTED", "CANCELLED", "RECONCILED"}:
        # A present live position overrides an old local terminal classification.
        row.state = "FILLED"
        row.reconciled_at = None
    merged = dict(row.result_json or {})
    merged.update(
        {
            "broker_reconciled": True,
            "broker_position_id": broker_position_id,
            "position_risk_updated": True,
            "evidence_ref": evidence_ref,
            "risk_updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    row.result_json = merged
    await _upsert_active_reservation(
        session,
        request_id=row.request_id,
        portfolio_key=portfolio_key,
        symbol=row.symbol,
        direction=direction,
        risk_r=risk_r,
        volatility=volatility,
        factors=factors,
    )
    await session.flush()
    return True


async def reconcile_closed_position(
    session: AsyncSession,
    *,
    portfolio_key: str,
    broker_position_id: str,
    broker_deal_id: str,
    evidence_ref: str,
    request_id: str | None = None,
) -> bool:
    """Release a position reservation only after MT5 reports a closed position."""
    if not broker_deal_id or not evidence_ref:
        raise ValueError("broker_deal_id and evidence_ref are required")
    await _portfolio_lock(session, portfolio_key)
    row = await _lookup_broker_record(
        session, portfolio_key=portfolio_key, broker_position_id=broker_position_id
    )
    if row is None and request_id:
        row = await session.scalar(
            select(ExecutionLedger)
            .where(
                ExecutionLedger.portfolio_key == portfolio_key,
                ExecutionLedger.request_id == request_id,
            )
            .with_for_update()
        )
    if row is None:
        return False
    if row.portfolio_key != portfolio_key:
        raise ValueError("closed position portfolio does not match")
    now = datetime.now(timezone.utc)
    row.state = "RECONCILED"
    row.reconciled_at = now
    row.broker_position_id = broker_position_id
    row.broker_deal_id = broker_deal_id
    merged = dict(row.result_json or {})
    merged.update(
        {
            "broker_reconciled": True,
            "broker_position_id": broker_position_id,
            "broker_deal_id": broker_deal_id,
            "broker_position_open": False,
            "evidence_ref": evidence_ref,
            "reconciled_at": now.isoformat(),
        }
    )
    row.result_json = merged
    reservation = await session.scalar(
        select(PortfolioReservation)
        .where(PortfolioReservation.request_id == row.request_id)
        .with_for_update()
    )
    if reservation is not None:
        reservation.status = "RELEASED"
        reservation.lease_until = now
    await session.flush()
    return True


async def sync_pending_order(
    session: AsyncSession,
    *,
    portfolio_key: str,
    request_id: str,
    broker_order_id: str,
    symbol: str,
    direction: str,
    risk_r: float,
    volatility: float,
    factors: dict[str, float],
    evidence_ref: str,
) -> tuple[str, float, bool]:
    """Import a live pending order into the account portfolio's risk book."""
    if not broker_order_id or not evidence_ref:
        raise ValueError("broker_order_id and evidence_ref are required")
    _validate_risk(risk_r, volatility, factors)
    await _portfolio_lock(session, portfolio_key)
    row = await _lookup_broker_record(
        session, portfolio_key=portfolio_key, broker_order_id=broker_order_id
    )
    if row is None:
        row = await session.scalar(
            select(ExecutionLedger)
            .where(ExecutionLedger.request_id == request_id)
            .with_for_update()
        )
    now = datetime.now(timezone.utc)
    if row is None:
        row = ExecutionLedger(
            request_id=request_id,
            portfolio_key=portfolio_key,
            signal_id=None,
            symbol=symbol,
            state="ACKED",
            broker_order_id=broker_order_id,
            request_json={
                "origin": "broker_pending_order_snapshot",
                "direction": direction,
                "risk_r": risk_r,
                "volatility": volatility,
                "factor_exposure": factors,
            },
            result_json={},
            created_at=now,
            checked_at=now,
            sent_at=now,
            lease_until=now + timedelta(seconds=LEASE_SECONDS),
        )
        session.add(row)
    else:
        if row.portfolio_key != portfolio_key:
            raise ValueError("pending order portfolio does not match")
        if row.state not in {"RECONCILED", "CANCELLED", "REJECTED", "FILLED"}:
            row.state = "ACKED"
        row.broker_order_id = broker_order_id
        row.symbol = symbol
        row.lease_until = now + timedelta(seconds=LEASE_SECONDS)
    merged = dict(row.result_json or {})
    merged.update(
        {
            "broker_acknowledged": True,
            "broker_order_id": broker_order_id,
            "evidence_ref": evidence_ref,
            "pending_order_observed_at": now.isoformat(),
        }
    )
    row.result_json = merged
    await _upsert_active_reservation(
        session,
        request_id=row.request_id,
        portfolio_key=portfolio_key,
        symbol=symbol,
        direction=direction,
        risk_r=risk_r,
        volatility=volatility,
        factors=factors,
    )
    await session.flush()
    active = (
        await session.execute(
            select(PortfolioReservation).where(
                PortfolioReservation.portfolio_key == portfolio_key,
                PortfolioReservation.status == "ACTIVE",
            )
        )
    ).scalars().all()
    total_heat = sum(abs(item.risk_r) for item in active)
    return row.request_id, total_heat, total_heat > MAX_PORTFOLIO_HEAT_R


async def reconcile_terminal_order(
    session: AsyncSession,
    *,
    portfolio_key: str,
    broker_order_id: str,
    terminal_state: str,
    evidence_ref: str,
) -> bool:
    """Record broker-confirmed cancellation/rejection of a pending order."""
    if terminal_state not in {"CANCELLED", "REJECTED"}:
        raise ValueError("terminal_state must be CANCELLED or REJECTED")
    if not evidence_ref:
        raise ValueError("evidence_ref is required")
    await _portfolio_lock(session, portfolio_key)
    row = await session.scalar(
        select(ExecutionLedger)
        .where(
            ExecutionLedger.portfolio_key == portfolio_key,
            ExecutionLedger.broker_order_id == broker_order_id,
        )
        .with_for_update()
    )
    if row is None or row.state in {"FILLED", "RECONCILED"}:
        return False
    now = datetime.now(timezone.utc)
    row.state = terminal_state
    row.reconciled_at = now
    merged = dict(row.result_json or {})
    merged.update(
        {
            "broker_confirmed_terminal": True,
            "broker_order_id": broker_order_id,
            "evidence_ref": evidence_ref,
            "terminal_state": terminal_state,
            "reconciled_at": now.isoformat(),
        }
    )
    row.result_json = merged
    reservation = await session.scalar(
        select(PortfolioReservation)
        .where(PortfolioReservation.request_id == row.request_id)
        .with_for_update()
    )
    if reservation is not None:
        reservation.status = "RELEASED"
        reservation.lease_until = now
    await session.flush()
    return True
