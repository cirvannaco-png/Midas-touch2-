from dataclasses import dataclass

from app.domain.copy import CopyRequest, authorize_copy


@dataclass(frozen=True)
class CopyAuthorizationContext:
    broker: object
    symbol: str
    direction: str
    risk_percent: float
    account_equity: float
    subscription_entitled: bool
    copy_authorized: bool
    portfolio_admitted: bool
    signal_created_at: object | None = None


class CopyService:
    def authorize(self, context: CopyAuthorizationContext):
        return authorize_copy(
            CopyRequest(
                broker=context.broker,
                symbol=context.symbol,
                direction=context.direction,
                risk_percent=context.risk_percent,
                account_equity=context.account_equity,
                subscription_entitled=context.subscription_entitled,
                copy_authorized=context.copy_authorized,
                portfolio_admitted=context.portfolio_admitted,
                signal_created_at=context.signal_created_at,
            )
        )
