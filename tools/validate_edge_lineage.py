#!/usr/bin/env python3
"""Static gate for the authoritative strategy -> setup -> bridge lineage.

This is intentionally complementary to MetaEditor: it cannot type-check
MQL5 or execute the service, but it can fail CI when a future refactor
removes explicit contracts that make the strategy and signal path auditable.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = {
    "EA/includes/Strategies/StrategySelector.mqh": [
        "REGIME_UNDEFINED",
        "STRATEGY_MOMENTUM_BREAKOUT",
        "STRATEGY_MEAN_REVERSION",
        "STRATEGY_KEY_LEVEL",
        "m_minSelectionScore",
    ],
    "EA/includes/Trading/StrategySetupBuilders.mqh": [
        "BuildMomentum",
        "BuildMeanReversion",
        "BuildKeyLevel",
        "invalidation",
        "ValidateCandidate",
    ],
    "EA/includes/Trading/TradeZone.mqh": [
        '#include "StrategyTradeZone.mqh"',
    ],
    "EA/includes/Trading/StrategyTradeZone.mqh": [
        "PopulateStrategyReads",
        "SelectPeerStrategy",
        "BuildNonSMC",
        "GenerateBuySetup",
        "GenerateSellSetup",
        "selected_strategy",
    ],
    "EA/includes/Decision/DecisionEngine.mqh": [
        "ValidateSetupGeometry",
        "setup.invalidation",
        "setup.stop_loss",
    ],
    "EA/includes/Decision/DecisionStore.mqh": [
        "rec.setup.invalidation",
        "rec.setup.reasons.selected_strategy",
        "Legacy decisions predate the first-class thesis boundary",
    ],
    "EA/includes/Signals/SignalPublisher.mqh": [
        "invalidation",
        "final_tp",
        "selected_strategy",
        "EnumToString(r.selected_strategy)",
    ],
    "telegram-bridge/app/routes.py": [
        "invalidation: float | None",
        "final_tp: float | None",
        "strategy: str | None",
        "invalidation=payload.invalidation",
        "final_tp=payload.final_tp",
        "strategy=payload.strategy",
        "invalidation=s.invalidation",
        "final_tp=s.final_tp",
        "strategy=s.strategy",
    ],
    "telegram-bridge/app/validator.py": [
        "thesis invalidation must be below entry price",
        "protective stop must be below thesis invalidation",
        "final TP must be above TP2",
        "thesis invalidation must be above entry price",
        "protective stop must be above thesis invalidation",
        "final TP must be below TP2",
    ],
    "telegram-bridge/app/models.py": [
        "invalidation = Column(Float, nullable=True)",
        "final_tp = Column(Float, nullable=True)",
        "strategy = Column(String(64), nullable=True, index=True)",
    ],
}


def main() -> int:
    errors: list[str] = []
    texts: dict[str, str] = {}
    for rel, tokens in REQUIRED.items():
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"missing required file: {rel}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        texts[rel] = text
        for token in tokens:
            if token not in text:
                errors.append(f"{rel}: required contract token missing: {token}")

    strategy_router = texts.get("EA/includes/Trading/StrategyTradeZone.mqh", "")
    if "if(!built)return false;" not in strategy_router:
        errors.append("StrategyTradeZone: non-SMC builders are not fail-closed")
    if "if(!out.active){ZeroMemory(out);m_lastSetup=out;return out;}" not in strategy_router:
        errors.append("StrategyTradeZone: inactive strategy setup is not returned fail-closed")
    if "return TradeSetup();" in strategy_router:
        errors.append("StrategyTradeZone: temporary TradeSetup return reintroduced in the strategy path")
    if "EA/includes/Trading/TradeZone.mqh" not in texts:
        errors.append("TradeZone compatibility shim disappeared; legacy includes must remain resolvable")
    elif "class CTradeDecision" in texts["EA/includes/Trading/TradeZone.mqh"]:
        errors.append("TradeZone: legacy class CTradeDecision definition still exists; duplicate strategy authority remains")

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(f"\n{len(errors)} edge-lineage problem(s) found.", file=sys.stderr)
        return 1

    print("Edge-lineage validation: strategy authority, setup ownership, durable thesis/provenance, bridge persistence, symmetric geometry validation, and fail-closed return path present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
