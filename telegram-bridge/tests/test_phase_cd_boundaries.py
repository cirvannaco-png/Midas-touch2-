"""Regression tests for the staged Phase C/D compatibility seams.

These tests intentionally do not change route registration or trading behavior.
They prove that the new service boundary and the legacy app.models surface
remain usable while the larger decompositions are staged incrementally.
"""

import inspect

from app.models import Base, Signal, SignalOutcome, Subscriber, TradeEvent
from app.services.copy_authorization import (
    CopyFeedKeyUnknown,
    CopyFeedNotEntitled,
    authorize_copy_feed,
)


def test_models_compatibility_exports_preserve_metadata():
    expected = {
        "signals",
        "trade_events",
        "signal_outcomes",
        "subscribers",
    }
    assert expected.issubset(set(Base.metadata.tables))
    assert Signal.__tablename__ == "signals"
    assert TradeEvent.__tablename__ == "trade_events"
    assert SignalOutcome.__tablename__ == "signal_outcomes"
    assert Subscriber.__tablename__ == "subscribers"


def test_copy_authorization_service_has_fail_closed_contract():
    assert inspect.iscoroutinefunction(authorize_copy_feed)
    assert issubclass(CopyFeedKeyUnknown, PermissionError)
    assert issubclass(CopyFeedNotEntitled, PermissionError)


def test_model_columns_keep_compatibility_names():
    assert {"signal_id", "status", "received_at"}.issubset(Signal.__table__.columns.keys())
    assert {"event_id", "trade_id", "status"}.issubset(TradeEvent.__table__.columns.keys())
    assert {"signal_id", "outcome"}.issubset(SignalOutcome.__table__.columns.keys())
    assert {"telegram_user_id", "copy_feed_api_key"}.issubset(Subscriber.__table__.columns.keys())
