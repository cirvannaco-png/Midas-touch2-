"""Persistent state for fail-closed EA configuration synchronization."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from app.database import Base


class ConfigSyncState(Base):
    """One durable synchronization state row per EA symbol."""

    __tablename__ = "config_sync_states"
    __table_args__ = (Index("ix_config_sync_states_symbol", "symbol", unique=True),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    active_config_hash = Column(String, nullable=True)
    acknowledged_config_hash = Column(String, nullable=True)
    state = Column(String, nullable=False, default="HOLD")
    last_ack_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
