"""
Copy-trading schema and authorization gate.

The copy layer authorizes already-created Midas signals; it never creates
alpha or bypasses execution governance. Authorization is rechecked immediately
before a copy event is claimed for execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class CopyEventStatus(str, Enum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class SubscriptionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    PAST_DUE = "PAST_DUE"


class EntitlementStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


@dataclass
class CopyAccount:
    account_id: str
    user_id: str
    broker: str
    broker_account_reference: str
    enabled: bool
    risk_mode: str
    risk_value: float


@dataclass
class Subscription:
    subscription_id: str
    user_id: str
    plan: str
    provider: str
    provider_reference: str
    status: SubscriptionStatus
    started_at: datetime
    expires_at: datetime | None


@dataclass
class Entitlement:
    entitlement_id: str
    user_id: str
    subscription_id: str
    status: EntitlementStatus
    copy_trading: bool
    signal_access: bool
    telegram_access: bool
    valid_from: datetime
    valid_until: datetime | None


@dataclass
class CopyTradeEvent:
    copy_id: str
    signal_id: str
    user_id: str
    account_id: str
    status: CopyEventStatus
    idempotency_key: str
    created_at: datetime
    broker_ticket: str | None = None
    claimed_at: datetime | None = None
    executed_at: datetime | None = None
    error: str | None = None


def account_scoped_idempotency_key(*, signal_id: str, account_id: str) -> str:
    """Return the stable idempotency namespace for one signal/account pair.

    A signal may legitimately fan out to many accounts, so the source signal
    ID alone must never be used as the broker/OMS idempotency key.
    """
    if not signal_id or not account_id:
        raise ValueError("signal_id and account_id are required")
    return f"copy:{signal_id}:account:{account_id}"


def can_copy(
    subscription: Subscription,
    entitlement: Entitlement,
    account: CopyAccount,
    signal,
    now: datetime,
) -> bool:
    """Return true only when all copy authorization conditions hold."""
    from .models import SignalStatus

    return (
        subscription.status == SubscriptionStatus.ACTIVE
        and subscription.expires_at is not None
        and subscription.expires_at > now
        and entitlement.status == EntitlementStatus.ACTIVE
        and entitlement.copy_trading is True
        and account.enabled is True
        and signal.status == SignalStatus.ACTIVE
        and signal.invalidated_at is None
        and (signal.expires_at is None or signal.expires_at > now)
    )


COPY_POLLING_WHERE_CLAUSE = """
WHERE subscription.status = 'ACTIVE'
  AND subscription.expires_at > NOW()
  AND entitlement.status = 'ACTIVE'
  AND entitlement.copy_trading = TRUE
  AND account.enabled = TRUE
  AND signal.status = 'ACTIVE'
  AND signal.invalidated_at IS NULL
  AND (signal.expires_at IS NULL OR signal.expires_at > NOW())
"""


class AuthorizationError(Exception):
    """Raised when immediate pre-execution authorization fails."""


def authorize_and_claim(
    *,
    subscription: Subscription,
    entitlement: Entitlement,
    account: CopyAccount,
    signal,
    copy_event: CopyTradeEvent,
    now: datetime,
) -> CopyTradeEvent:
    """Reauthorize and claim a pending copy event.

    Persistence must enforce the final compare-and-swap/row-lock around this
    transition. This pure function additionally rejects non-PENDING events so
    a stale worker cannot locally re-claim an event that another worker owns.
    """
    if copy_event.status != CopyEventStatus.PENDING:
        raise AuthorizationError(
            f"copy_id={copy_event.copy_id} is not pending; current={copy_event.status.value}"
        )
    expected_key = account_scoped_idempotency_key(
        signal_id=copy_event.signal_id,
        account_id=copy_event.account_id,
    )
    if copy_event.idempotency_key != expected_key:
        copy_event.status = CopyEventStatus.REJECTED
        copy_event.error = "invalid_account_scoped_idempotency_key"
        raise AuthorizationError(f"copy_id={copy_event.copy_id} has invalid idempotency scope")
    if not can_copy(subscription, entitlement, account, signal, now):
        copy_event.status = CopyEventStatus.REJECTED
        copy_event.error = "authorization_failed_at_claim_time"
        raise AuthorizationError(
            f"copy_id={copy_event.copy_id} failed re-authorization at claim time"
        )

    copy_event.status = CopyEventStatus.CLAIMED
    copy_event.claimed_at = now
    return copy_event
