from medis_touch.app.execution_validation import (
    RejectionReason,
    SymbolMetadata,
    validate_execution,
    validate_stop_distance,
    validate_volume,
)


def _meta(**overrides):
    values = {
        "point_size": 0.01,
        "tick_size": 0.01,
        "stops_level_points": 10,
        "freeze_level_points": 5,
        "volume_min": 0.1,
        "volume_max": 10.0,
        "volume_step": 0.1,
        "trading_permitted": True,
        "session_open": True,
        "price_digits": 2,
    }
    values.update(overrides)
    return SymbolMetadata(**values)


def test_invalid_broker_metadata_is_rejected():
    result = validate_execution(entry_price=100.0, stop_loss=99.0, volume=1.0, meta=_meta(point_size=0), required_margin=10.0, free_margin=100.0)
    assert not result.ok
    assert result.reason is RejectionReason.MISSING_POINT_SIZE


def test_zero_volume_step_is_rejected():
    result = validate_volume(1.0, _meta(volume_step=0))
    assert not result.ok
    assert result.reason is RejectionReason.MISSING_VOLUME_LIMITS


def test_zero_point_size_is_rejected_before_division():
    result = validate_stop_distance(entry_price=100.0, stop_loss=99.0, meta=_meta(point_size=0))
    assert not result.ok
    assert result.reason is RejectionReason.MISSING_POINT_SIZE


def test_valid_metadata_passes_execution_validation():
    result = validate_execution(entry_price=100.0, stop_loss=99.0, volume=1.0, meta=_meta(), required_margin=10.0, free_margin=100.0)
    assert result.ok
