"""Evidence provenance for Midas Touch calibration and cold-start data.

Historical, OOS, demo-forward, and live observations must never be treated
as interchangeable evidence. This module provides the canonical labels and
a conservative ordering for downstream calibration code.
"""

from __future__ import annotations

from enum import Enum


class EvidenceSource(str, Enum):
    BACKTEST = "BACKTEST"
    OOS_WALK_FORWARD = "OOS_WALK_FORWARD"
    DEMO_FORWARD = "DEMO_FORWARD"
    MICRO_LIVE = "MICRO_LIVE"
    LIVE = "LIVE"


# Ordering is provenance, not a claim that one source is inherently more
# predictive. Calibration code may use these labels to prevent accidental
# pooling or to apply explicitly documented weights.
PROVENANCE_ORDER = (
    EvidenceSource.BACKTEST,
    EvidenceSource.OOS_WALK_FORWARD,
    EvidenceSource.DEMO_FORWARD,
    EvidenceSource.MICRO_LIVE,
    EvidenceSource.LIVE,
)


def normalize_source(value: str | EvidenceSource) -> EvidenceSource:
    """Normalize persisted/user input and reject unknown evidence sources."""
    if isinstance(value, EvidenceSource):
        return value
    try:
        return EvidenceSource(value.upper())
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"unknown evidence source: {value!r}") from exc


def can_enter_calibration(source: str | EvidenceSource) -> bool:
    """Return whether the source is a recognized calibration provenance."""
    normalize_source(source)
    return True
