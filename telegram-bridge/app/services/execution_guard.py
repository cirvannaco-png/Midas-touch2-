"""Fail-closed execution boundary contract.

This is a contract/seam only. Broker order placement remains outside the
Telegram bridge. No broker credentials or trading logic belong here.
"""

from .architecture import ArchitectureViolation, EXECUTION_GATE_ORDER


def require_authoritative_portfolio_admission(*, admitted: bool, authoritative: bool) -> None:
    """Reject execution unless persistent admission was authoritatively verified."""
    if not admitted or not authoritative:
        raise ArchitectureViolation(
            "Execution requires authoritative persistent portfolio admission"
        )


def require_all_gates(completed: set[str]) -> None:
    """Reject an execution attempt with any missing mandatory gate."""
    missing = [gate for gate in EXECUTION_GATE_ORDER if gate not in completed]
    if missing:
        raise ArchitectureViolation(f"Execution blocked; missing gates: {', '.join(missing)}")
