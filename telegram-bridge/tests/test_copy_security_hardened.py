from datetime import datetime, timedelta, timezone

from app.domain.brokers import Broker, normalize_broker
from app.domain.copy import CopyRequest, authorize_copy


def base(**overrides):
    value = dict(
        broker=Broker.EXNESS,
        symbol="XAUUSD",
        direction="BUY",
        risk_percent=0.5,
        account_equity=1000,
        subscription_entitled=True,
        copy_authorized=True,
        portfolio_admitted=True,
        signal_created_at=datetime.now(timezone.utc),
    )
    value.update(overrides)
    return CopyRequest(**value)


def test_user_selected_risk_is_accepted_when_within_bounds():
    assert authorize_copy(base(risk_percent=1.5))[0]


def test_excessive_user_risk_is_rejected():
    ok, reason = authorize_copy(base(risk_percent=2.1))
    assert not ok and reason == "RISK_OUT_OF_BOUNDS"


def test_subscription_does_not_imply_copy_authorization():
    ok, reason = authorize_copy(base(copy_authorized=False))
    assert not ok and reason == "COPY_NOT_EXPLICITLY_ENABLED"


def test_stale_signal_is_rejected():
    created = datetime.now(timezone.utc) - timedelta(minutes=5, seconds=1)
    ok, reason = authorize_copy(base(signal_created_at=created))
    assert not ok and reason == "STALE_SIGNAL"


def test_pepperdine_alias_is_safe():
    assert normalize_broker("Pepperdine") is Broker.PEPPERSTONE


def test_unknown_broker_fails_closed():
    ok, reason = authorize_copy(base(broker="Unknown Broker"))
    assert not ok and reason == "UNSUPPORTED_BROKER"


def test_portfolio_gate_fails_closed():
    ok, reason = authorize_copy(base(portfolio_admitted=False))
    assert not ok and reason == "PORTFOLIO_NOT_ADMITTED"
