"""Fail-closed parity checking for the authoritative decision envelope."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from decision_fingerprint import CANONICAL_FIELDS, canonical_fields, fingerprint


@dataclass(frozen=True)
class ParityResult:
    matched: bool
    mismatches: tuple[str, ...]
    diffs: dict[str, dict[str, str | None]]
    expected_fingerprint: str
    actual_fingerprint: str

    @property
    def event(self) -> str:
        return "PARITY_OK" if self.matched else "PARITY_MISMATCH"


def _values(payload: Mapping[str, Any]) -> dict[str, str]:
    return canonical_fields(payload)


def compare(
    authoritative: Mapping[str, Any],
    boundary: Mapping[str, Any],
) -> ParityResult:
    left = _values(authoritative)
    right = _values(boundary)
    diffs: dict[str, dict[str, str | None]] = {}
    for field in CANONICAL_FIELDS:
        if left[field] != right[field]:
            diffs[field] = {"authoritative": left[field], "boundary": right[field]}
    for field in ("risk_allowed", "news_allowed", "portfolio_allowed"):
        if bool(authoritative.get(field, True)) != bool(boundary.get(field, True)):
            diffs[field] = {"authoritative": str(bool(authoritative.get(field, True))), "boundary": str(bool(boundary.get(field, True)))}
    expected = fingerprint(authoritative)
    actual = fingerprint(boundary)
    if expected != actual and "decision_fingerprint" not in diffs:
        diffs["_fingerprint"] = {"authoritative": expected, "boundary": actual}
    return ParityResult(
        matched=not diffs,
        mismatches=tuple(diffs.keys()),
        diffs=diffs,
        expected_fingerprint=expected,
        actual_fingerprint=actual,
    )


def compare_fingerprints(
    payload: Mapping[str, Any],
    claimed_fingerprint: str | None,
) -> ParityResult:
    expected = fingerprint(payload)
    actual = (claimed_fingerprint or "").upper()
    diffs = {} if expected == actual else {
        "_fingerprint": {"authoritative": expected, "boundary": actual or None}
    }
    return ParityResult(
        matched=not diffs,
        mismatches=tuple(diffs.keys()),
        diffs=diffs,
        expected_fingerprint=expected,
        actual_fingerprint=actual,
    )
