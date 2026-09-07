from dataclasses import dataclass
from datetime import datetime, timezone

from .brokers import Broker, normalize_broker

MAX_RISK_PERCENT = 2.0
MIN_RISK_PERCENT = 0.1
MAX_SIGNAL_AGE_SECONDS = 300


@dataclass(frozen=True)
class CopyRequest:
    broker: str | Broker
    symbol: str
    direction: str
    risk_percent: float
    account_equity: float
    subscription_entitled: bool
    copy_authorized: bool
    portfolio_admitted: bool
    signal_created_at: datetime | None = None


def signal_age_seconds(created_at: datetime | None, now: datetime | None = None) -> float | None:
    if created_at is None:
        return None
    now = now or datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return max(0.0, (now - created_at).total_seconds())


def authorize_copy(request: CopyRequest, now: datetime | None = None) -> tuple[bool, str]:
    broker = normalize_broker(request.broker)
    if not request.subscription_entitled:
        return False, "SUBSCRIPTION_NOT_ENTITLED"
    if not request.copy_authorized:
        return False, "COPY_NOT_EXPLICITLY_ENABLED"
    if broker is None:
        return False, "UNSUPPORTED_BROKER"
    if not request.symbol.strip():
        return False, "INVALID_SYMBOL"
    if request.direction.upper() not in {"BUY", "SELL"}:
        return False, "INVALID_DIRECTION"
    age = signal_age_seconds(request.signal_created_at, now)
    if age is not None and age > MAX_SIGNAL_AGE_SECONDS:
        return False, "STALE_SIGNAL"
    if request.account_equity <= 0:
        return False, "INVALID_ACCOUNT_EQUITY"
    if request.risk_percent < MIN_RISK_PERCENT or request.risk_percent > MAX_RISK_PERCENT:
        return False, "RISK_OUT_OF_BOUNDS"
    if not request.portfolio_admitted:
        return False, "PORTFOLIO_NOT_ADMITTED"
    return True, "AUTHORIZED"
