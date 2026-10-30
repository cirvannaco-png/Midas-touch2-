"""Fail-closed execution boundary contract.

This is a contract/seam only. Broker order placement remains outside the
Telegram bridge. No broker credentials or trading logic belong here.
"""

from .architecture import EXECUTION_GATE_ORDER, ArchitectureViolation


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



def require_broker_execution_authority(
    *,
    principal: str,
    environment: str,
    admitted: bool,
    authoritative: bool,
    ledger_ready: bool,
    risk_protection_ready: bool,
    completed_gates: set[str],
    demo_validated: bool = False,
    human_approved: bool = False,
) -> None:
    """Authorize only Midas-owned execution after every mandatory control.

    External AI assistants may research, explain, and propose. They are not a
    broker principal and cannot submit or modify a production position. The
    Midas EA remains the sole broker execution authority. Production execution
    additionally requires a previously validated demo configuration and
    explicit human approval.
    """
    if principal != "midas_ea":
        raise ArchitectureViolation(
            "Broker execution is restricted to the Midas EA; external AI is proposal-only"
        )
    normalized_environment = environment.strip().casefold()
    if normalized_environment not in {"demo", "production", "strategy_tester"}:
        raise ArchitectureViolation("Execution environment is not recognized")
    if not ledger_ready:
        raise ArchitectureViolation("Execution requires a ready durable execution ledger")
    if not risk_protection_ready:
        raise ArchitectureViolation("Execution requires active Midas risk and protective-stop controls")
    if normalized_environment == "production" and not (demo_validated and human_approved):
        raise ArchitectureViolation(
            "Production execution requires validated demo evidence and explicit human approval"
        )
    require_authoritative_portfolio_admission(
        admitted=admitted,
        authoritative=authoritative,
    )
    require_all_gates(completed_gates)
