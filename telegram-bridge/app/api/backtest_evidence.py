"""Authenticated ingestion of immutable MT5 Strategy Tester evidence.

This endpoint stores backtest results as research evidence. It does not activate
an EA configuration; approval and exact-hash EA acknowledgement remain separate.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from math import sqrt, tanh
from statistics import mean, pstdev
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config_evaluation_model import ConfigurationEvaluation
from app.config_registry import ConfigurationIdentity
from app.config_registry_model import ConfigurationRegistry
from app.database import get_session
from app.routes import verify_api_key

router = APIRouter()

SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
COMMIT_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
MIN_OOS_TRADES = 30
MIN_FOLD_TRAIN_TRADES = 20
MIN_FOLD_VALIDATION_TRADES = 10
MIN_WALK_FORWARD_FOLDS = 3
MIN_PAIRED_SCENARIOS = 30


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class TesterProvenance(StrictModel):
    source: Literal["MT5_STRATEGY_TESTER"]
    run_id: str = Field(min_length=1, max_length=160)
    report_sha256: str = Field(min_length=64, max_length=64)
    outcome_csv_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    dataset_sha256: str = Field(min_length=64, max_length=64)
    ea_source_commit: str = Field(min_length=40, max_length=64)
    ea_build: str = Field(min_length=1, max_length=120)
    terminal_build: str = Field(min_length=1, max_length=120)
    data_vendor: str = Field(min_length=1, max_length=120)
    period_start: datetime
    period_end: datetime
    locked_oos_start: datetime
    locked_oos_end: datetime
    generated_at: datetime
    spread_model: str = Field(min_length=1, max_length=120)
    spread_points: float = Field(ge=0)
    commission_per_lot: float = Field(ge=0)
    slippage_points: float = Field(ge=0)
    fill_policy: str = Field(min_length=1, max_length=80)

    @field_validator("report_sha256", "outcome_csv_sha256", "dataset_sha256")
    @classmethod
    def _validate_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not SHA256_RE.fullmatch(value):
            raise ValueError("must be a 64-character SHA-256 hex digest")
        return value.lower()

    @field_validator("ea_source_commit")
    @classmethod
    def _validate_commit(cls, value: str) -> str:
        if not COMMIT_RE.fullmatch(value):
            raise ValueError("ea_source_commit must be a 40- or 64-character Git commit hash")
        return value.lower()

    @field_validator("period_start", "period_end", "locked_oos_start", "locked_oos_end", "generated_at")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _validate_period(self):
        if self.period_start >= self.period_end:
            raise ValueError("period_start must be earlier than period_end")
        if not self.period_start <= self.locked_oos_start < self.locked_oos_end <= self.period_end:
            raise ValueError("locked OOS period must be inside the overall backtest period")
        return self


class TesterTrade(StrictModel):
    """One resolved trade or no-fill observation emitted by a Tester exporter."""

    trade_id: str = Field(min_length=1, max_length=160)
    timestamp: datetime
    partition: Literal["train", "validation", "locked_oos"]
    fold_id: int | None = Field(default=None, ge=1, le=1000)
    outcome: Literal["win", "loss", "scratch", "no_fill", "ambiguous"]
    realized_r: float | None = Field(default=None, allow_inf_nan=False)
    filled: bool
    commission_cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    spread_cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    slippage_cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("timestamp")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("trade timestamps must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _validate_trade(self):
        if self.partition == "locked_oos" and self.fold_id is not None:
            raise ValueError("locked_oos rows must not have a fold_id")
        if self.partition != "locked_oos" and self.fold_id is None:
            raise ValueError("train/validation rows must include a fold_id")
        if self.outcome in {"win", "loss", "scratch"}:
            if self.realized_r is None:
                raise ValueError("resolved trades require realized_r")
            if self.outcome == "win" and self.realized_r <= 0:
                raise ValueError("win outcome requires positive net realized_r")
            if self.outcome == "loss" and self.realized_r >= 0:
                raise ValueError("loss outcome requires negative net realized_r")
            if self.outcome == "scratch" and abs(self.realized_r) > 1e-6:
                raise ValueError("scratch outcome requires realized_r approximately zero")
            if not self.filled:
                raise ValueError("resolved win/loss/scratch outcomes must be filled")
        elif self.realized_r is not None:
            raise ValueError("no_fill/ambiguous outcomes must use null realized_r")
        if self.outcome == "no_fill" and self.filled:
            raise ValueError("no_fill outcome cannot be marked filled")
        if self.filled and any(
            value is None
            for value in (self.commission_cost, self.spread_cost, self.slippage_cost)
        ):
            raise ValueError("filled rows require commission, spread, and slippage costs")
        return self


class NeighborTrade(StrictModel):
    trade_id: str = Field(min_length=1, max_length=160)
    timestamp: datetime
    outcome: Literal["win", "loss", "scratch"]
    realized_r: float = Field(allow_inf_nan=False)

    @field_validator("timestamp")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("neighbor trade timestamps must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _validate_sign(self):
        if self.outcome == "win" and self.realized_r <= 0:
            raise ValueError("neighbor win requires positive realized_r")
        if self.outcome == "loss" and self.realized_r >= 0:
            raise ValueError("neighbor loss requires negative realized_r")
        if self.outcome == "scratch" and abs(self.realized_r) > 1e-6:
            raise ValueError("neighbor scratch requires realized_r approximately zero")
        return self


class NeighborRun(StrictModel):
    parameters: dict[str, Any]
    report_sha256: str = Field(min_length=64, max_length=64)
    outcome_csv_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    dataset_sha256: str = Field(min_length=64, max_length=64)
    ea_source_commit: str = Field(min_length=40, max_length=64)
    ea_build: str = Field(min_length=1, max_length=120)
    terminal_build: str = Field(min_length=1, max_length=120)
    period_start: datetime
    period_end: datetime
    trades: list[NeighborTrade] = Field(min_length=1, max_length=15000)

    @field_validator("report_sha256", "outcome_csv_sha256", "dataset_sha256")
    @classmethod
    def _validate_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not SHA256_RE.fullmatch(value):
            raise ValueError("must be a 64-character SHA-256 hex digest")
        return value.lower()

    @field_validator("ea_source_commit")
    @classmethod
    def _validate_commit(cls, value: str) -> str:
        if not COMMIT_RE.fullmatch(value):
            raise ValueError("ea_source_commit must be a 40- or 64-character Git commit hash")
        return value.lower()

    @field_validator("period_start", "period_end")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("neighbor period timestamps must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _require_parameters_and_period(self):
        if not self.parameters:
            raise ValueError("neighbor parameters must not be empty")
        if self.period_start >= self.period_end:
            raise ValueError("neighbor period_start must be earlier than period_end")
        return self


class FeatureImportanceEvidence(StrictModel):
    feature: str = Field(min_length=1, max_length=160)
    delta_metric: float = Field(allow_inf_nan=False)


class ClusteredMDAEvidence(StrictModel):
    group_name: str = Field(min_length=1, max_length=160)
    features: list[str] = Field(min_length=1, max_length=100)
    delta_metric: float = Field(allow_inf_nan=False)


class CounterfactualEvidence(StrictModel):
    scenario_id: str = Field(min_length=1, max_length=160)
    baseline_realized_r: float = Field(allow_inf_nan=False)
    candidate_realized_r: float = Field(allow_inf_nan=False)


class ScaleOutEvidence(StrictModel):
    scenario_id: str = Field(min_length=1, max_length=160)
    full_exit_realized_r: float = Field(allow_inf_nan=False)
    scale_out_realized_r: float = Field(allow_inf_nan=False)


class BacktestEvidenceRequest(StrictModel):
    strategy: str = Field(min_length=1, max_length=64)
    instrument: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(min_length=1, max_length=16)
    parameters: dict[str, Any]
    data_version: str = Field(min_length=1, max_length=160)
    optimizer_version: str = Field(min_length=1, max_length=120)
    claimed_config_hash: str | None = Field(default=None, min_length=64, max_length=64)
    change_scope: Literal["ENTRY", "EXIT", "BOTH"] = "ENTRY"
    provenance: TesterProvenance
    trades: list[TesterTrade] = Field(min_length=1, max_length=30000)
    parameter_neighbors: list[NeighborRun] = Field(default_factory=list, max_length=50)
    feature_importance: list[FeatureImportanceEvidence] = Field(default_factory=list, max_length=500)
    clustered_mda: list[ClusteredMDAEvidence] = Field(default_factory=list, max_length=200)
    counterfactual: list[CounterfactualEvidence] = Field(default_factory=list, max_length=30000)
    paired_test_p_value: float | None = Field(default=None, gt=0, le=1, allow_inf_nan=False)
    scale_out: list[ScaleOutEvidence] = Field(default_factory=list, max_length=30000)

    @field_validator("claimed_config_hash")
    @classmethod
    def _validate_claimed_hash(cls, value: str | None) -> str | None:
        if value is not None and not SHA256_RE.fullmatch(value):
            raise ValueError("claimed_config_hash must be a SHA-256 hex digest")
        return value.lower() if value else value

    @model_validator(mode="after")
    def _validate_payload(self):
        if not self.parameters:
            raise ValueError("parameters must not be empty")
        if self.provenance.period_start >= self.provenance.period_end:
            raise ValueError("invalid backtest period")
        for trade in self.trades:
            if not self.provenance.period_start <= trade.timestamp <= self.provenance.period_end:
                raise ValueError(f"trade {trade.trade_id} is outside the declared backtest period")
            if trade.partition == "locked_oos" and not (
                self.provenance.locked_oos_start <= trade.timestamp < self.provenance.locked_oos_end
            ):
                raise ValueError(f"locked_oos trade {trade.trade_id} is outside the locked OOS window")
            if trade.partition != "locked_oos" and trade.timestamp >= self.provenance.locked_oos_start:
                raise ValueError(f"train/validation trade {trade.trade_id} overlaps the locked OOS window")
        if len(self.counterfactual) > 0:
            ids = [row.scenario_id for row in self.counterfactual]
            if len(ids) != len(set(ids)):
                raise ValueError("counterfactual scenario_id values must be unique")
        if len(self.scale_out) > 0:
            ids = [row.scenario_id for row in self.scale_out]
            if len(ids) != len(set(ids)):
                raise ValueError("scale_out scenario_id values must be unique")
        return self


def _resolved(rows: list[Any]) -> list[Any]:
    return [row for row in rows if row.outcome in {"win", "loss", "scratch"}]


def _wilson(wins: int, n: int) -> tuple[float, float] | None:
    if n <= 0:
        return None
    z = 1.959963984540054
    p = wins / n
    den = 1 + (z * z / n)
    center = (p + z * z / (2 * n)) / den
    half = (z / den) * sqrt((p * (1 - p) / n) + (z * z / (4 * n * n)))
    return max(0.0, center - half), min(1.0, center + half)


def _summarize(rows: list[Any]) -> dict[str, Any]:
    done = _resolved(rows)
    values = [float(row.realized_r) for row in done if row.realized_r is not None]
    wins = sum(row.outcome == "win" for row in done)
    gross_profit = sum(v for v in values if v > 0)
    gross_loss = -sum(v for v in values if v < 0)
    profit_factor = (
        gross_profit / gross_loss if gross_loss > 0
        else (1000.0 if gross_profit > 0 else 0.0)
    )
    cumulative = peak = max_drawdown = 0.0
    for row in sorted(done, key=lambda item: item.timestamp):
        cumulative += float(row.realized_r)
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)
    return {
        "observations": len(rows),
        "resolved_trades": len(done),
        "no_fill_count": sum(row.outcome == "no_fill" for row in rows),
        "ambiguous_count": sum(row.outcome == "ambiguous" for row in rows),
        "wins": wins,
        "losses": sum(row.outcome == "loss" for row in done),
        "scratches": sum(row.outcome == "scratch" for row in done),
        "win_rate": wins / len(done) if done else None,
        "expectancy_r": mean(values) if values else None,
        "profit_factor": round(profit_factor, 8),
        "max_drawdown_r": round(max_drawdown, 8),
        "gross_profit_r": round(gross_profit, 8),
        "gross_loss_r": round(gross_loss, 8),
        "wilson_win_rate_ci": list(_wilson(wins, len(done))) if done else None,
        "commission_cost_total": round(sum(float(getattr(r, "commission_cost", 0) or 0) for r in rows), 8),
        "spread_cost_total": round(sum(float(getattr(r, "spread_cost", 0) or 0) for r in rows), 8),
        "slippage_cost_total": round(sum(float(getattr(r, "slippage_cost", 0) or 0) for r in rows), 8),
    }


def _fold_verdict(train_rows: list[Any], validation_rows: list[Any]) -> str:
    train = _resolved(train_rows)
    validation = _resolved(validation_rows)
    if len(train) < MIN_FOLD_TRAIN_TRADES or len(validation) < MIN_FOLD_VALIDATION_TRADES:
        return "insufficient_data"
    train_ci = _wilson(sum(row.outcome == "win" for row in train), len(train))
    validation_ci = _wilson(sum(row.outcome == "win" for row in validation), len(validation))
    if train_ci is None or validation_ci is None:
        return "insufficient_data"
    overlap = train_ci[0] <= validation_ci[1] and validation_ci[0] <= train_ci[1]
    return "consistent" if overlap else "diverged"


def _objective_components(oos: dict, fold_verdicts: list[str], parameter_stability: float) -> dict[str, float]:
    expectancy = float(oos.get("expectancy_r") or 0.0)
    values = [float(v) for v in oos.get("_values", [])]
    dispersion = pstdev(values) if len(values) > 1 else max(abs(expectancy), 0.25)
    risk_adjusted = 0.5 + 0.5 * tanh(expectancy / max(dispersion, 0.25))
    expectancy_score = 0.5 + 0.5 * tanh(expectancy)
    pf = min(float(oos.get("profit_factor") or 0.0), 20.0)
    pf_score = pf / (1.0 + pf)
    drawdown_score = 1.0 / (1.0 + max(float(oos.get("max_drawdown_r") or 0.0), 0.0))
    fold_score = (
        sum(verdict == "consistent" for verdict in fold_verdicts) / len(fold_verdicts)
        if fold_verdicts else 0.0
    )
    components = {
        "risk_adjusted_return": risk_adjusted,
        "expectancy": expectancy_score,
        "profit_factor": pf_score,
        "drawdown_control": drawdown_score,
        "out_of_sample_stability": fold_score,
        "parameter_stability": parameter_stability,
    }
    return {key: max(0.0, min(1.0, value)) for key, value in components.items()}


def _objective_score(components: dict[str, float]) -> float:
    weights = {
        "risk_adjusted_return": 0.30,
        "expectancy": 0.20,
        "profit_factor": 0.15,
        "drawdown_control": 0.15,
        "out_of_sample_stability": 0.10,
        "parameter_stability": 0.10,
    }
    return round(sum(weights[name] * components[name] for name in weights), 8)


def _is_parameter_neighbor(
    baseline: dict[str, Any], candidate: dict[str, Any], *, max_relative_step: float = 0.25
) -> bool:
    """Reject an unrelated configuration masquerading as a local plateau neighbor."""
    if set(baseline) != set(candidate):
        return False
    changed = False
    for key, base_value in baseline.items():
        candidate_value = candidate[key]
        if base_value == candidate_value:
            continue
        changed = True
        if isinstance(base_value, bool) or isinstance(candidate_value, bool):
            if not (isinstance(base_value, bool) and isinstance(candidate_value, bool)):
                return False
            continue
        if isinstance(base_value, (int, float)) and isinstance(candidate_value, (int, float)):
            scale = max(abs(float(base_value)), 1.0)
            if abs(float(candidate_value) - float(base_value)) / scale > max_relative_step:
                return False
            continue
        # Categorical/text values must match; otherwise this is not a local
        # numeric-neighborhood comparison.
        return False
    return changed


@router.post("/research/backtest-evidence")
async def ingest_backtest_evidence(
    payload: BacktestEvidenceRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    """Persist a real Tester result as append-only evidence, never activate it."""
    identity = ConfigurationIdentity(
        strategy=payload.strategy,
        instrument=payload.instrument,
        timeframe=payload.timeframe,
        parameters=payload.parameters,
        data_version=payload.data_version,
        optimizer_version=payload.optimizer_version,
    )
    config_hash = identity.config_hash
    if payload.claimed_config_hash and payload.claimed_config_hash != config_hash:
        raise HTTPException(status_code=409, detail="claimed_config_hash does not match canonical configuration identity")
    now = datetime.now(timezone.utc)
    if payload.provenance.period_end > now:
        raise HTTPException(status_code=422, detail="backtest period_end cannot be in the future")
    if payload.provenance.generated_at > now:
        raise HTTPException(status_code=422, detail="tester evidence generated_at cannot be in the future")

    grouped: dict[int, dict[str, list[Any]]] = defaultdict(lambda: {"train": [], "validation": []})
    holdout = [row for row in payload.trades if row.partition == "locked_oos"]
    train_all = [row for row in payload.trades if row.partition == "train"]
    validation_all = [row for row in payload.trades if row.partition == "validation"]
    keys = [(row.fold_id, row.partition, row.trade_id) for row in payload.trades]
    if len(keys) != len(set(keys)):
        raise HTTPException(status_code=422, detail="duplicate trade_id within the same fold/partition")
    for row in train_all:
        grouped[int(row.fold_id)]["train"].append(row)
    for row in validation_all:
        grouped[int(row.fold_id)]["validation"].append(row)
    for fold_id, partitions in grouped.items():
        train_ids = {row.trade_id for row in partitions["train"]}
        validation_ids = {row.trade_id for row in partitions["validation"]}
        if train_ids & validation_ids:
            raise HTTPException(status_code=422, detail=f"fold {fold_id} reuses trade IDs across train and validation")
    if not holdout:
        raise HTTPException(status_code=422, detail="locked_oos outcomes are required")
    holdout_ids = [row.trade_id for row in holdout]
    if len(holdout_ids) != len(set(holdout_ids)):
        raise HTTPException(status_code=422, detail="locked_oos trade_id values must be unique")
    prior_partition_ids = {row.trade_id for row in [*train_all, *validation_all]}
    if prior_partition_ids & set(holdout_ids):
        raise HTTPException(status_code=422, detail="locked_oos reuses train/validation trade IDs")

    folds: list[dict[str, Any]] = []
    fold_verdicts: list[str] = []
    for fold_id in sorted(grouped):
        fold_train = grouped[fold_id]["train"]
        fold_validation = grouped[fold_id]["validation"]
        if not fold_train or not fold_validation:
            raise HTTPException(status_code=422, detail=f"fold {fold_id} must have train and validation rows")
        if max(row.timestamp for row in fold_train) >= min(row.timestamp for row in fold_validation):
            raise HTTPException(status_code=422, detail=f"fold {fold_id} violates train-before-validation chronology")
        if max(row.timestamp for row in fold_validation) >= min(row.timestamp for row in holdout):
            raise HTTPException(status_code=422, detail="locked_oos must start after every walk-forward validation window")
        verdict = _fold_verdict(fold_train, fold_validation)
        fold_verdicts.append(verdict)
        folds.append({
            "fold_id": fold_id,
            "train": _summarize(fold_train),
            "validation": _summarize(fold_validation),
            "verdict": verdict,
            "train_end": max(row.timestamp for row in fold_train).isoformat(),
            "validation_start": min(row.timestamp for row in fold_validation).isoformat(),
            "validation_end": max(row.timestamp for row in fold_validation).isoformat(),
        })
    if len(folds) < MIN_WALK_FORWARD_FOLDS:
        raise HTTPException(status_code=422, detail=f"at least {MIN_WALK_FORWARD_FOLDS} walk-forward folds are required")

    oos_rows = _resolved(holdout)
    if len(oos_rows) < MIN_OOS_TRADES:
        raise HTTPException(status_code=422, detail=f"locked_oos requires at least {MIN_OOS_TRADES} resolved trades")
    train_summary = _summarize(train_all)
    validation_summary = _summarize(validation_all)
    oos_summary = _summarize(holdout)
    oos_values = [float(row.realized_r) for row in oos_rows]
    # Keep raw R values local to scoring; summary JSON remains compact.
    oos_summary["_values"] = oos_values

    validation_expectancy = validation_summary["expectancy_r"]
    oos_expectancy = oos_summary["expectancy_r"]
    oos_degradation = (
        max(0.0, (float(validation_expectancy) - float(oos_expectancy)) / abs(float(validation_expectancy)))
        if validation_expectancy is not None and validation_expectancy > 0
        else 1.0
    )

    counterfactual_ids = [row.scenario_id for row in payload.counterfactual]
    counterfactual_complete = len(counterfactual_ids) >= MIN_PAIRED_SCENARIOS and len(counterfactual_ids) == len(set(counterfactual_ids))
    cf_delta = (
        mean(row.candidate_realized_r - row.baseline_realized_r for row in payload.counterfactual)
        if counterfactual_complete else None
    )
    statistical_evidence: dict[str, Any] = {
        "paired_scenario_count": len(payload.counterfactual),
        "paired_expectancy_delta_r": cf_delta,
    }
    if payload.paired_test_p_value is not None:
        statistical_evidence["p_value"] = payload.paired_test_p_value

    scale_out_ids = [row.scenario_id for row in payload.scale_out]
    scale_out_complete = len(scale_out_ids) >= MIN_PAIRED_SCENARIOS and len(scale_out_ids) == len(set(scale_out_ids))
    neighbors: list[dict[str, Any]] = []
    stable_neighbors: list[dict[str, Any]] = []
    seen_neighbor_hashes: set[str] = set()
    for neighbor in payload.parameter_neighbors:
        if not _is_parameter_neighbor(payload.parameters, neighbor.parameters):
            raise HTTPException(
                status_code=422,
                detail="parameter-neighbor configuration is not a local perturbation of the candidate",
            )
        neighbor_identity = ConfigurationIdentity(
            strategy=payload.strategy,
            instrument=payload.instrument,
            timeframe=payload.timeframe,
            parameters=neighbor.parameters,
            data_version=payload.data_version,
            optimizer_version=payload.optimizer_version,
        )
        neighbor_hash = neighbor_identity.config_hash
        if neighbor_hash == config_hash:
            raise HTTPException(status_code=422, detail="parameter neighbor cannot have the same configuration hash as candidate")
        if neighbor_hash in seen_neighbor_hashes:
            raise HTTPException(status_code=422, detail="parameter-neighbor configurations must be unique")
        seen_neighbor_hashes.add(neighbor_hash)
        if (
            neighbor.dataset_sha256 != payload.provenance.dataset_sha256
            or neighbor.ea_source_commit != payload.provenance.ea_source_commit
            or neighbor.ea_build != payload.provenance.ea_build
            or neighbor.terminal_build != payload.provenance.terminal_build
            or neighbor.period_start != payload.provenance.period_start
            or neighbor.period_end != payload.provenance.period_end
        ):
            raise HTTPException(
                status_code=422,
                detail="parameter-neighbor evidence must use the same data digest, EA/terminal build, and historical period",
            )
        if any(
            not payload.provenance.locked_oos_start <= row.timestamp < payload.provenance.locked_oos_end
            for row in neighbor.trades
        ):
            raise HTTPException(status_code=422, detail="parameter-neighbor trade is outside the common locked OOS window")
        neighbor_ids = [row.trade_id for row in neighbor.trades]
        if len(neighbor_ids) != len(set(neighbor_ids)):
            raise HTTPException(status_code=422, detail=f"duplicate trade_id in neighbor configuration {neighbor_hash}")
        neighbor_summary = _summarize(neighbor.trades)
        neighbor_expectancy = neighbor_summary["expectancy_r"]
        neighbor_record = {
            "config_hash": neighbor_hash,
            "report_sha256": neighbor.report_sha256,
            "outcome_csv_sha256": neighbor.outcome_csv_sha256,
            "metrics": neighbor_summary,
        }
        neighbors.append(neighbor_record)
        if (
            neighbor_summary["resolved_trades"] >= MIN_OOS_TRADES
            and neighbor_summary["profit_factor"] >= 1.0
            and neighbor_expectancy is not None
            and oos_expectancy is not None
            and oos_expectancy > 0
            and neighbor_expectancy > 0
            and abs(float(neighbor_expectancy) - float(oos_expectancy)) / abs(float(oos_expectancy)) <= 0.10
        ):
            stable_neighbors.append(neighbor_record)

    parameter_stability = len(stable_neighbors) / len(neighbors) if neighbors else 0.0
    parameter_degradation = (
        min(
            abs(float(item["metrics"]["expectancy_r"]) - float(oos_expectancy)) / abs(float(oos_expectancy))
            for item in stable_neighbors
        )
        if stable_neighbors and oos_expectancy and float(oos_expectancy) != 0
        else 1.0
    )

    features_complete = bool(payload.feature_importance) and all(
        row.feature.strip() for row in payload.feature_importance
    )
    clustered_complete = bool(payload.clustered_mda) and all(
        row.features and row.group_name.strip() for row in payload.clustered_mda
    )
    if payload.change_scope in {"EXIT", "BOTH"}:
        scope_valid = scale_out_complete
    else:
        scope_valid = True

    # Every received trade row must carry a timestamp inside the source period.
    # Report/data digests are retained as provenance references; the API cannot
    # independently fetch a terminal's local file to authenticate its producer.
    train_resolved_count = len(_resolved(train_all))
    validation_resolved_count = len(_resolved(validation_all))
    oos_verified = (
        len(oos_rows) >= MIN_OOS_TRADES
        and max(row.timestamp for row in validation_all) < payload.provenance.locked_oos_start
        and all(
            payload.provenance.locked_oos_start <= row.timestamp < payload.provenance.locked_oos_end
            for row in holdout
        )
    )
    research_reasons: list[str] = []
    if not oos_verified:
        research_reasons.append("locked OOS chronology/sample verification failed")
    if len(folds) < MIN_WALK_FORWARD_FOLDS:
        research_reasons.append("not enough walk-forward folds")
    if any(verdict == "diverged" for verdict in fold_verdicts):
        research_reasons.append("one or more walk-forward folds diverged")
    if any(verdict == "insufficient_data" for verdict in fold_verdicts):
        research_reasons.append("one or more walk-forward folds lack minimum sample")
    if not features_complete:
        research_reasons.append("feature-importance evidence is incomplete")
    if not clustered_complete:
        research_reasons.append("clustered-MDA evidence is incomplete")
    if not counterfactual_complete:
        research_reasons.append("paired counterfactual evidence is incomplete")
    if not scope_valid:
        research_reasons.append("scale-out replay evidence is required for exit-affecting changes")

    research_pass = not research_reasons
    quality_pass = (
        oos_expectancy is not None
        and float(oos_expectancy) > 0.0
        and float(oos_summary["profit_factor"]) >= 1.0
        and oos_degradation <= 0.35
        and bool(stable_neighbors)
    )
    components = _objective_components(oos_summary, fold_verdicts, parameter_stability)
    score = _objective_score(components)
    all_records = [*train_all, *validation_all, *holdout]
    first_fold = grouped[min(grouped)]
    last_fold = grouped[max(grouped)]
    provenance_payload = payload.model_dump(mode="json")
    payload_sha256 = hashlib.sha256(
        json.dumps(provenance_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    evidence_provenance = {
        "source": payload.provenance.source,
        "run_id": payload.provenance.run_id,
        "report_sha256": payload.provenance.report_sha256,
        "outcome_csv_sha256": payload.provenance.outcome_csv_sha256,
        "dataset_sha256": payload.provenance.dataset_sha256,
        "ingest_payload_sha256": payload_sha256,
        "ea_source_commit": payload.provenance.ea_source_commit,
        "ea_build": payload.provenance.ea_build,
        "terminal_build": payload.provenance.terminal_build,
        "data_vendor": payload.provenance.data_vendor,
        "period_start": payload.provenance.period_start.isoformat(),
        "period_end": payload.provenance.period_end.isoformat(),
        "generated_at": payload.provenance.generated_at.isoformat(),
        "execution_costs": {
            "spread_model": payload.provenance.spread_model,
            "spread_points": payload.provenance.spread_points,
            "commission_per_lot": payload.provenance.commission_per_lot,
            "slippage_points": payload.provenance.slippage_points,
            "fill_policy": payload.provenance.fill_policy,
        },
        "walk_forward_folds": folds,
        "parameter_neighbors": neighbors,
        "feature_importance": [row.model_dump(mode="json") for row in payload.feature_importance],
        "clustered_mda": [row.model_dump(mode="json") for row in payload.clustered_mda],
        "counterfactual": [row.model_dump(mode="json") for row in payload.counterfactual],
        "paired_test_p_value": payload.paired_test_p_value,
        "scale_out": [row.model_dump(mode="json") for row in payload.scale_out],
        "trade_observations": len(all_records),
    }

    validation_evidence = {
        "training_trades": train_resolved_count,
        "validation_trades": validation_resolved_count,
        "holdout_trades": len(oos_rows),
        "purged_walk_forward": len(folds) >= MIN_WALK_FORWARD_FOLDS and all(v == "consistent" for v in fold_verdicts),
        "independent_holdout": oos_verified,
        "oos_verified": oos_verified,
        "oos_degradation": round(float(oos_degradation), 8),
        "parameter_degradation": round(float(parameter_degradation), 8),
        "parameter_stability": round(float(parameter_stability), 8),
        "walk_forward_verdicts": fold_verdicts,
        "feature_importance_complete": features_complete,
        "clustered_mda_complete": clustered_complete,
        "counterfactual_complete": counterfactual_complete,
        "scale_out_complete": scale_out_complete,
        "research_pass": research_pass,
        "oos_quality_pass": quality_pass,
        "research_reasons": research_reasons,
    }

    performance_metrics = {
        "train": train_summary,
        "validation": validation_summary,
        "locked_oos": {key: value for key, value in oos_summary.items() if key != "_values"},
        "objective_score": score,
        "objective_components": components,
        "counterfactual_expectancy_delta_r": cf_delta,
        "stable_parameter_neighbors": len(stable_neighbors),
    }
    risk_metrics = {
        "locked_oos_max_drawdown_r": oos_summary["max_drawdown_r"],
        "locked_oos_profit_factor": oos_summary["profit_factor"],
        "oos_degradation": round(float(oos_degradation), 8),
        "parameter_degradation": round(float(parameter_degradation), 8),
        "transaction_costs": {
            "commission_total": oos_summary["commission_cost_total"],
            "spread_total": oos_summary["spread_cost_total"],
            "slippage_total": oos_summary["slippage_cost_total"],
        },
    }

    if not research_pass:
        decision = "INSUFFICIENT_EVIDENCE"
    elif not quality_pass:
        decision = "HOLD"
    else:
        decision = "VALIDATED"

    existing = await session.scalar(
        select(ConfigurationRegistry).where(ConfigurationRegistry.config_hash == config_hash)
    )
    if existing is None:
        registry = ConfigurationRegistry.from_identity(
            identity,
            provenance={"initial_source": "MT5_STRATEGY_TESTER", "first_run_id": payload.provenance.run_id},
            performance_metrics=performance_metrics,
            risk_metrics=risk_metrics,
            regime_conditions={"source": "backtest_evidence", "change_scope": payload.change_scope},
            train_start=min(row.timestamp for row in first_fold["train"]),
            train_end=max(row.timestamp for row in first_fold["train"]),
            validation_start=min(row.timestamp for row in first_fold["validation"]),
            validation_end=max(row.timestamp for row in last_fold["validation"]),
            holdout_start=min(row.timestamp for row in holdout),
            holdout_end=max(row.timestamp for row in holdout),
        )
        session.add(registry)
        await session.flush()
    else:
        registry = existing
        expected = ConfigurationIdentity(
            strategy=registry.strategy,
            instrument=registry.instrument,
            timeframe=registry.timeframe,
            parameters=registry.parameters or {},
            data_version=registry.data_version,
            optimizer_version=registry.optimizer_version,
        ).config_hash
        if expected != config_hash:
            raise HTTPException(status_code=409, detail="registered candidate identity/hash mismatch")
        prior_evaluations = list((await session.scalars(
            select(ConfigurationEvaluation)
            .where(ConfigurationEvaluation.config_hash == config_hash)
            .order_by(ConfigurationEvaluation.evidence_version.asc())
        )).all())
        if any((row.provenance or {}).get("run_id") == payload.provenance.run_id for row in prior_evaluations):
            raise HTTPException(status_code=409, detail="run_id has already been ingested for this configuration")
        if registry.lifecycle_status == "OPTIMIZED":
            registry.transition_to("BACKTESTED")
        registry.performance_metrics = performance_metrics
        registry.risk_metrics = risk_metrics
        registry.regime_conditions = {"source": "backtest_evidence", "change_scope": payload.change_scope}

    if registry.lifecycle_status == "OPTIMIZED":
        registry.transition_to("BACKTESTED")
    if decision == "VALIDATED" and registry.lifecycle_status == "BACKTESTED":
        registry.transition_to("VALIDATED")

    previous = await session.scalar(
        select(ConfigurationEvaluation)
        .where(ConfigurationEvaluation.config_hash == config_hash)
        .order_by(ConfigurationEvaluation.evidence_version.desc())
        .limit(1)
    )
    evidence_version = (previous.evidence_version + 1) if previous else 1
    evaluation = ConfigurationEvaluation.from_evidence(
        config_hash,
        evidence_version,
        objective_score={"score": score, "components": components},
        performance_metrics=performance_metrics,
        risk_metrics=risk_metrics,
        validation_evidence=validation_evidence,
        statistical_evidence=statistical_evidence,
        regime_conditions={"instrument": payload.instrument, "timeframe": payload.timeframe},
        provenance=evidence_provenance,
        decision=decision,
    )
    session.add(evaluation)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="duplicate configuration evidence version; retry with a new run_id") from exc

    return {
        "status": "stored",
        "config_hash": config_hash,
        "evidence_version": evidence_version,
        "decision": decision,
        "lifecycle_status": registry.lifecycle_status,
        "locked_oos": {key: value for key, value in oos_summary.items() if key != "_values"},
        "walk_forward_verdicts": fold_verdicts,
        "research_reasons": research_reasons,
        "promotion_boundary": "not activated; quarantine/shadow/challenger review, human approval, and exact EA config-hash ACK remain required",
    }
