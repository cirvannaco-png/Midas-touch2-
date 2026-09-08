"""Fail-closed promotion gate over persisted configuration evidence.

The gate is deliberately independent of trading logic. It consumes immutable
configuration-evaluation evidence and the configured policy, and returns an
explicit decision. Missing or malformed evidence never becomes a promotion.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

from tools.recalibration_guard import PromotionPolicy, challenger_passes

REQUIRED_OBJECTIVE_COMPONENTS = (
    "risk_adjusted_return",
    "expectancy",
    "profit_factor",
    "drawdown_control",
    "out_of_sample_stability",
    "parameter_stability",
)
REQUIRED_VALIDATION_FIELDS = (
    "training_trades",
    "validation_trades",
    "holdout_trades",
    "purged_walk_forward",
    "independent_holdout",
)
REQUIRED_STATISTICAL_FIELDS = ("p_value",)


@dataclass(frozen=True)
class PromotionDecision:
    action: str
    reasons: tuple[str, ...]


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _complete_evidence(
    evaluation: Any, *, require_statistics: bool
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for field in (
        "objective_score",
        "performance_metrics",
        "risk_metrics",
        "validation_evidence",
        "regime_conditions",
        "provenance",
    ):
        if getattr(evaluation, field, None) in (None, {}):
            reasons.append(f"missing persisted evidence: {field}")

    objective = getattr(evaluation, "objective_score", {})
    if isinstance(objective, Mapping):
        components = objective.get("components", objective)
        if not isinstance(components, Mapping):
            reasons.append("objective_score.components must be a mapping")
        else:
            missing = [name for name in REQUIRED_OBJECTIVE_COMPONENTS if name not in components]
            if missing:
                reasons.append(f"missing objective components: {', '.join(missing)}")
            if "score" not in objective:
                reasons.append("missing persisted composite objective score")

    validation = getattr(evaluation, "validation_evidence", {})
    if isinstance(validation, Mapping):
        missing = [name for name in REQUIRED_VALIDATION_FIELDS if name not in validation]
        if missing:
            reasons.append(f"missing validation evidence: {', '.join(missing)}")
        if validation.get("independent_holdout") is not True:
            reasons.append("independent holdout evidence is required and must be true")
        if validation.get("purged_walk_forward") is not True:
            reasons.append("purged walk-forward evidence is required and must be true")

    statistics = getattr(evaluation, "statistical_evidence", {})
    if require_statistics:
        if not isinstance(statistics, Mapping):
            reasons.append("statistical evidence is required")
        else:
            missing = [name for name in REQUIRED_STATISTICAL_FIELDS if name not in statistics]
            if missing:
                reasons.append(f"missing statistical evidence: {', '.join(missing)}")
            elif not isinstance(statistics.get("p_value"), (int, float)) or not isfinite(float(statistics["p_value"])):
                reasons.append("statistical p_value must be a finite number")
    return not reasons, reasons


def evaluate_challenger(
    champion: Any,
    challenger: Any,
    *,
    policy: PromotionPolicy,
) -> PromotionDecision:
    """Evaluate persisted evidence; never infer missing values or mutate state."""
    ok_champion, champion_reasons = _complete_evidence(champion, require_statistics=False)
    ok_challenger, challenger_reasons = _complete_evidence(
        challenger,
        require_statistics=policy.maximum_p_value is not None,
    )
    if not ok_champion:
        return PromotionDecision("HOLD", ("champion evidence incomplete", *champion_reasons))
    if not ok_challenger:
        return PromotionDecision("HOLD", ("challenger evidence incomplete", *challenger_reasons))

    try:
        objective = _require_mapping(challenger.objective_score, "challenger.objective_score")
        champion_objective = _require_mapping(champion.objective_score, "champion.objective_score")
        challenger_score = float(objective["score"])
        champion_score = float(champion_objective["score"])
        validation = _require_mapping(challenger.validation_evidence, "challenger.validation_evidence")
        statistics = _require_mapping(challenger.statistical_evidence, "challenger.statistical_evidence")
        if not all(isfinite(value) for value in (challenger_score, champion_score)):
            return PromotionDecision("HOLD", ("persisted objective score is not finite",))
        oos_degradation = float(validation.get("oos_degradation", 1.0))
        parameter_degradation = float(validation.get("parameter_degradation", 1.0))
        p_value = statistics.get("p_value")
        if not all(isfinite(value) for value in (oos_degradation, parameter_degradation)):
            return PromotionDecision("HOLD", ("persisted degradation evidence is not finite",))
    except (KeyError, TypeError, ValueError):
        return PromotionDecision("HOLD", ("persisted promotion evidence has invalid numeric fields",))

    passed = challenger_passes(
        champion_score=champion_score,
        challenger_score=challenger_score,
        oos_degradation=oos_degradation,
        parameter_degradation=parameter_degradation,
        statistical_p_value=p_value,
        policy=policy,
    )
    if not passed:
        return PromotionDecision("HOLD", ("challenger failed persisted promotion policy",))
    return PromotionDecision(
        "PROMOTE", ("persisted evidence satisfies challenger-to-champion policy",)
    )
