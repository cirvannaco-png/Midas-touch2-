"""Payment-to-entitlement integrity boundary.

Provider-specific adapters remain responsible for cryptographic verification.
This module deliberately does not invent or infer provider API contracts.
"""


class PaymentIntegrityError(ValueError):
    """Raised when a verified payment cannot safely become entitlement."""


def validate_entitlement_inputs(*, verified: bool, transaction_id: str, amount: int,
                                currency: str, period_days: int) -> None:
    """Fail closed before a payment can be used for entitlement.

    Provider adapters must perform signature/webhook verification and
    reconciliation before calling this boundary.
    """
    if not verified:
        raise PaymentIntegrityError("Payment has not passed provider verification")
    if not transaction_id.strip():
        raise PaymentIntegrityError("Missing transaction identifier")
    if amount <= 0:
        raise PaymentIntegrityError("Payment amount must be positive")
    if not currency.strip():
        raise PaymentIntegrityError("Payment currency is required")
    if period_days <= 0:
        raise PaymentIntegrityError("Entitlement period must be positive")
