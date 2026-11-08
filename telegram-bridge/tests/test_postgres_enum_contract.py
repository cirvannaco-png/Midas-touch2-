"""Regression tests for native PostgreSQL enum storage labels.

The migration scripts create lowercase enum labels from each Python enum's
.value. SQLAlchemy otherwise persists enum member names by default, which
causes PostgreSQL errors such as: invalid input value for enum signalstatus:
"FAILED".
"""

from app.models import (
    SignalLifecycleStatus,
    SignalStatus,
    TradeEventStatus,
    TradeEventType,
    _signal_lifecycle_status_type,
    _signal_status_type,
    _trade_event_status_type,
    _trade_event_type_type,
)


def test_signal_status_enum_uses_migration_labels():
    assert _signal_status_type.enums == [member.value for member in SignalStatus]


def test_signal_lifecycle_enum_uses_migration_labels():
    assert _signal_lifecycle_status_type.enums == [
        member.value for member in SignalLifecycleStatus
    ]


def test_trade_event_status_enum_uses_migration_labels():
    assert _trade_event_status_type.enums == [
        member.value for member in TradeEventStatus
    ]


def test_trade_event_type_enum_uses_migration_labels():
    assert _trade_event_type_type.enums == [member.value for member in TradeEventType]


def test_failed_status_is_bound_to_lowercase_database_label():
    assert SignalStatus.FAILED.value == "failed"
    assert "failed" in _signal_status_type.enums
    assert "FAILED" not in _signal_status_type.enums
