"""Append-only evaluation evidence for immutable recalibration candidates."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String

from app.database import Base


class ConfigurationEvaluation(Base):
    """One immutable evidence snapshot for one registered configuration.

    A new evaluation is always a new row.  The configuration registry identity
    is never overwritten when later validation evidence becomes available.
    """

    __tablename__ = "configuration_evaluations"
    __table_args__ = (
        Index("ix_configuration_evaluations_config_hash", "config_hash"),
        Index("ix_configuration_evaluations_status", "decision"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_hash = Column(
        String(64),
        ForeignKey("configuration_registry.config_hash"),
        nullable=False,
    )
    evidence_version = Column(Integer, nullable=False)
    objective_score = Column(JSON, nullable=False)
    performance_metrics = Column(JSON, nullable=False)
    risk_metrics = Column(JSON, nullable=False)
    validation_evidence = Column(JSON, nullable=False)
    statistical_evidence = Column(JSON, nullable=False)
    regime_conditions = Column(JSON, nullable=False)
    provenance = Column(JSON, nullable=False)
    decision = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    @classmethod
    def from_evidence(
        cls,
        config_hash: str,
        evidence_version: int,
        *,
        objective_score: dict,
        performance_metrics: dict,
        risk_metrics: dict,
        validation_evidence: dict,
        statistical_evidence: dict,
        regime_conditions: dict,
        provenance: dict,
        decision: str,
    ) -> "ConfigurationEvaluation":
        """Materialize one evidence snapshot; never mutate an older snapshot."""
        if evidence_version < 1:
            raise ValueError("evidence_version must be positive")
        if not config_hash or len(config_hash) != 64:
            raise ValueError("config_hash must be a 64-character SHA-256 hash")
        if not decision:
            raise ValueError("decision is required")
        return cls(
            config_hash=config_hash,
            evidence_version=evidence_version,
            objective_score=dict(objective_score),
            performance_metrics=dict(performance_metrics),
            risk_metrics=dict(risk_metrics),
            validation_evidence=dict(validation_evidence),
            statistical_evidence=dict(statistical_evidence),
            regime_conditions=dict(regime_conditions),
            provenance=dict(provenance),
            decision=decision,
        )
