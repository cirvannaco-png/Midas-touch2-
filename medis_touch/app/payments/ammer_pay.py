"""Ammer Pay adapter kept disabled until its merchant API contract is verified.

The repository does not contain a primary-source contract for Ammer Pay's
server-to-server API. Therefore this adapter must never create or verify real
payments. This is intentionally fail-closed rather than an assumed protocol.
"""
from __future__ import annotations

from typing import Any

from .base import (
    CheckoutRequest,
    CheckoutResult,
    NormalizedPaymentEvent,
    PaymentProvider,
    WebhookVerificationError,
)


class AmmerPayProvider(PaymentProvider):
    name = "ammer_pay"

    def __init__(self, **_: Any) -> None:
        raise RuntimeError(
            "Ammer Pay is disabled: the production merchant API, webhook schema, "
            "signature algorithm, and endpoint contract have not been verified. "
            "Use a verified payment provider until those contracts are supplied."
        )

    def create_checkout(self, request: CheckoutRequest) -> CheckoutResult:
        raise RuntimeError("Ammer Pay is disabled until its production API contract is verified")

    def verify_webhook(self, headers: dict[str, str], raw_body: bytes) -> dict[str, Any]:
        raise WebhookVerificationError("Ammer Pay webhook verification is disabled until its signature contract is verified")

    def normalize_event(self, verified_payload: dict[str, Any]) -> NormalizedPaymentEvent:
        raise WebhookVerificationError("Ammer Pay event normalization is disabled until its payload contract is verified")

    def lookup_payment(self, provider_payment_id: str) -> dict[str, Any]:
        raise RuntimeError("Ammer Pay payment lookup is disabled until its production API contract is verified")
