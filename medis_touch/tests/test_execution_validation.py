from medis_touch.app.execution_validation import RejectionReason, SymbolMetadata, validate_execution, validate_stop_distance, validate_volume


def _meta(**overrides):
    values = dict(point_size=0.01, tick_size=0.01, stops_level_points=10, freeze_level_points=5, volume_min=0.1, volume_max=10.0, volume_step=0.1, trading_permitted=True, session_open=True, price_digits=2)
    values.update(overrides)
    return SymbolMetadata(**values)


def test_missing_or_zero_point_size_fails_closed():
    assert validate_stop_distance(entry_price=100, stop_loss=99.8, meta=_meta(point_size=None)).reason is RejectionReason.MISSING_POINT_SIZE
    assert validate_stop_distance(entry_price=100, stop_loss=99.8, meta=_meta(point_size=0)).reason is RejectionReason.MISSING_POINT_SIZE


def test_zero_volume_step_fails_closed_without_division_error():
    result = validate_volume(1.0, _meta(volume_step=0))
    assert result.reason is RejectionReason.MISSING_VOLUME_LIMITS


def test_nonfinite_margin_fails_closed():
    result = validate_execution(entry_price=100, stop_loss=99.8, volume=1.0, meta=_meta(), required_margin=float("nan"), free_margin=1000)
    assert result.reason is RejectionReason.INSUFFICIENT_MARGIN


def test_valid_execution_passes():
    result = validate_execution(entry_price=100, stop_loss=99.8, volume=1.0, meta=_meta(), required_margin=100, free_margin=1000)
    assert result.ok
