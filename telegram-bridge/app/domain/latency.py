from dataclasses import dataclass, field
from time import monotonic_ns
from typing import Dict


@dataclass
class LatencyTrace:
    started_ns: int = field(default_factory=monotonic_ns)
    marks: Dict[str, int] = field(default_factory=dict)

    def mark(self, name: str) -> None:
        self.marks[name] = monotonic_ns()

    def duration_ms(self, start: str | None, end: str) -> float | None:
        end_ns = self.marks.get(end)
        if end_ns is None:
            return None
        start_ns = self.started_ns if start is None else self.marks.get(start)
        if start_ns is None:
            return None
        return (end_ns - start_ns) / 1_000_000

    def metrics(self) -> dict[str, float]:
        ordered = ["signal_received", "eligibility", "entitlement", "authorization", "risk", "portfolio", "order_check", "submission", "broker_ack", "position_observed", "reconciliation"]
        result = {}
        previous = None
        for name in ordered:
            if name in self.marks:
                result[f"{name}_latency_ms"] = self.duration_ms(previous, name) or 0.0
                previous = name
        if self.marks:
            last = ordered[-1]
            if last in self.marks:
                result["end_to_end_latency_ms"] = (self.marks[last] - self.started_ns) / 1_000_000
        return result
