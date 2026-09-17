"""Strict parity checks for decisions represented by EA/backend telemetry."""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose


@dataclass(frozen=True)
class ParityResult:
    matched: bool
    mismatches: tuple[str, ...]


def compare(ea: dict, backend: dict, *, confidence_tol: float = 1e-9) -> ParityResult:
    mismatches: list[str] = []
    for field in ("strategy", "regime", "environment_key"):
        if ea.get(field) != backend.get(field):
            mismatches.append(field)
    if not isclose(float(ea.get("confidence", 0.0)), float(backend.get("confidence", 0.0)), abs_tol=confidence_tol):
        mismatches.append("confidence")
    for gate in ("risk_allowed", "news_allowed", "portfolio_allowed"):
        if ea.get(gate) != backend.get(gate):
            mismatches.append(gate)
    return ParityResult(not mismatches, tuple(mismatches))
