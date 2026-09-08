import asyncio

import pytest

from app.config_evaluation_model import ConfigurationEvaluation
from app.database import Base, async_session

HASH = "a" * 64


def make_row(version=1, config_hash=HASH):
    return ConfigurationEvaluation.from_evidence(
        config_hash,
        version,
        objective_score={"composite": 0.70},
        performance_metrics={"profit_factor": 1.4},
        risk_metrics={"max_drawdown": 0.15},
        validation_evidence={"holdout_untouched": True},
        statistical_evidence={"p_value": 0.20},
        regime_conditions={},
        provenance={},
        decision="HOLD",
    )


def test_evaluation_table_is_registered_in_sqlalchemy_metadata():
    assert "configuration_evaluations" in Base.metadata.tables
    table = Base.metadata.tables["configuration_evaluations"]
    assert "config_hash" in table.c
    assert "evidence_version" in table.c


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
        make_row(0)


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


def test_evidence_version_creates_a_new_snapshot():
    first = make_row(1)
    second = make_row(2)
    second.objective_score = {"composite": 0.82}
    assert first.config_hash == second.config_hash
    assert first.evidence_version != second.evidence_version
    assert first.objective_score != second.objective_score


def test_persisted_evidence_cannot_be_updated():
    async def _exercise():
        async with async_session() as session:
            row = make_row(1, "b" * 64)
            session.add(row)
            await session.commit()
            row.decision = "CHALLENGER"
            with pytest.raises(ValueError, match="append-only"):
                await session.commit()
            await session.rollback()

    asyncio.run(_exercise())


def test_persisted_evidence_cannot_be_deleted():
    async def _exercise():
        async with async_session() as session:
            row = make_row(1, "c" * 64)
            session.add(row)
            await session.commit()
            await session.delete(row)
            with pytest.raises(ValueError, match="cannot be deleted"):
                await session.commit()
            await session.rollback()

    asyncio.run(_exercise())
