"""Fail-closed orchestration boundary for Midas Touch strategy selection.

This module deliberately does NOT invent trading heuristics. Existing
strategy detectors remain the source of truth for market-specific logic.
The pipeline's job is to enforce the architectural boundary:

    REGIME -> SELECT ONE STRATEGY -> BUILD COMPLETE TradeSetup
           -> VALIDATE -> COMMON RISK/PORTFOLIO/EXECUTION

A strategy that cannot manufacture a complete setup is not silently
replaced by SMC and its diagnostic score is not mixed into another
strategy's confidence. That prevents the selector from becoming a
second confidence soup.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from .models import OrderType, TradeSetup
from .strategy_engines import MarketContext, SetupEngine


@dataclass(frozen=True)
class StrategyCandidate:
    """A selector decision before setup construction."""

    strategy: str
    score: float


@dataclass(frozen=True)
class PipelineDecision:
    """Immutable result passed to common risk/execution infrastructure."""

    strategy: str
    setup: TradeSetup


class SetupValidationError(ValueError):
    """Raised when a strategy emits a structurally unsafe setup."""


def validate_complete_setup(setup: TradeSetup) -> None:
    """Validate the normalized contract without creating strategy logic."""
    values = (
        setup.entry_top,
        setup.entry_bottom,
        setup.invalidation,
        setup.stop_loss,
        setup.tp1,
        setup.tp2,
        setup.final_tp,
        setup.confidence,
    )
    if not all(math.isfinite(value) for value in values):
        raise SetupValidationError("TradeSetup contains a non-finite value")

    if setup.entry_top < setup.entry_bottom:
        raise SetupValidationError("entry_top must be >= entry_bottom")

    if setup.type == OrderType.BUY:
        if setup.stop_loss >= setup.entry_bottom:
            raise SetupValidationError("BUY stop_loss must be below entry range")
        if setup.invalidation >= setup.entry_bottom:
            raise SetupValidationError("BUY invalidation must be below entry range")
        if not (setup.tp1 > setup.entry_top and setup.tp2 > setup.tp1 and setup.final_tp > setup.tp2):
            raise SetupValidationError("BUY targets must increase: TP1 < TP2 < final TP")
    else:
        if setup.stop_loss <= setup.entry_top:
            raise SetupValidationError("SELL stop_loss must be above entry range")
        if setup.invalidation <= setup.entry_top:
            raise SetupValidationError("SELL invalidation must be above entry range")
        if not (setup.tp1 < setup.entry_bottom and setup.tp2 < setup.tp1 and setup.final_tp < setup.tp2):
            raise SetupValidationError("SELL targets must decrease: TP1 > TP2 > final TP")

    if not 0.0 <= setup.confidence <= 100.0:
        raise SetupValidationError("confidence must be in the canonical 0..100 range")


class AuthoritativeStrategyPipeline:
    """Turn an already-selected strategy into one normalized setup.

    `selector` must return exactly one strategy name. This class does not
    rank strategies by profit and does not manufacture a fallback setup.
    If the selected engine cannot produce a setup, the decision fails
    closed and common execution must not receive a partial thesis.
    """

    def __init__(self, engines: dict[str, SetupEngine]):
        self._engines = dict(engines)

    def build(
        self,
        selected: StrategyCandidate,
        ctx: MarketContext,
        now: datetime,
    ) -> PipelineDecision | None:
        engine = self._engines.get(selected.strategy)
        if engine is None:
            return None

        setup = engine.generate(ctx, now)
        if setup is None:
            return None

        try:
            validate_complete_setup(setup)
        except SetupValidationError:
            return None

        return PipelineDecision(strategy=selected.strategy, setup=setup)
