from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.execution_control import (
    confirm_position_modification,
    prepare_position_modification,
    reconcile_closed_position,
    reconcile_open_position,
    reconcile_terminal_order,
    recover_expired_leases,
    reserve_execution,
    sync_pending_order,
    transition_execution,
    update_position_risk,
)
from app.models import ExecutionLedger, ExecutionPositionModification, PortfolioReservation

TABLES = [
    Base.metadata.tables["execution_ledger"],
    Base.metadata.tables["portfolio_reservations"],
    Base.metadata.tables["execution_position_modifications"],
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
            assert not await transition_execution(
                session, request_id="req-3", state="REJECTED"
            )
            assert not await transition_execution(
                session, request_id="req-3", state="FILLED"
            )
            assert await transition_execution(
                session, request_id="req-3", state="ACKED", result={"broker_acknowledged": True, "broker_position_id": "456"}
            )
            assert await transition_execution(
                session,
                request_id="req-3",
                state="FILLED",
                result={"broker_confirmed_fill": True, "broker_deal_id": "789"},
            )
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


def test_execution_ledger_route_requires_api_key(client):
    payload = {
        "portfolio_key": "account:test:magic:test",
        "requested_by": "MT5_EA",
        "request_id": "route-auth-test",
        "signal_id": "route-auth-signal",
        "symbol": "EURUSD",
        "direction": "BUY",
        "risk_r": 0.25,
        "volatility": 0.5,
        "factors": {"usd": 1.0},
    }
    missing = client.post("/execution-ledger/reserve", json=payload)
    assert missing.status_code == 422
    wrong = client.post(
        "/execution-ledger/reserve",
        json=payload,
        headers={"X-API-Key": "wrong-key"},
    )
    assert wrong.status_code == 401


def test_execution_ledger_api_is_mounted_and_rejects_duplicate_requests(client, auth_headers):
    payload = {
        "portfolio_key": "account:test:magic:test",
        "requested_by": "MT5_EA",
        "request_id": "route-idempotency-test",
        "signal_id": "route-idempotency-signal",
        "symbol": "EURUSD",
        "direction": "BUY",
        "risk_r": 0.25,
        "volatility": 0.5,
        "factors": {"usd": 1.0},
    }
    first = client.post("/execution-ledger/reserve", json=payload, headers=auth_headers)
    assert first.status_code == 200
    assert first.json()["state"] == "RESERVED"

    duplicate = client.post("/execution-ledger/reserve", json=payload, headers=auth_headers)
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_portfolio_heat_isolated_by_portfolio_key():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            assert await reserve_execution(
                session,
                portfolio_key="server-A:login-1:magic-7",
                request_id="account-a-request",
                signal_id="signal-a",
                symbol="EURUSD",
                direction="BUY",
                risk_r=2.5,
                volatility=0.8,
                factors={"usd": 1.0},
            )
            await session.commit()

        async with factory() as session:
            assert await reserve_execution(
                session,
                portfolio_key="server-B:login-2:magic-7",
                request_id="account-b-request",
                signal_id="signal-b",
                symbol="EURUSD",
                direction="BUY",
                risk_r=2.5,
                volatility=0.8,
                factors={"usd": 1.0},
            )
            await session.commit()
    finally:
        await engine.dispose()



@pytest.mark.asyncio
async def test_startup_position_sync_adopts_and_then_updates_existing_risk():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            request_id, heat, over_limit = await reconcile_open_position(
                session,
                portfolio_key="Exness:123:magic-77",
                request_id="brokerpos:Exness:123:magic-77:9001",
                broker_position_id="9001",
                broker_order_id="8001",
                broker_deal_id="7001",
                symbol="EURUSD",
                direction="BUY",
                risk_r=1.0,
                volatility=0.6,
                factors={"usd": 1.0},
                evidence_ref="mt5-position-snapshot:9001",
            )
            assert request_id == "brokerpos:Exness:123:magic-77:9001"
            assert heat == 1.0
            assert not over_limit
            await session.commit()

        async with factory() as session:
            request_id, heat, over_limit = await reconcile_open_position(
                session,
                portfolio_key="Exness:123:magic-77",
                request_id="unused-request-id",
                broker_position_id="9001",
                broker_order_id="8001",
                broker_deal_id="7002",
                symbol="EURUSD",
                direction="BUY",
                risk_r=0.4,
                volatility=0.4,
                factors={"usd": 0.4},
                evidence_ref="mt5-restart-snapshot:9001",
            )
            assert request_id == "brokerpos:Exness:123:magic-77:9001"
            assert heat == 0.4
            assert not over_limit
            await session.commit()

        async with factory() as session:
            rows = (
                await session.execute(
                    select(PortfolioReservation).where(
                        PortfolioReservation.portfolio_key == "Exness:123:magic-77"
                    )
                )
            ).scalars().all()
            assert len(rows) == 1
            assert rows[0].risk_r == 0.4
            assert rows[0].status == "ACTIVE"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_partial_close_updates_risk_and_full_close_releases_reservation():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            await reconcile_open_position(
                session,
                portfolio_key="Exness:123:magic-78",
                request_id="brokerpos:Exness:123:magic-78:9002",
                broker_position_id="9002",
                broker_order_id="8002",
                broker_deal_id="7003",
                symbol="XAUUSD",
                direction="SELL",
                risk_r=1.2,
                volatility=1.1,
                factors={"gold": -1.0},
                evidence_ref="mt5-position-snapshot:9002",
            )
            await session.commit()

        async with factory() as session:
            assert await update_position_risk(
                session,
                portfolio_key="Exness:123:magic-78",
                broker_position_id="9002",
                direction="SELL",
                risk_r=0.6,
                volatility=0.7,
                factors={"gold": -0.5},
                evidence_ref="mt5-partial-close-deal:7004",
            )
            await session.commit()

        async with factory() as session:
            reservation = await session.scalar(
                select(PortfolioReservation).where(
                    PortfolioReservation.request_id == "brokerpos:Exness:123:magic-78:9002"
                )
            )
            assert reservation.risk_r == 0.6
            assert reservation.status == "ACTIVE"
            assert await reconcile_closed_position(
                session,
                portfolio_key="Exness:123:magic-78",
                broker_position_id="9002",
                broker_deal_id="7005",
                evidence_ref="mt5-position-closed:7005",
            )
            await session.commit()

        async with factory() as session:
            reservation = await session.scalar(
                select(PortfolioReservation).where(
                    PortfolioReservation.request_id == "brokerpos:Exness:123:magic-78:9002"
                )
            )
            assert reservation.status == "RELEASED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pending_order_is_adopted_and_only_released_with_terminal_broker_evidence():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            request_id, heat, over_limit = await sync_pending_order(
                session,
                portfolio_key="Broker:777:magic-9",
                request_id="pending:Broker:777:magic-9:4567",
                broker_order_id="4567",
                symbol="GBPUSD",
                direction="SELL",
                risk_r=0.8,
                volatility=0.7,
                factors={},
                evidence_ref="mt5-order-snapshot:4567",
            )
            assert request_id == "pending:Broker:777:magic-9:4567"
            assert heat == 0.8
            assert not over_limit
            await session.commit()

        async with factory() as session:
            assert await reconcile_terminal_order(
                session,
                portfolio_key="Broker:777:magic-9",
                broker_order_id="4567",
                terminal_state="CANCELLED",
                evidence_ref="mt5-history-order:4567:CANCELED",
            )
            await session.commit()

        async with factory() as session:
            reservation = await session.scalar(
                select(PortfolioReservation).where(
                    PortfolioReservation.request_id == "pending:Broker:777:magic-9:4567"
                )
            )
            assert reservation.status == "RELEASED"
    finally:
        await engine.dispose()

@pytest.mark.asyncio
async def test_sent_intent_releases_risk_only_with_proof_no_broker_call_was_attempted():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            assert await reserve_execution(
                session,
                request_id="local-nonsend",
                signal_id="local-nonsend-signal",
                symbol="EURUSD",
                direction="BUY",
                risk_r=0.5,
                volatility=0.3,
                factors={},
                portfolio_key="broker:account:magic",
            )
            assert await transition_execution(
                session, request_id="local-nonsend", state="CHECKED"
            )
            assert await transition_execution(
                session,
                request_id="local-nonsend",
                state="SENT",
                result={"ea_send_intent": True},
            )
            assert not await transition_execution(
                session, request_id="local-nonsend", state="REJECTED"
            )
            assert await transition_execution(
                session,
                request_id="local-nonsend",
                state="REJECTED",
                result={
                    "submission_attempted": False,
                    "evidence_ref": "ea-local-preflight:decision-1",
                },
            )
            await session.commit()

        async with factory() as session:
            reservation = await session.scalar(
                select(PortfolioReservation).where(
                    PortfolioReservation.request_id == "local-nonsend"
                )
            )
            assert reservation.status == "RELEASED"
    finally:
        await engine.dispose()

@pytest.mark.asyncio
async def test_breakeven_protected_position_can_have_zero_remaining_stop_risk():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            request_id, heat, over_limit = await reconcile_open_position(
                session,
                portfolio_key="Exness:123:magic-79",
                request_id="brokerpos:Exness:123:magic-79:9003",
                broker_position_id="9003",
                broker_order_id="8003",
                broker_deal_id="7006",
                symbol="EURUSD",
                direction="BUY",
                risk_r=0.0,
                volatility=0.4,
                factors={"usd": 0.0},
                evidence_ref="mt5-breakeven-position:9003",
            )
            assert request_id == "brokerpos:Exness:123:magic-79:9003"
            assert heat == 0.0
            assert not over_limit
            await session.commit()

        async with factory() as session:
            updated = await update_position_risk(
                session,
                portfolio_key="Exness:123:magic-79",
                broker_position_id="9003",
                direction="BUY",
                risk_r=0.0,
                volatility=0.3,
                factors={"usd": 0.0},
                evidence_ref="mt5-breakeven-stop:9003",
            )
            assert updated
            await session.commit()

        async with factory() as session:
            reservation = await session.scalar(
                select(PortfolioReservation).where(
                    PortfolioReservation.request_id == "brokerpos:Exness:123:magic-79:9003"
                )
            )
            assert reservation is not None
            assert reservation.status == "ACTIVE"
            assert reservation.risk_r == 0.0

        async with factory() as session:
            with pytest.raises(ValueError, match="greater than zero"):
                await reserve_execution(
                    session,
                    portfolio_key="Exness:123:magic-79",
                    request_id="must-not-reserve-zero-risk",
                    signal_id="signal-zero-risk",
                    symbol="EURUSD",
                    direction="BUY",
                    risk_r=0.0,
                    volatility=0.0,
                    factors={},
                )
            await session.rollback()
    finally:
        await engine.dispose()



@pytest.mark.asyncio
async def test_position_modification_is_durable_idempotent_and_updates_reserved_risk():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            await reconcile_open_position(
                session,
                portfolio_key="Exness-Demo:123:magic-88",
                request_id="position:88",
                broker_position_id="8800",
                broker_order_id="8801",
                broker_deal_id="8802",
                symbol="EURUSD",
                direction="BUY",
                risk_r=1.0,
                volatility=0.4,
                factors={},
                evidence_ref="mt5-position-snapshot:8800",
                stop_loss=1.0900,
                take_profit=1.1200,
            )
            await session.commit()

        async with factory() as session:
            prepared, status = await prepare_position_modification(
                session,
                portfolio_key="Exness-Demo:123:magic-88",
                event_id="modify:8800:1",
                broker_position_id="8800",
                symbol="EURUSD",
                direction="BUY",
                old_stop_loss=1.0900,
                old_take_profit=1.1200,
                proposed_stop_loss=1.0980,
                proposed_take_profit=1.1200,
                evidence_ref="mt5-stop-intent:8800:1",
            )
            assert prepared and status == "PENDING"
            await session.commit()

        async with factory() as session:
            # A modification whose broker outcome is not yet reconciled blocks
            # new admissions for the entire account portfolio.
            assert not await reserve_execution(
                session,
                portfolio_key="Exness-Demo:123:magic-88",
                request_id="new-order-1",
                signal_id="new-signal-1",
                symbol="GBPUSD",
                direction="BUY",
                risk_r=0.2,
                volatility=0.2,
                factors={},
            )
            await session.rollback()

        async with factory() as session:
            confirmed = await confirm_position_modification(
                session,
                portfolio_key="Exness-Demo:123:magic-88",
                event_id="modify:8800:1",
                actual_stop_loss=1.0980,
                actual_take_profit=1.1200,
                risk_r=0.3,
                volatility=0.2,
                evidence_ref="mt5-stop-observed:8800:1",
            )
            assert confirmed
            await session.commit()

        async with factory() as session:
            event = await session.scalar(
                select(ExecutionPositionModification).where(
                    ExecutionPositionModification.event_id == "modify:8800:1"
                )
            )
            reservation = await session.scalar(
                select(PortfolioReservation).where(PortfolioReservation.request_id == "position:88")
            )
            assert event.status == "APPLIED"
            assert event.actual_stop_loss == 1.0980
            assert reservation.risk_r == 0.3
            assert await confirm_position_modification(
                session,
                portfolio_key="Exness-Demo:123:magic-88",
                event_id="modify:8800:1",
                actual_stop_loss=1.0980,
                actual_take_profit=1.1200,
                risk_r=0.3,
                volatility=0.2,
                evidence_ref="mt5-stop-observed:8800:1-replay",
            )
            assert await reserve_execution(
                session,
                portfolio_key="Exness-Demo:123:magic-88",
                request_id="new-order-1",
                signal_id="new-signal-1",
                symbol="GBPUSD",
                direction="BUY",
                risk_r=0.2,
                volatility=0.2,
                factors={},
            )
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_position_modification_rejects_looser_stops_and_conflicting_idempotency_key():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            await reconcile_open_position(
                session,
                portfolio_key="Exness-Demo:123:magic-89",
                request_id="position:89",
                broker_position_id="8900",
                broker_order_id="8901",
                broker_deal_id="8902",
                symbol="EURUSD",
                direction="BUY",
                risk_r=0.8,
                volatility=0.3,
                factors={},
                evidence_ref="mt5-position-snapshot:8900",
            )
            with pytest.raises(ValueError, match="loosen protection"):
                await prepare_position_modification(
                    session,
                    portfolio_key="Exness-Demo:123:magic-89",
                    event_id="modify:8900:bad",
                    broker_position_id="8900",
                    symbol="EURUSD",
                    direction="BUY",
                    old_stop_loss=1.0900,
                    old_take_profit=1.1200,
                    proposed_stop_loss=1.0800,
                    proposed_take_profit=1.1200,
                    evidence_ref="mt5-stop-intent:8900:bad",
                )
            prepared, status = await prepare_position_modification(
                session,
                portfolio_key="Exness-Demo:123:magic-89",
                event_id="modify:8900:1",
                broker_position_id="8900",
                symbol="EURUSD",
                direction="BUY",
                old_stop_loss=1.0900,
                old_take_profit=1.1200,
                proposed_stop_loss=1.0950,
                proposed_take_profit=1.1200,
                evidence_ref="mt5-stop-intent:8900:1",
            )
            assert prepared and status == "PENDING"
            await session.commit()

        async with factory() as session:
            with pytest.raises(ValueError, match="reused with different"):
                await prepare_position_modification(
                    session,
                    portfolio_key="Exness-Demo:123:magic-89",
                    event_id="modify:8900:1",
                    broker_position_id="8900",
                    symbol="EURUSD",
                    direction="BUY",
                    old_stop_loss=1.0900,
                    old_take_profit=1.1200,
                    proposed_stop_loss=1.0960,
                    proposed_take_profit=1.1200,
                    evidence_ref="conflict",
                )
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_startup_broker_snapshot_resolves_pending_modification_from_actual_stop():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            await reconcile_open_position(
                session,
                portfolio_key="Exness-Demo:123:magic-90",
                request_id="position:90",
                broker_position_id="9000",
                broker_order_id="9001",
                broker_deal_id="9002",
                symbol="EURUSD",
                direction="BUY",
                risk_r=1.0,
                volatility=0.2,
                factors={},
                evidence_ref="snapshot-before",
                stop_loss=1.0900,
                take_profit=1.1200,
            )
            await prepare_position_modification(
                session,
                portfolio_key="Exness-Demo:123:magic-90",
                event_id="modify:9000:1",
                broker_position_id="9000",
                symbol="EURUSD",
                direction="BUY",
                old_stop_loss=1.0900,
                old_take_profit=1.1200,
                proposed_stop_loss=1.0950,
                proposed_take_profit=1.1200,
                evidence_ref="intent",
            )
            await session.commit()

        async with factory() as session:
            await reconcile_open_position(
                session,
                portfolio_key="Exness-Demo:123:magic-90",
                request_id="position:90",
                broker_position_id="9000",
                broker_order_id="9001",
                broker_deal_id="9002",
                symbol="EURUSD",
                direction="BUY",
                risk_r=0.4,
                volatility=0.2,
                factors={},
                evidence_ref="broker-snapshot-after-restart",
                stop_loss=1.0960,
                take_profit=1.1200,
            )
            await session.commit()

        async with factory() as session:
            event = await session.scalar(
                select(ExecutionPositionModification).where(
                    ExecutionPositionModification.event_id == "modify:9000:1"
                )
            )
            assert event.status == "APPLIED"
            assert event.actual_stop_loss == 1.0960
            assert event.resolution_evidence_ref == "broker-snapshot-after-restart"
    finally:
        await engine.dispose()


def test_ai_cannot_reserve_broker_execution_even_with_a_client_supplied_actor(client):
    payload = {
        "portfolio_key": "account:test:magic:ai",
        "request_id": "ai-must-not-reserve",
        "signal_id": "ai-proposal",
        "symbol": "EURUSD",
        "direction": "BUY",
        "risk_r": 0.1,
        "volatility": 0.1,
        "factors": {},
        "requested_by": "AI_AGENT",
    }
    response = client.post(
        "/execution-ledger/reserve",
        json=payload,
        headers={"X-API-Key": "test-secret-key"},
    )
    assert response.status_code == 403



def test_ai_cannot_prepare_position_modification(client):
    payload = {
        "portfolio_key": "account:test:magic:ai",
        "event_id": "ai-modification-attempt",
        "broker_position_id": "123",
        "symbol": "EURUSD",
        "direction": "BUY",
        "old_stop_loss": 1.0900,
        "old_take_profit": 1.1200,
        "proposed_stop_loss": 1.0950,
        "proposed_take_profit": 1.1200,
        "evidence_ref": "ai-proposal",
        "requested_by": "AI_AGENT",
    }
    response = client.post(
        "/execution-ledger/position-modification/prepare",
        json=payload,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_confirmed_position_close_resolves_pending_modification():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            await reconcile_open_position(
                session,
                portfolio_key="Exness-Demo:123:magic-91",
                request_id="position:91",
                broker_position_id="9100",
                broker_order_id="9101",
                broker_deal_id="9102",
                symbol="EURUSD",
                direction="BUY",
                risk_r=0.7,
                volatility=0.2,
                factors={},
                evidence_ref="snapshot-before-close",
            )
            await prepare_position_modification(
                session,
                portfolio_key="Exness-Demo:123:magic-91",
                event_id="modify:9100:1",
                broker_position_id="9100",
                symbol="EURUSD",
                direction="BUY",
                old_stop_loss=1.0900,
                old_take_profit=1.1200,
                proposed_stop_loss=1.0950,
                proposed_take_profit=1.1200,
                evidence_ref="intent",
            )
            await session.commit()

        async with factory() as session:
            assert await reconcile_closed_position(
                session,
                portfolio_key="Exness-Demo:123:magic-91",
                broker_position_id="9100",
                broker_deal_id="9103",
                evidence_ref="mt5-close:9103",
            )
            await session.commit()

        async with factory() as session:
            event = await session.scalar(
                select(ExecutionPositionModification).where(
                    ExecutionPositionModification.event_id == "modify:9100:1"
                )
            )
            assert event.status == "POSITION_CLOSED"
            assert event.resolution_evidence_ref == "mt5-close:9103"
    finally:
        await engine.dispose()



def test_general_bridge_key_cannot_mutate_reservations_without_mt5_capability(client):
    payload = {
        "portfolio_key": "account:test:magic:unauthorized",
        "request_id": "bridge-only-must-not-reserve",
        "signal_id": "bridge-only",
        "symbol": "EURUSD",
        "direction": "BUY",
        "risk_r": 0.1,
        "volatility": 0.1,
        "factors": {},
        "requested_by": "MT5_EA",
    }
    response = client.post(
        "/execution-ledger/reserve",
        json=payload,
        headers={
            "X-API-Key": "deliberately-invalid-bridge-key",
        },
    )
    assert response.status_code == 403
