from datetime import datetime, timedelta, timezone

from calibration_matrix import compute_matrix
from instrument_taxonomy import classify_symbol


def test_multi_asset_taxonomy_common_broker_symbols():
    assert classify_symbol("EURUSD.a") == "fx"
    assert classify_symbol("US500.cash") == "indices"
    assert classify_symbol("XAUUSD") == "metals"
    assert classify_symbol("BTCUSDm") == "crypto"
    assert classify_symbol("UNKNOWN_CFDb") == "other"


def test_calibration_matrix_keeps_strategy_attribution(make_outcome):
    base = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(20):
        rows.append(make_outcome(symbol="EURUSD", strategy=("SMC" if i < 10 else "MOMENTUM_BREAKOUT"), session="London", sweep_grade="A", received_at=base + timedelta(days=i)))
    matrix = compute_matrix(rows, min_sample=1)
    tags = {row["tag"] for row in matrix}
    assert any("SMC" in tag for tag in tags)
    assert any("MOMENTUM_BREAKOUT" in tag for tag in tags)
