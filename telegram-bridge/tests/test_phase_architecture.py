import pytest

from app.services.architecture import ArchitectureViolation, assert_execution_order
from app.services.execution_guard import require_all_gates, require_authoritative_portfolio_admission
from app.services.payment_integrity import PaymentIntegrityError, validate_entitlement_inputs


def test_execution_order_is_fail_closed():
    assert_execution_order(["signal", "freshness", "eligibility", "risk_gate"])
    with pytest.raises(ArchitectureViolation):
        assert_execution_order(["signal", "risk_gate", "freshness"])


def test_portfolio_admission_cannot_be_asserted_by_caller_flag_alone():
    with pytest.raises(ArchitectureViolation):
        require_authoritative_portfolio_admission(admitted=True, authoritative=False)


def test_execution_requires_all_mandatory_gates():
    with pytest.raises(ArchitectureViolation):
        require_all_gates({"signal", "freshness"})


def test_payment_integrity_fails_closed():
    with pytest.raises(PaymentIntegrityError):
        validate_entitlement_inputs(
            verified=False,
            transaction_id="tx-1",
            amount=500,
            currency="KES",
            period_days=7,
        )


def test_payment_integrity_accepts_verified_reconciled_inputs():
    validate_entitlement_inputs(
        verified=True,
        transaction_id="tx-1",
        amount=500,
        currency="KES",
        period_days=7,
    )
