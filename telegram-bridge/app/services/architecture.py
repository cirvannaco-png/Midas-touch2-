"""Architecture invariants shared by Phase A-D reviews.

This module intentionally contains no trading decisions. It documents the
fail-closed ordering that execution-facing code must preserve.
"""

EXECUTION_GATE_ORDER = (
    "signal",
    "freshness",
    "eligibility",
    "entitlement",
    "copy_authorization",
    "broker_capability",
    "user_risk_validation",
    "risk_gate",
    "portfolio_gate",
    "persistent_portfolio_admission",
    "execution_ledger",
    "order_check",
    "order_send_async",
    "broker_acknowledgement",
    "trade_transaction",
    "position_observation",
    "reconciliation",
    "outcome_telemetry",
)


class ArchitectureViolation(RuntimeError):
    """Raised when a service attempts to bypass a mandatory gate."""


def assert_execution_order(completed: list[str]) -> None:
    """Fail closed if completed gates are out of canonical order."""
    positions = {name: index for index, name in enumerate(EXECUTION_GATE_ORDER)}
    seen = [positions[name] for name in completed if name in positions]
    if seen != sorted(seen) or len(set(seen)) != len(seen):
        raise ArchitectureViolation("Execution gates must remain fail-closed and ordered")
