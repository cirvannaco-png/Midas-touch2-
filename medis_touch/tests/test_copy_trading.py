# ruff: noqa: I001

from datetime import datetime, timedelta, timezone

import pytest

from medis_touch.app.copy_trading import (
    AuthorizationError,
    CopyAccount,
    CopyEventStatus,
    CopyTradeEvent,
    Entitlement,
    EntitlementStatus,
    Subscription,
    SubscriptionStatus,
    account_scoped_idempotency_key,
    authorize_and_claim,
)
from medis_touch.app.models import OrderType, Signal, SignalStatus, TradeSetup


NOW = datetime(2026, 9, 14, 19, 0, tzinfo=timezone.utc)


def _fixtures(account_id: str = "acct-1"):
    subscription = Subscription(
        "sub-1", "user-1", "copy", "ammer_pay", "pay-1", SubscriptionStatus.ACTIVE,
        NOW - timedelta(days=1), NOW + timedelta(days=1),
    )
    entitlement = Entitlement(
        "ent-1", "user-1", "sub-1", EntitlementStatus.ACTIVE, True, True, True,
        NOW - timedelta(days=1), NOW + timedelta(days=1),
    )
    account = CopyAccount(account_id, "user-1", "simulated", f"broker-{account_id}", True, "fixed_risk_amount", 100.0)
    setup = TradeSetup(
        OrderType.BUY, 101.0, 100.0, 99.0, 98.5, 102.0, 103.0, 105.0, 0.8,
        NOW, NOW + timedelta(minutes=5),
    )
    signal = Signal(signal_id="sig-1", setup=setup, status=SignalStatus.ACTIVE)
    event = CopyTradeEvent(
        f"copy-{account_id}", signal.signal_id, "user-1", account_id, CopyEventStatus.PENDING,
        account_scoped_idempotency_key(signal_id=signal.signal_id, account_id=account_id), NOW,
    )
    return subscription, entitlement, account, signal, event


def test_copy_idempotency_is_scoped_per_account():
    assert account_scoped_idempotency_key(signal_id="sig-1", account_id="acct-a") != account_scoped_idempotency_key(signal_id="sig-1", account_id="acct-b")


def test_authorize_and_claim_rejects_stale_worker_claim():
    subscription, entitlement, account, signal, event = _fixtures()
    event.status = CopyEventStatus.CLAIMED
    with pytest.raises(AuthorizationError, match="not pending"):
        authorize_and_claim(subscription=subscription, entitlement=entitlement, account=account, signal=signal, copy_event=event, now=NOW)


def test_authorize_and_claim_rejects_wrong_idempotency_scope():
    subscription, entitlement, account, signal, event = _fixtures()
    event.idempotency_key = "copy:sig-1:account:another-account"
    with pytest.raises(AuthorizationError, match="idempotency scope"):
        authorize_and_claim(subscription=subscription, entitlement=entitlement, account=account, signal=signal, copy_event=event, now=NOW)
    assert event.status == CopyEventStatus.REJECTED


def test_same_signal_can_claim_for_two_independent_accounts():
    subscription_a, entitlement_a, account_a, signal, event_a = _fixtures("acct-a")
    subscription_b, entitlement_b, account_b, _, event_b = _fixtures("acct-b")
    authorize_and_claim(subscription=subscription_a, entitlement=entitlement_a, account=account_a, signal=signal, copy_event=event_a, now=NOW)
    authorize_and_claim(subscription=subscription_b, entitlement=entitlement_b, account=account_b, signal=signal, copy_event=event_b, now=NOW)
    assert event_a.status == CopyEventStatus.CLAIMED
    assert event_b.status == CopyEventStatus.CLAIMED
    assert event_a.idempotency_key != event_b.idempotency_key


def test_claim_rechecks_entitlement_at_execution_boundary():
    subscription, entitlement, account, signal, event = _fixtures()
    entitlement.status = EntitlementStatus.INACTIVE
    with pytest.raises(AuthorizationError, match="re-authorization"):
        authorize_and_claim(subscription=subscription, entitlement=entitlement, account=account, signal=signal, copy_event=event, now=NOW)
    assert event.status == CopyEventStatus.REJECTED
