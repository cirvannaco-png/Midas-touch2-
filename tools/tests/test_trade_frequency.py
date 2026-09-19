from datetime import datetime, timezone
from tools.trade_frequency import daily_status


def test_three_trade_target_is_measurement_not_force():
    rows = [
        {"executed": True, "execution_time": datetime(2026, 9, 18, 8, 0, tzinfo=timezone.utc)},
        {"executed": True, "execution_time": datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)},
    ]
    status = daily_status(rows, 3)
    assert status[0].qualified_trades == 2
    assert not status[0].met
