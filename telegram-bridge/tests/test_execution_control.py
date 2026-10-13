from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.execution_control import (
    recover_expired_leases,
    reserve_execution,
    transition_execution,
)
from app.models import ExecutionLedger, PortfolioReservation

TABLES = [
    Base.metadata.tables["execution_ledger"],
    Base.metadata.tables["portfolio_reservations"],
]


async def make_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: Base.metadata.create_all(sync, tables=TABLES))
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_reservation_is_idempotent_and_enforces_heat_limit():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            assert await reserve_execution(
                session,
                request_id="req-1",
                signal_id="sig-1",
                symbol="EURUSD",
                direction="BUY",
                risk_r=2.0,
                volatility=0.8,
                factors={"usd": 1.0},
            )
            await session.commit()

        async with factory() as session:
            assert not await reserve_execution(
                session,
                request_id="req-1",
                signal_id="sig-1",
                symbol="EURUSD",
                direction="BUY",
                risk_r=0.5,
                volatility=0.8,
                factors={},
            )
            await session.rollback()
            assert not await reserve_execution(
                session,
                request_id="req-2",
                signal_id="sig-2",
                symbol="GBPUSD",
                direction="SELL",
                risk_r=1.1,
                volatility=0.7,
                factors={"usd": -1.0},
            )
            await session.rollback()
            active = (
                await session.execute(
                    select(PortfolioReservation).where(PortfolioReservation.status == "ACTIVE")
                )
            ).scalars().all()
            assert len(active) == 1
            assert active[0].risk_r == 2.0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_transition_order_is_enforced_and_terminal_state_cannot_resurrect():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            assert await reserve_execution(
                session,
                request_id="req-3",
                signal_id="sig-3",
                symbol="USDJPY",
                direction="SELL",
                risk_r=0.5,
                volatility=0.4,
                factors={},
            )
            await session.commit()

        async with factory() as session:
            assert not await transition_execution(
                session, request_id="req-3", state="SENT", result={"broker_order_id": "123"}
            )
            await session.rollback()
            assert await transition_execution(session, request_id="req-3", state="CHECKED")
            assert await transition_execution(
                session, request_id="req-3", state="SENT", result={"broker_order_id": "123"}
            )
            assert await transition_execution(
                session, request_id="req-3", state="SENT", result={"broker_order_id": "123"}
            )
            assert await transition_execution(
                session, request_id="req-3", state="ACKED", result={"broker_position_id": "456"}
            )
            assert await transition_execution(session, request_id="req-3", state="FILLED")
            await session.commit()

        async with factory() as session:
            ledger = await session.scalar(
                select(ExecutionLedger).where(ExecutionLedger.request_id == "req-3")
            )
            assert ledger.state == "FILLED"
            assert ledger.broker_order_id == "123"
            assert ledger.broker_position_id == "456"
            reservation = await session.scalar(
                select(PortfolioReservation).where(PortfolioReservation.request_id == "req-3")
            )
            assert reservation.status == "ACTIVE"
            assert await transition_execution(
                session,
                request_id="req-3",
                state="RECONCILED",
                result={
                    "broker_reconciled": True,
                    "broker_deal_id": "789",
                    "evidence_ref": "deal-history:789",
                },
            )
            await session.commit()

        async with factory() as session:
            assert not await transition_execution(session, request_id="req-3", state="FILLED")
            await session.rollback()
            reservation = await session.scalar(
                select(PortfolioReservation).where(PortfolioReservation.request_id == "req-3")
            )
            assert reservation.status == "RELEASED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_expired_lease_requires_reconciliation_and_keeps_risk_reserved():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            assert await reserve_execution(
                session,
                request_id="req-4",
                signal_id="sig-4",
                symbol="XAUUSD",
                direction="BUY",
                risk_r=0.75,
                volatility=1.2,
                factors={"gold": 1.0},
            )
            row = await session.scalar(
                select(ExecutionLedger).where(ExecutionLedger.request_id == "req-4")
            )
            row.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
            await session.commit()

        async with factory() as session:
            assert await recover_expired_leases(session) == 1
            await session.commit()

        async with factory() as session:
            row = await session.scalar(
                select(ExecutionLedger).where(ExecutionLedger.request_id == "req-4")
            )
            reservation = await session.scalar(
                select(PortfolioReservation).where(PortfolioReservation.request_id == "req-4")
            )
            assert row.state == "RECOVERING"
            assert reservation.status == "ACTIVE"
            # A recovered/ambiguous broker request cannot be silently resent.
            assert not await transition_execution(
                session, request_id="req-4", state="RECONCILED"
            )
            assert await transition_execution(
                session,
                request_id="req-4",
                state="RECONCILED",
                result={
                    "broker_reconciled": True,
                    "broker_order_found": False,
                    "evidence_ref": "broker-history-window:2026-10-13",
                },
            )
            await session.commit()
            assert not await reserve_execution(
                session,
                request_id="req-4",
                signal_id="sig-4",
                symbol="XAUUSD",
                direction="BUY",
                risk_r=0.75,
                volatility=1.2,
                factors={"gold": 1.0},
            )
    finally:
        await engine.dispose()
