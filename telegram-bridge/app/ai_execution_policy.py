"""Explicit boundary between AI reasoning and broker-mutating execution.

AI components may produce analysis and proposals. They are not execution
principals and cannot reserve risk, submit orders, modify stops, or close
positions. Broker mutations must arrive from the authenticated MT5 EA path.
"""
from __future__ import annotations


class ExecutionAuthorizationError(PermissionError):
    """Raised when the caller is not authorized to mutate broker execution state."""


READ_ONLY_AI_ACTIONS = frozenset({"ANALYZE", "EXPLAIN", "PROPOSE"})
BROKER_MUTATION_ACTIONS = frozenset(
    {
        "RESERVE_EXECUTION",
        "SUBMIT_ORDER",
        "MODIFY_POSITION",
        "CLOSE_POSITION",
        "CANCEL_ORDER",
        "CHANGE_RISK",
    }
)


def authorize_execution_origin(requested_by: str, action: str) -> str:
    """Return the authorized execution principal or fail closed.

    The AI principal is intentionally read-only. Human approval of a proposal
    must still flow through the MT5 EA's normal risk/ledger gates; an AI-supplied
    approval flag is never accepted as broker authorization.
    """
    principal = (requested_by or "").strip().upper()
    operation = (action or "").strip().upper()
    if principal == "AI_AGENT":
        if operation in READ_ONLY_AI_ACTIONS:
            return "AI_AGENT"
        if operation in BROKER_MUTATION_ACTIONS:
            raise ExecutionAuthorizationError(
                "AI agents may propose actions but cannot mutate broker execution state"
            )
        raise ExecutionAuthorizationError("unknown AI action")
    if principal == "MT5_EA" and operation in BROKER_MUTATION_ACTIONS:
        return "MT5_EA"
    raise ExecutionAuthorizationError("execution mutation requires the authenticated MT5_EA principal")
