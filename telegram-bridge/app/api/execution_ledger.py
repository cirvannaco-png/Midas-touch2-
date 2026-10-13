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
    reserve_execution,
    transition_execution,
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
