import pytest

from app.ai_execution_policy import (
    ExecutionAuthorizationError,
    authorize_execution_origin,
)


@pytest.mark.parametrize("action", ["ANALYZE", "EXPLAIN", "PROPOSE"])
def test_ai_agent_may_only_perform_read_only_or_proposal_actions(action):
    assert authorize_execution_origin("AI_AGENT", action) == "AI_AGENT"


@pytest.mark.parametrize(
    "action",
    ["RESERVE_EXECUTION", "SUBMIT_ORDER", "MODIFY_POSITION", "CLOSE_POSITION", "CANCEL_ORDER", "CHANGE_RISK"],
)
def test_ai_agent_cannot_mutate_broker_execution_state_even_with_approval_claim(action):
    # Approval data is deliberately not an argument to this policy. An AI
    # assertion cannot be elevated into a broker execution authorization.
    with pytest.raises(ExecutionAuthorizationError, match="cannot mutate"):
        authorize_execution_origin("AI_AGENT", action)


def test_mt5_ea_remains_the_only_broker_mutation_principal():
    assert authorize_execution_origin("MT5_EA", "RESERVE_EXECUTION") == "MT5_EA"
    with pytest.raises(ExecutionAuthorizationError):
        authorize_execution_origin("UNKNOWN", "RESERVE_EXECUTION")


