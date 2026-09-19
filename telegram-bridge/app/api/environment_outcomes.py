"""Outcome ingestion boundary for Environment -> Strategy -> Outcome memory.

The legacy /outcome route remains registered for older EA payloads. This
router is mounted first so upgraded EA payloads retain the richer strategy and
environment snapshot without changing the legacy contract.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models import SignalOutcome
from app.ratelimit import enforce_rate_limit

router = APIRouter()


class EnvironmentOutcomeRequest(BaseModel):
    signal_id: str = Field(..., min_length=1, max_length=100)
    symbol: str = Field(..., min_length=1, max_length=20)
    direction: str = Field(..., pattern=r"^(BUY|SELL)$")
    outcome: str = Field(..., pattern=r"^(win|loss|scratch|no_fill|ambiguous)$")
    realized_r: float | None = None
    mfe_r: float | None = None
    mae_r: float | None = None
    bars_held: int | None = Field(default=None, ge=0)
    bars_to_fill: int | None = Field(default=None, ge=0)
    filled: bool = False
    regime: str | None = Field(default=None, max_length=32)
    session: str | None = Field(default=None, max_length=32)
    sweep_grade: str | None = Field(default=None, max_length=16)
    htf_ob_aligned: bool | None = None
    weight_version: str | None = Field(default=None, max_length=64)
    confidence_at_signal: float | None = None
    confidence_decayed: float | None = None
    decay_bars: int | None = Field(default=None, ge=0)
    strategy: str | None = Field(default=None, max_length=64)
    exit_reason: str | None = Field(default=None, max_length=64)
    environment_key: str | None = Field(default=None, max_length=512)
    environment: dict | None = None


class EnvironmentOutcomeResponse(BaseModel):
    status: str
    signal_id: str
    upserted: bool = False


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    if not secrets.compare_digest(x_api_key, settings.SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@router.post("/outcome", response_model=EnvironmentOutcomeResponse)
async def receive_environment_outcome(
    payload: EnvironmentOutcomeRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
    _rate: None = Depends(enforce_rate_limit),
):
    existing = await session.scalar(select(SignalOutcome).where(SignalOutcome.signal_id == payload.signal_id))
    upserted = existing is not None
    row = existing or SignalOutcome(signal_id=payload.signal_id)
    row.symbol = payload.symbol
    row.direction = payload.direction
    row.outcome = payload.outcome
    row.realized_r = payload.realized_r
    row.mfe_r = payload.mfe_r
    row.mae_r = payload.mae_r
    row.bars_held = payload.bars_held
    row.bars_to_fill = payload.bars_to_fill
    row.filled = payload.filled
    row.regime = payload.regime
    row.session = payload.session
    row.sweep_grade = payload.sweep_grade
    row.htf_ob_aligned = payload.htf_ob_aligned
    row.weight_version = payload.weight_version
    row.confidence_at_signal = payload.confidence_at_signal
    row.confidence_decayed = payload.confidence_decayed
    row.decay_bars = payload.decay_bars
    row.strategy = payload.strategy
    row.exit_reason = payload.exit_reason
    row.environment_key = payload.environment_key
    row.environment = payload.environment
    if not upserted:
        session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(select(SignalOutcome).where(SignalOutcome.signal_id == payload.signal_id))
        if existing is None:
            raise
        existing.symbol = payload.symbol
        existing.direction = payload.direction
        existing.outcome = payload.outcome
        existing.realized_r = payload.realized_r
        existing.mfe_r = payload.mfe_r
        existing.mae_r = payload.mae_r
        existing.bars_held = payload.bars_held
        existing.bars_to_fill = payload.bars_to_fill
        existing.filled = payload.filled
        existing.regime = payload.regime
        existing.session = payload.session
        existing.sweep_grade = payload.sweep_grade
        existing.htf_ob_aligned = payload.htf_ob_aligned
        existing.weight_version = payload.weight_version
        existing.confidence_at_signal = payload.confidence_at_signal
        existing.confidence_decayed = payload.confidence_decayed
        existing.decay_bars = payload.decay_bars
        existing.strategy = payload.strategy
        existing.exit_reason = payload.exit_reason
        existing.environment_key = payload.environment_key
        existing.environment = payload.environment
        await session.commit()
        upserted = True
    return EnvironmentOutcomeResponse(status="ok", signal_id=payload.signal_id, upserted=upserted)
