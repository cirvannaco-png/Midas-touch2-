"""HTTP transport for the fail-closed EA configuration protocol."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config_registry import ConfigurationIdentity
from app.config_registry_model import ConfigurationRegistry
from app.config_sync_contract import activation_decision, envelope_from_mapping, validate_envelope
from app.config_sync_state_model import ConfigSyncState
from app.database import get_session
from app.routes import verify_api_key

router = APIRouter()


class ConfigEnvelopeResponse(BaseModel):
    config_hash: str
    strategy: str
    instrument: str
    timeframe: str
    parameters: dict
    data_version: str
    optimizer_version: str
    lifecycle_status: str
    version: int
    active: bool


class ConfigAckRequest(BaseModel):
    config_hash: str = Field(..., min_length=64, max_length=64)
    strategy: str = Field(..., min_length=1, max_length=64)
    timeframe: str = Field(..., min_length=1, max_length=16)
    version: int = Field(..., ge=1)


class ConfigAckResponse(BaseModel):
    action: Literal["ACTIVATE", "HOLD"]
    config_hash: str
    state: str
    reasons: list[str]


class RuntimeReportRequest(BaseModel):
    config_hash: str = Field(..., min_length=64, max_length=64)
    healthy: bool


class RuntimeReportResponse(BaseModel):
    action: Literal["KEEP_ACTIVE", "ROLLBACK", "DEFENSIVE", "HALT"]
    active_config_hash: str | None
    state: str
    reasons: list[str]


async def _get_state(session: AsyncSession, symbol: str) -> ConfigSyncState:
    state = await session.scalar(select(ConfigSyncState).where(ConfigSyncState.symbol == symbol))
    if state is None:
        state = ConfigSyncState(symbol=symbol, state="HOLD")
        session.add(state)
        await session.flush()
    return state


def _verify_registry_hash(registry: ConfigurationRegistry) -> None:
    """Fail closed if persisted identity fields no longer reproduce its hash."""
    expected = ConfigurationIdentity(
        strategy=registry.strategy,
        instrument=registry.instrument,
        timeframe=registry.timeframe,
        parameters=registry.parameters or {},
        data_version=registry.data_version,
        optimizer_version=registry.optimizer_version,
    ).config_hash
    if expected != registry.config_hash:
        raise HTTPException(status_code=500, detail="Registered configuration identity/hash mismatch")


@router.get("/config/{symbol}", response_model=ConfigEnvelopeResponse)
async def get_approved_config(
    symbol: str,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    """Return the latest CHAMPION immutable configuration for this symbol."""
    registry = await session.scalar(
        select(ConfigurationRegistry)
        .where(
            ConfigurationRegistry.instrument == symbol,
            ConfigurationRegistry.lifecycle_status == "CHAMPION",
        )
        .order_by(ConfigurationRegistry.created_at.desc())
        .limit(1)
    )
    if registry is None:
        raise HTTPException(status_code=404, detail="No champion configuration is available")
    _verify_registry_hash(registry)

    state = await _get_state(session, symbol)
    state.last_seen_at = datetime.now(timezone.utc)
    await session.commit()

    return ConfigEnvelopeResponse(
        config_hash=registry.config_hash,
        strategy=registry.strategy,
        instrument=registry.instrument,
        timeframe=registry.timeframe,
        parameters=dict(registry.parameters or {}),
        data_version=registry.data_version,
        optimizer_version=registry.optimizer_version,
        lifecycle_status=registry.lifecycle_status,
        version=1,
        active=state.active_config_hash == registry.config_hash,
    )


@router.post("/config/{symbol}/ack", response_model=ConfigAckResponse)
async def acknowledge_config(
    symbol: str,
    payload: ConfigAckRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    """Validate the EA's exact hash/metadata and persist activation."""
    registry = await session.scalar(
        select(ConfigurationRegistry).where(
            ConfigurationRegistry.config_hash == payload.config_hash,
            ConfigurationRegistry.instrument == symbol,
        )
    )
    if registry is None:
        raise HTTPException(status_code=404, detail="Configuration hash is not registered for this symbol")
    _verify_registry_hash(registry)

    envelope = envelope_from_mapping({
        "config_hash": registry.config_hash,
        "strategy": registry.strategy,
        "instrument": registry.instrument,
        "timeframe": registry.timeframe,
        "parameters": registry.parameters or {},
        "data_version": registry.data_version,
        "optimizer_version": registry.optimizer_version,
        "lifecycle_status": registry.lifecycle_status,
        "version": payload.version,
    })
    validation = validate_envelope(
        envelope,
        expected_symbol=symbol,
        expected_timeframe=payload.timeframe,
        expected_strategy=payload.strategy,
    )
    decision = activation_decision(
        validation,
        acknowledged_hash=payload.config_hash,
        expected_hash=registry.config_hash,
    )

    state = await _get_state(session, symbol)
    state.last_ack_at = datetime.now(timezone.utc)
    state.last_error = None if decision.action == "ACTIVATE" else "; ".join(decision.reasons)
    if decision.action == "ACTIVATE":
        state.acknowledged_config_hash = payload.config_hash
        state.active_config_hash = payload.config_hash
        state.state = "ACTIVE"
    else:
        state.state = "HOLD"
    await session.commit()

    return ConfigAckResponse(
        action=decision.action,
        config_hash=payload.config_hash,
        state=state.state,
        reasons=list(decision.reasons),
    )


@router.post("/config/{symbol}/runtime", response_model=RuntimeReportResponse)
async def report_runtime(
    symbol: str,
    payload: RuntimeReportRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    """Record runtime health and fail closed to the current CHAMPION."""
    state = await _get_state(session, symbol)
    champion = await session.scalar(
        select(ConfigurationRegistry)
        .where(
            ConfigurationRegistry.instrument == symbol,
            ConfigurationRegistry.lifecycle_status == "CHAMPION",
        )
        .order_by(ConfigurationRegistry.created_at.desc())
        .limit(1)
    )
    champion_hash = ""
    if champion is not None:
        _verify_registry_hash(champion)
        champion_hash = champion.config_hash

    from app.config_sync_contract import rollback_decision

    decision = rollback_decision(
        active_hash=payload.config_hash,
        champion_hash=champion_hash,
        runtime_healthy=payload.healthy,
    )
    state.last_seen_at = datetime.now(timezone.utc)
    if decision.action == "KEEP_ACTIVE":
        state.active_config_hash = payload.config_hash
        state.state = "ACTIVE"
        state.last_error = None
    elif decision.action == "ROLLBACK":
        state.active_config_hash = champion_hash
        state.state = "ROLLBACK"
        state.last_error = "; ".join(decision.reasons)
    elif decision.action == "DEFENSIVE":
        state.state = "DEFENSIVE"
        state.last_error = "; ".join(decision.reasons)
    else:
        state.state = "HALT"
        state.last_error = "; ".join(decision.reasons)
    await session.commit()

    return RuntimeReportResponse(
        action=decision.action,
        active_config_hash=state.active_config_hash,
        state=state.state,
        reasons=list(decision.reasons),
    )
