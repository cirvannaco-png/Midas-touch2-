from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.execution_control import (
    reconcile_closed_position,
    reconcile_open_position,
    record_position_modification,
    reconcile_terminal_order,
    recover_expired_leases,
    reserve_execution,
    sync_pending_order,
    transition_execution,
    update_position_risk,
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


def test_canonical_bridge_api_key_takes_precedence_with_legacy_fallback(client, monkeypatch):
    from app.config import settings

    original = settings.BRIDGE_API_KEY
    try:
        settings.BRIDGE_API_KEY = "dedicated-bridge-key"
        accepted = client.get(
            "/execution-ledger/health",
            headers={"X-API-Key": "dedicated-bridge-key"},
        )
        assert accepted.status_code == 200, accepted.text

        legacy_rejected = client.get(
            "/execution-ledger/health",
            headers={"X-API-Key": settings.SECRET_KEY},
        )
        assert legacy_rejected.status_code == 401

        settings.BRIDGE_API_KEY = ""
        legacy_accepted = client.get(
            "/execution-ledger/health",
            headers={"X-API-Key": settings.SECRET_KEY},
        )
        assert legacy_accepted.status_code == 200, legacy_accepted.text
    finally:
        settings.BRIDGE_API_KEY = original


def test_execution_ledger_route_requires_api_key(client):
    payload = {
        "portfolio_key": "account:test:magic:test",
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
async def test_position_modification_reconciliation_is_idempotent_and_updates_reserved_risk():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            await reconcile_open_position(
                session,
                portfolio_key="DEMO:Exness:123:magic-77",
                request_id="position-modification-request",
                broker_position_id="9001",
                broker_order_id="8001",
                broker_deal_id="7001",
                symbol="XAUUSD",
                direction="BUY",
                risk_r=1.2,
                volatility=0.7,
                factors={"gold": 1.0},
                evidence_ref="mt5-position-snapshot:9001",
            )
            await session.commit()

        event = {
            "portfolio_key": "DEMO:Exness:123:magic-77",
            "broker_position_id": "9001",
            "symbol": "XAUUSD",
            "direction": "BUY",
            "modification_id": "mt5-posmod:9001:1",
            "old_stop_loss": 2300.0,
            "new_stop_loss": 2310.0,
            "old_take_profit": 2350.0,
            "new_take_profit": 2360.0,
            "risk_r": 0.4,
            "volatility": 0.5,
            "evidence_ref": "mt5-position-modification:9001:1",
        }
        async with factory() as session:
            assert await record_position_modification(session, **event)
            await session.commit()

        async with factory() as session:
            assert await record_position_modification(session, **event)
            await session.commit()
            row = await session.scalar(
                select(ExecutionLedger).where(
                    ExecutionLedger.portfolio_key == event["portfolio_key"],
                    ExecutionLedger.broker_position_id == "9001",
                )
            )
            assert row is not None
            history = row.result_json["position_modifications"]
            assert len(history) == 1
            assert history[0]["new_stop_loss"] == 2310.0
            reservation = await session.scalar(
                select(PortfolioReservation).where(
                    PortfolioReservation.portfolio_key == event["portfolio_key"],
                    PortfolioReservation.request_id == "position-modification-request",
                )
            )
            assert reservation is not None
            assert reservation.risk_r == 0.4
            assert reservation.factor_exposure == {"gold": 1.0}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_position_modification_rejects_stop_loosening_and_conflicting_retry():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            await reconcile_open_position(
                session,
                portfolio_key="DEMO:Exness:123:magic-77",
                request_id="position-modification-request",
                broker_position_id="9002",
                broker_order_id="8002",
                broker_deal_id="7002",
                symbol="XAUUSD",
                direction="BUY",
                risk_r=1.0,
                volatility=0.7,
                factors={},
                evidence_ref="mt5-position-snapshot:9002",
            )
            await session.commit()

        event = {
            "portfolio_key": "DEMO:Exness:123:magic-77",
            "broker_position_id": "9002",
            "symbol": "XAUUSD",
            "direction": "BUY",
            "modification_id": "mt5-posmod:9002:1",
            "old_stop_loss": 2300.0,
            "new_stop_loss": 2310.0,
            "old_take_profit": 2350.0,
            "new_take_profit": 2360.0,
            "risk_r": 0.4,
            "volatility": 0.5,
            "evidence_ref": "mt5-position-modification:9002:1",
        }
        async with factory() as session:
            assert await record_position_modification(session, **event)
            await session.commit()

        async with factory() as session:
            conflicting = dict(event, new_stop_loss=2315.0)
            with pytest.raises(ValueError, match="conflicting broker evidence"):
                await record_position_modification(session, **conflicting)
            await session.rollback()

        async with factory() as session:
            loosening = dict(
                event,
                modification_id="mt5-posmod:9002:2",
                old_stop_loss=2310.0,
                new_stop_loss=2305.0,
            )
            with pytest.raises(ValueError, match="cannot be loosened"):
                await record_position_modification(session, **loosening)
            await session.rollback()
    finally:
        await engine.dispose()
