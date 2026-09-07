from dataclasses import dataclass
from enum import Enum


class Broker(str, Enum):
    EXNESS = "Exness"
    PEPPERSTONE = "Pepperstone"
    HFM = "HFM"
    IC_MARKETS = "IC Markets"
    XM = "XM"
    IG = "IG"
    OANDA = "OANDA"
    AVATRADE = "AvaTrade"
    FXTM = "FXTM"
    FP_MARKETS = "FP Markets"


@dataclass(frozen=True)
class BrokerCapability:
    broker: Broker
    mt5: bool = True
    copy_trading: bool = True


ALIASES = {
    "pepperdine": Broker.PEPPERSTONE,
    "pepperstone": Broker.PEPPERSTONE,
    "icmarkets": Broker.IC_MARKETS,
    "ic markets": Broker.IC_MARKETS,
    "ava trade": Broker.AVATRADE,
    "fpmarkets": Broker.FP_MARKETS,
}

REGISTRY = {b.value.lower(): BrokerCapability(b) for b in Broker}


def normalize_broker(value: str | Broker) -> Broker | None:
    if isinstance(value, Broker):
        return value
    key = str(value).strip().lower()
    if key in ALIASES:
        return ALIASES[key]
    for broker in Broker:
        if key == broker.value.lower():
            return broker
    return None


def capability(value: str | Broker) -> BrokerCapability | None:
    broker = normalize_broker(value)
    return BrokerCapability(broker) if broker is not None else None
