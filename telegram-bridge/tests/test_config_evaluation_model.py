import pytest

from app.config_evaluation_model import ConfigurationEvaluation
HASH = "a" * 64


def test_evaluation_materializes_complete_evidence_snapshot():
    row = ConfigurationEvaluation.from_evidence(
        HASH,
        1,
        objective_score={"composite": 0.81, "expectancy": 0.72},
        performance_metrics={"profit_factor": 1.7},
        risk_metrics={"max_drawdown": 0.12},
        validation_evidence={
            "training_trades": 300,
            "validation_trades": 100,
            "holdout_trades": 100,
            "purged": True,
            "holdout_untouched": True,
        },
        statistical_evidence={"paired_test": "wilcoxon", "p_value": 0.03},
        regime_conditions={"trend": 0.8, "volatility": 0.6},
        provenance={"data_version": "market-v1", "optimizer_version": "optimizer-v1"},
        decision="CHALLENGER",
    )

    assert row.config_hash == HASH
    assert row.evidence_version == 1
    assert row.validation_evidence["holdout_untouched"] is True
    assert row.statistical_evidence["p_value"] == 0.03


def test_evidence_version_must_be_positive():
    with pytest.raises(ValueError, match="evidence_version must be positive"):
        ConfigurationEvaluation.from_evidence(
            HASH,
            0,
            objective_score={},
            performance_metrics={},
            risk_metrics={},
            validation_evidence={},
            statistical_evidence={},
            regime_conditions={},
            provenance={},
            decision="HOLD",
        )


def test_invalid_config_hash_fails_closed():
    with pytest.raises(ValueError, match="64-character SHA-256 hash"):
        ConfigurationEvaluation.from_evidence(
            "short",
            1,
            objective_score={},
            performance_metrics={},
            risk_metrics={},
            validation_evidence={},
            statistical_evidence={},
            regime_conditions={},
            provenance={},
            decision="HOLD",
        )


def test_evidence_is_a_new_snapshot_not_an_identity_mutation():
    first = ConfigurationEvaluation.from_evidence(
        HASH,
        1,
        objective_score={"composite": 0.70},
        performance_metrics={"profit_factor": 1.4},
        risk_metrics={"max_drawdown": 0.15},
        validation_evidence={"holdout_untouched": True},
        statistical_evidence={"p_value": 0.20},
        regime_conditions={},
        provenance={},
        decision="HOLD",
    )
    second = ConfigurationEvaluation.from_evidence(
        HASH,
        2,
        objective_score={"composite": 0.82},
        performance_metrics={"profit_factor": 1.8},
        risk_metrics={"max_drawdown": 0.10},
        validation_evidence={"holdout_untouched": True},
        statistical_evidence={"p_value": 0.03},
        regime_conditions={},
        provenance={},
        decision="CHALLENGER",
    )

    assert first.config_hash == second.config_hash
    assert first.evidence_version != second.evidence_version
    assert first.objective_score != second.objective_score
