"""Fail-closed research validation gate.

The gate composes the existing locked OOS and walk-forward evidence with the
new feature-importance, clustered-MDA, counterfactual, and scale-out studies.
It only decides whether evidence is complete enough for promotion review; it
never changes a trading parameter.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ResearchScope(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    BOTH = "BOTH"


class ResearchValidationStatus(str, Enum):
    PASS = "PASS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ResearchValidationPolicy:
    minimum_oos_trades: int = 30
    minimum_walk_forward_folds: int = 3
    require_feature_importance: bool = True
    require_clustered_mda: bool = True
    require_counterfactual: bool = True
    require_scale_out_for_exit_scope: bool = True


@dataclass(frozen=True)
class ResearchValidationEvidence:
    oos_verified: bool
    oos_trades: int
    walk_forward_verdicts: tuple[str, ...]
    feature_importance_complete: bool = False
    clustered_mda_complete: bool = False
    counterfactual_complete: bool = False
    scale_out_complete: bool = False


@dataclass(frozen=True)
class ResearchValidationDecision:
    status: ResearchValidationStatus
    reasons: tuple[str, ...]


def validate_research_evidence(
    evidence: ResearchValidationEvidence,
    *,
    scope: ResearchScope,
    policy: ResearchValidationPolicy = ResearchValidationPolicy(),
) -> ResearchValidationDecision:
    reasons: list[str] = []
    if not evidence.oos_verified:
        reasons.append("locked OOS provenance has not been verified")
    if evidence.oos_trades < policy.minimum_oos_trades:
        reasons.append(
            f"OOS sample {evidence.oos_trades} is below minimum {policy.minimum_oos_trades}"
        )
    if len(evidence.walk_forward_verdicts) < policy.minimum_walk_forward_folds:
        reasons.append(
            f"walk-forward folds {len(evidence.walk_forward_verdicts)} "
            f"are below minimum {policy.minimum_walk_forward_folds}"
        )
    if any(verdict != "consistent" for verdict in evidence.walk_forward_verdicts):
        reasons.append("at least one walk-forward fold is not consistent")
    if policy.require_feature_importance and not evidence.feature_importance_complete:
        reasons.append("feature-importance evidence is incomplete")
    if policy.require_clustered_mda and not evidence.clustered_mda_complete:
        reasons.append("clustered-MDA evidence is incomplete")
    if policy.require_counterfactual and not evidence.counterfactual_complete:
        reasons.append("counterfactual replay evidence is incomplete")
    if scope in (ResearchScope.EXIT, ResearchScope.BOTH) and policy.require_scale_out_for_exit_scope:
        if not evidence.scale_out_complete:
            reasons.append("scale-out replay evidence is required for exit-affecting changes")

    if not evidence.oos_verified or any(verdict == "diverged" for verdict in evidence.walk_forward_verdicts):
        return ResearchValidationDecision(ResearchValidationStatus.FAIL, tuple(reasons))
    if reasons:
        return ResearchValidationDecision(
            ResearchValidationStatus.INSUFFICIENT_EVIDENCE, tuple(reasons)
        )
    return ResearchValidationDecision(ResearchValidationStatus.PASS, ())
