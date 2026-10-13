"""Authenticated experiment/observation/validation API restored from Medis Touch.

These routes collect immutable research provenance. They do not promote or activate
a configuration; Midas's configuration registry and evaluation gates remain authoritative.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import ExperimentObservation, ResearchExperiment, ValidationRun
from app.routes import verify_api_key

router = APIRouter(prefix="/research", tags=["research"])


def canonical_hash(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _require_aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return value


class ExperimentCreate(BaseModel):
    experiment_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    code_sha: str = Field(min_length=7, max_length=64)
    config: dict
    data_snapshot: str = Field(min_length=1, max_length=128)
    train_start: datetime
    train_end: datetime
    oos_start: datetime
    oos_end: datetime
    walk_forward_id: str | None = Field(default=None, max_length=128)

    @field_validator("train_start", "train_end", "oos_start", "oos_end")
    @classmethod
    def timestamps_must_be_aware(cls, value, info):
        return _require_aware(value, info.field_name)

    def validate_chronology(self) -> None:
        if (
            self.train_start >= self.train_end
            or self.oos_start >= self.oos_end
            or self.train_end > self.oos_start
        ):
            raise ValueError("training and out-of-sample windows must be ordered and non-overlapping")


class ObservationCreate(BaseModel):
    signal_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=32)
    timestamp: datetime
    payload: dict

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_aware(cls, value):
        return _require_aware(value, "timestamp")


class ValidationRunCreate(BaseModel):
    validation_type: str = Field(min_length=1, max_length=64)
    window: dict
    metrics: dict
    passed: bool


@router.post("/experiments")
async def create_experiment(
    body: ExperimentCreate,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    try:
        body.validate_chronology()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing = await session.scalar(
        select(ResearchExperiment).where(ResearchExperiment.experiment_id == body.experiment_id)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="experiment already exists")

    config_hash = canonical_hash(body.config)
    row = ResearchExperiment(
        experiment_id=body.experiment_id,
        name=body.name,
        code_sha=body.code_sha,
        config_hash=config_hash,
        data_snapshot=body.data_snapshot,
        created_at=datetime.now(timezone.utc),
        train_start=body.train_start,
        train_end=body.train_end,
        oos_start=body.oos_start,
        oos_end=body.oos_end,
        walk_forward_id=body.walk_forward_id,
        holdout_locked=False,
    )
    session.add(row)
    await session.commit()
    return {
        "experiment_id": row.experiment_id,
        "config_hash": row.config_hash,
        "holdout_locked": row.holdout_locked,
    }


@router.post("/experiments/{experiment_id}/observations")
async def ingest_observation(
    experiment_id: str,
    body: ObservationCreate,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    experiment = await session.scalar(
        select(ResearchExperiment).where(ResearchExperiment.experiment_id == experiment_id)
    )
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")

    fingerprint = canonical_hash(
        {
            "experiment_id": experiment_id,
            "signal_id": body.signal_id,
            "symbol": body.symbol,
            "timestamp": body.timestamp.isoformat(),
            "payload": body.payload,
        }
    )
    existing = await session.scalar(
        select(ExperimentObservation).where(ExperimentObservation.fingerprint == fingerprint)
    )
    if existing is not None:
        return {"stored": True, "duplicate": True, "fingerprint": fingerprint}

    session.add(
        ExperimentObservation(
            experiment_id=experiment_id,
            signal_id=body.signal_id,
            symbol=body.symbol,
            timestamp=body.timestamp,
            payload=body.payload,
            fingerprint=fingerprint,
        )
    )
    await session.commit()
    return {"stored": True, "duplicate": False, "fingerprint": fingerprint}


@router.post("/experiments/{experiment_id}/holdout-lock")
async def lock_holdout(
    experiment_id: str,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    experiment = await session.scalar(
        select(ResearchExperiment).where(ResearchExperiment.experiment_id == experiment_id).with_for_update()
    )
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    if experiment.holdout_locked:
        return {"experiment_id": experiment_id, "holdout_locked": True, "already_locked": True}

    now = datetime.now(timezone.utc)
    oos_end = experiment.oos_end
    if oos_end.tzinfo is None:
        oos_end = oos_end.replace(tzinfo=timezone.utc)
    if now < oos_end:
        raise HTTPException(status_code=409, detail="out-of-sample window has not ended")

    experiment.holdout_locked = True
    session.add(
        ValidationRun(
            experiment_id=experiment_id,
            validation_type="holdout_lock",
            window_json={"oos_start": experiment.oos_start.isoformat(), "oos_end": experiment.oos_end.isoformat()},
            metrics_json={"locked_at": now.isoformat(), "config_hash": experiment.config_hash},
            passed=True,
            created_at=now,
        )
    )
    await session.commit()
    return {"experiment_id": experiment_id, "holdout_locked": True, "already_locked": False}


@router.post("/experiments/{experiment_id}/validation-runs")
async def record_validation_run(
    experiment_id: str,
    body: ValidationRunCreate,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    experiment = await session.scalar(
        select(ResearchExperiment).where(ResearchExperiment.experiment_id == experiment_id)
    )
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    row = ValidationRun(
        experiment_id=experiment_id,
        validation_type=body.validation_type,
        window_json=body.window,
        metrics_json=body.metrics,
        passed=body.passed,
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.flush()
    run_id = row.id
    await session.commit()
    return {
        "validation_run_id": run_id,
        "experiment_id": experiment_id,
        "passed": body.passed,
        "promoted": False,
    }
