from tools.research.validation import (
    ResearchScope,
    ResearchValidationEvidence,
    ResearchValidationStatus,
    validate_research_evidence,
)


def test_entry_validation_passes_with_complete_oos_research_evidence():
    evidence = ResearchValidationEvidence(
        oos_verified=True,
        oos_trades=50,
        walk_forward_verdicts=("consistent", "consistent", "consistent"),
        feature_importance_complete=True,
        clustered_mda_complete=True,
        counterfactual_complete=True,
    )
    decision = validate_research_evidence(evidence, scope=ResearchScope.ENTRY)
    assert decision.status is ResearchValidationStatus.PASS


def test_exit_validation_requires_scale_out_evidence():
    evidence = ResearchValidationEvidence(
        oos_verified=True,
        oos_trades=50,
        walk_forward_verdicts=("consistent", "consistent", "consistent"),
        feature_importance_complete=True,
        clustered_mda_complete=True,
        counterfactual_complete=True,
        scale_out_complete=False,
    )
    decision = validate_research_evidence(evidence, scope=ResearchScope.EXIT)
    assert decision.status is ResearchValidationStatus.INSUFFICIENT_EVIDENCE
    assert "scale-out" in " ".join(decision.reasons)


def test_diverged_walk_forward_fails_closed():
    evidence = ResearchValidationEvidence(
        oos_verified=True,
        oos_trades=50,
        walk_forward_verdicts=("consistent", "diverged", "consistent"),
        feature_importance_complete=True,
        clustered_mda_complete=True,
        counterfactual_complete=True,
    )
    decision = validate_research_evidence(evidence, scope=ResearchScope.ENTRY)
    assert decision.status is ResearchValidationStatus.FAIL
