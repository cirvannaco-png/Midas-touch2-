from __future__ import annotations

import pytest

from app.services.architecture import ArchitectureViolation, EXECUTION_GATE_ORDER
from app.services.execution_guard import require_broker_execution_authority


def _gates() -> set[str]:
    return set(EXECUTION_GATE_ORDER)


def _authorize(**overrides):
    values = {
        "principal": "midas_ea",
        "environment": "demo",
        "admitted": True,
        "authoritative": True,
        "ledger_ready": True,
        "risk_protection_ready": True,
        "completed_gates": _gates(),
    }
    values.update(overrides)
    require_broker_execution_authority(**values)


def test_external_ai_is_proposal_only_even_with_other_gates_satisfied():
    with pytest.raises(ArchitectureViolation, match="proposal-only"):
        _authorize(principal="external_ai")


@pytest.mark.parametrize("missing", ["execution_ledger", "risk_gate", "reconciliation"])
def test_midas_execution_rejects_missing_mandatory_gate(missing):
    gates = _gates()
    gates.remove(missing)
    with pytest.raises(ArchitectureViolation, match="missing gates"):
        _authorize(completed_gates=gates)


def test_midas_execution_requires_authoritative_persistent_admission():
    with pytest.raises(ArchitectureViolation, match="authoritative persistent"):
        _authorize(authoritative=False)


def test_midas_execution_requires_ready_ledger_and_risk_protection():
    with pytest.raises(ArchitectureViolation, match="durable execution ledger"):
        _authorize(ledger_ready=False)
    with pytest.raises(ArchitectureViolation, match="protective-stop"):
        _authorize(risk_protection_ready=False)


def test_production_requires_demo_validation_and_human_approval():
    with pytest.raises(ArchitectureViolation, match="validated demo"):
        _authorize(environment="production")
    with pytest.raises(ArchitectureViolation, match="validated demo"):
        _authorize(environment="production", demo_validated=True, human_approved=False)
    _authorize(environment="production", demo_validated=True, human_approved=True)


def test_midas_ea_can_execute_on_demo_only_after_all_gates():
    _authorize()
