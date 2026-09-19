"""Deterministic decision replay and non-determinism detection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from decision_fingerprint import fingerprint


@dataclass(frozen=True)
class ReplayResult:
    event: str
    matched: bool
    original_fingerprint: str
    replayed_fingerprint: str
    mismatches: dict[str, Any]


def replay(
    original: Mapping[str, Any],
    decision_engine: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> ReplayResult:
    replayed = dict(decision_engine(dict(original)))
    expected = str(original.get("decision_fingerprint") or fingerprint(original)).upper()
    actual = fingerprint(replayed)
    if expected == actual:
        return ReplayResult("REPLAY_DETERMINISTIC", True, expected, actual, {})
    diffs = {}
    for key in set(original) | set(replayed):
        if key in {"decision_fingerprint", "canonical_decision"}:
            continue
        if original.get(key) != replayed.get(key):
            diffs[key] = {"original": original.get(key), "replayed": replayed.get(key)}
    return ReplayResult("REPLAY_NON_DETERMINISM", False, expected, actual, diffs)
