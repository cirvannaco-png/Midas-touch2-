"""Daily qualified-trade target telemetry.

A minimum daily target is a monitoring objective, not permission to lower the
strategy, risk, news, portfolio, or execution gates just to hit a number.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable, Mapping


@dataclass(frozen=True)
class DailyTargetStatus:
    day: date
    qualified_trades: int
    target: int
    met: bool

    @property
    def deficit(self) -> int:
        return max(0, self.target - self.qualified_trades)


def daily_status(records: Iterable[Mapping[str, object]], target: int = 3) -> list[DailyTargetStatus]:
    if target < 0:
        raise ValueError("target must be non-negative")
    counts: Counter[date] = Counter()
    for row in records:
        if not row.get("executed"):
            continue
        raw = row.get("execution_time") or row.get("decision_time") or row.get("signal_time")
        if not raw:
            continue
        if isinstance(raw, datetime):
            dt = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        counts[dt.astimezone(timezone.utc).date()] += 1
    return [
        DailyTargetStatus(day=day, qualified_trades=count, target=target, met=count >= target)
        for day, count in sorted(counts.items())
    ]
