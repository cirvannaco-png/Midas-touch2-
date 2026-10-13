"""Authenticated HTTP API for durable execution intent and reconciliation state.

These endpoints only persist admission/state. They do not place or retry broker orders.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.execution_control import (
    MAX_PORTFOLIO_HEAT_R,
    recover_expired_leases,
    reconcile_closed_position,
    reconcile_open_position,
    reconcile_terminal_order,
    reserve_execution,
    sync_pending_order,
    transition_execution,
    update_position_risk,
)
from app.routes import verify_api_key

router = APIRouter(prefix="/execution-ledger", tags=["execution-ledger"])


class ReserveRequest(BaseModel):
    portfolio_key: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    signal_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=32)
    direction: Literal["BUY", "SELL"]
    risk_r: float = Field(gt=0)
    volatility: float = Field(ge=0)
    factors: dict[str, float] = Field(default_factory=dict)
    # Callers cannot raise the global portfolio heat ceiling.
    max_heat_r: float = Field(default=MAX_PORTFOLIO_HEAT_R, gt=0, le=MAX_PORTFOLIO_HEAT_R)


class TransitionRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    state: Literal["CHECKED", "SENT", "ACKED", "FILLED", "REJECTED", "CANCELLED", "RECONCILED"]
    result: dict | None = None


@router.post("/reserve")
async def reserve(
    body: ReserveRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    try:
        reserved = await reserve_execution(
            session,
            request_id=body.request_id,
            signal_id=body.signal_id,
            symbol=body.symbol,
            direction=body.direction,
            risk_r=body.risk_r,
            volatility=body.volatility,
            factors=body.factors,
            max_heat_r=body.max_heat_r,
            portfolio_key=body.portfolio_key,
        )
        if not reserved:
            await session.rollback()
            raise HTTPException(409, "duplicate request or portfolio heat limit exceeded")
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(422, str(exc)) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "duplicate execution request") from exc
    return {
        "reserved": True,
        "portfolio_key": body.portfolio_key,
        "request_id": body.request_id,
        "state": "RESERVED",
    }


@router.post("/transition")
async def transition(
    body: TransitionRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    try:
        transitioned = await transition_execution(
            session,
            request_id=body.request_id,
            state=body.state,
            result=body.result,
        )
        if not transitioned:
            await session.rollback()
            raise HTTPException(409, "unknown request, conflicting retry, or illegal state transition")
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "execution state conflict") from exc
    return {"transitioned": True, "request_id": body.request_id, "state": body.state}


@router.post("/recover-expired")
async def recover_expired(
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    count = await recover_expired_leases(session)
    await session.commit()
    return {"recovery_required": count}



class BrokerPositionSyncRequest(BaseModel):
    portfolio_key: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    broker_position_id: str = Field(min_length=1, max_length=100)
    broker_order_id: str | None = Field(default=None, max_length=100)
    broker_deal_id: str | None = Field(default=None, max_length=100)
    symbol: str = Field(min_length=1, max_length=32)
    direction: Literal["BUY", "SELL"]
    risk_r: float = Field(gt=0)
    volatility: float = Field(ge=0)
    factors: dict[str, float] = Field(default_factory=dict)
    evidence_ref: str = Field(min_length=1, max_length=256)


class PositionRiskUpdateRequest(BaseModel):
    portfolio_key: str = Field(min_length=1, max_length=128)
    broker_position_id: str = Field(min_length=1, max_length=100)
    direction: Literal["BUY", "SELL"]
    risk_r: float = Field(gt=0)
    volatility: float = Field(ge=0)
    factors: dict[str, float] = Field(default_factory=dict)
    evidence_ref: str = Field(min_length=1, max_length=256)


class ClosedPositionRequest(BaseModel):
    portfolio_key: str = Field(min_length=1, max_length=128)
    broker_position_id: str = Field(min_length=1, max_length=100)
    broker_deal_id: str = Field(min_length=1, max_length=100)
    evidence_ref: str = Field(min_length=1, max_length=256)


class PendingOrderSyncRequest(BaseModel):
    portfolio_key: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    broker_order_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=32)
    direction: Literal["BUY", "SELL"]
    risk_r: float = Field(gt=0)
    volatility: float = Field(ge=0)
    factors: dict[str, float] = Field(default_factory=dict)
    evidence_ref: str = Field(min_length=1, max_length=256)


class TerminalOrderRequest(BaseModel):
    portfolio_key: str = Field(min_length=1, max_length=128)
    broker_order_id: str = Field(min_length=1, max_length=100)
    terminal_state: Literal["CANCELLED", "REJECTED"]
    evidence_ref: str = Field(min_length=1, max_length=256)


@router.post("/sync-position")
async def sync_position(
    body: BrokerPositionSyncRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    try:
        request_id, heat_r, over_limit = await reconcile_open_position(
            session,
            portfolio_key=body.portfolio_key,
            request_id=body.request_id,
            broker_position_id=body.broker_position_id,
            broker_order_id=body.broker_order_id,
            broker_deal_id=body.broker_deal_id,
            symbol=body.symbol,
            direction=body.direction,
            risk_r=body.risk_r,
            volatility=body.volatility,
            factors=body.factors,
            evidence_ref=body.evidence_ref,
        )
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="broker position reconciliation conflict") from exc
    return {
        "reconciled": True,
        "request_id": request_id,
        "portfolio_key": body.portfolio_key,
        "portfolio_heat_r": heat_r,
        "over_heat_limit": over_limit,
    }


@router.post("/position-risk")
async def position_risk_update(
    body: PositionRiskUpdateRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    try:
        updated = await update_position_risk(
            session,
            portfolio_key=body.portfolio_key,
            broker_position_id=body.broker_position_id,
            direction=body.direction,
            risk_r=body.risk_r,
            volatility=body.volatility,
            factors=body.factors,
            evidence_ref=body.evidence_ref,
        )
        if not updated:
            await session.rollback()
            raise HTTPException(status_code=404, detail="broker position is not registered in the execution ledger")
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"updated": True, "broker_position_id": body.broker_position_id}


@router.post("/position-closed")
async def position_closed(
    body: ClosedPositionRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    try:
        reconciled = await reconcile_closed_position(
            session,
            portfolio_key=body.portfolio_key,
            broker_position_id=body.broker_position_id,
            broker_deal_id=body.broker_deal_id,
            evidence_ref=body.evidence_ref,
        )
        if not reconciled:
            await session.rollback()
            raise HTTPException(status_code=404, detail="broker position is not registered; reservation was not released")
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"reconciled": True, "broker_position_id": body.broker_position_id, "state": "RECONCILED"}


@router.post("/sync-pending-order")
async def sync_live_pending_order(
    body: PendingOrderSyncRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    try:
        request_id, heat_r, over_limit = await sync_pending_order(
            session,
            portfolio_key=body.portfolio_key,
            request_id=body.request_id,
            broker_order_id=body.broker_order_id,
            symbol=body.symbol,
            direction=body.direction,
            risk_r=body.risk_r,
            volatility=body.volatility,
            factors=body.factors,
            evidence_ref=body.evidence_ref,
        )
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="pending-order reconciliation conflict") from exc
    return {
        "reconciled": True,
        "request_id": request_id,
        "portfolio_heat_r": heat_r,
        "over_heat_limit": over_limit,
    }


@router.post("/order-terminal")
async def order_terminal(
    body: TerminalOrderRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    try:
        terminal = await reconcile_terminal_order(
            session,
            portfolio_key=body.portfolio_key,
            broker_order_id=body.broker_order_id,
            terminal_state=body.terminal_state,
            evidence_ref=body.evidence_ref,
        )
        if not terminal:
            await session.rollback()
            raise HTTPException(status_code=409, detail="order not found or already filled; reservation retained")
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"reconciled": True, "broker_order_id": body.broker_order_id, "state": body.terminal_state}
