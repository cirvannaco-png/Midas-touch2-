"""SQLAlchemy mapping for immutable recalibration candidate configurations."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, JSON, String

from app.database import Base
from app.config_registry import LIFECYCLE, validate_transition


class ConfigurationRegistry(Base):
    """One immutable identity record per candidate configuration.

    Identity fields are never updated in-place. A changed configuration must
    receive a new row and therefore a new SHA-256 config_hash.
    """

    __tablename__ = "configuration_registry"
    __table_args__ = (
        Index(
            "ix_configuration_registry_strategy_instrument_timeframe",
            "strategy",
            "instrument",
            "timeframe",
        ),
        Index("ix_configuration_registry_lifecycle_status", "lifecycle_status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_hash = Column(String(64), unique=True, nullable=False, index=True)
    strategy = Column(String, nullable=False)
    instrument = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    parameters = Column(JSON, nullable=False)
    data_version = Column(String, nullable=False)
    optimizer_version = Column(String, nullable=False)
    train_start = Column(DateTime(timezone=True), nullable=True)
    train_end = Column(DateTime(timezone=True), nullable=True)
    validation_start = Column(DateTime(timezone=True), nullable=True)
    validation_end = Column(DateTime(timezone=True), nullable=True)
    holdout_start = Column(DateTime(timezone=True), nullable=True)
    holdout_end = Column(DateTime(timezone=True), nullable=True)
    performance_metrics = Column(JSON, nullable=True)
    risk_metrics = Column(JSON, nullable=False)
    regime_conditions = Column(JSON, nullable=True)
    lifecycle_status = Column(String, nullable=False, default=LIFECYCLE[0])
    provenance = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    @classmethod
    def from_identity(cls, identity, *, provenance=None, performance_metrics=None,
                      risk_metrics=None, regime_conditions=None, **periods):
        """Build a registry row without mutating an existing identity."""
        return cls(
            config_hash=identity.config_hash,
            strategy=identity.strategy,
            instrument=identity.instrument,
            timeframe=identity.timeframe,
            parameters=dict(identity.parameters),
            data_version=identity.data_version,
            optimizer_version=identity.optimizer_version,
            provenance=provenance,
            performance_metrics=performance_metrics,
            risk_metrics=risk_metrics or {},
            regime_conditions=regime_conditions,
            **periods,
        )

    def transition_to(self, target: str) -> None:
        """Advance exactly one lifecycle step; never skip evidence stages."""
        validate_transition(self.lifecycle_status, target)
        self.lifecycle_status = target

    def is_terminal(self) -> bool:
        return self.lifecycle_status == LIFECYCLE[-1]
