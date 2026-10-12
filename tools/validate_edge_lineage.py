#!/usr/bin/env python3
"""Static gate for authoritative strategy -> owned setup -> bridge lineage.

Complements (but does not replace) MetaEditor compilation and MT5 validation.
The gate checks stable contracts with whitespace-tolerant patterns so formatting
changes do not break CI while genuine setup-ownership regressions still fail.
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
    "EA/includes/Trading/StrategyTradeZone.mqh": [
        "BuildAuthoritativeStrategy",
        "SelectPeerStrategy",
        "BuildSMC",
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
        content = path.read_text(encoding="utf-8", errors="replace")
        texts[rel] = content
        for token in tokens:
            if token not in content:
                errors.append(f"{rel}: required contract token missing: {token}")

    trade_zone = texts.get("EA/includes/Trading/StrategyTradeZone.mqh", "")
    checks = [
        (
            r"SelectPeerStrategy\s*\(\s*forBuy\s*,\s*reasons\s*,\s*selected\s*,\s*selectedScore\s*\)",
            "TradeZone: authoritative strategy selection is not explicitly wired",
        ),
        (
            r"if\s*\(\s*selected\s*==\s*STRATEGY_SMC\s*\)\s*owned\s*=\s*BuildSMC\s*\(\s*forBuy\s*,\s*selectedScore\s*,\s*reasons\s*\)",
            "TradeZone: selected SMC strategy is not built through its owned builder",
        ),
        (
            r"else\s+if\s*\(\s*!\s*BuildNonSMC\s*\(\s*forBuy\s*,\s*selected\s*,\s*selectedScore\s*,\s*reasons\s*,\s*owned\s*\)\s*\)",
            "TradeZone: selected challenger strategy is not built through its owned builder",
        ),
        (
            r"if\s*\(\s*owned\.active\s*\)\s*\{(?:(?!\}).)*m_lastSetup\s*=\s*owned\s*;(?:(?!\}).)*return\s+owned\s*;",
            "TradeZone: only an active owned setup may cross the authoritative return boundary",
        ),
    ]
    for pattern, message in checks:
        if re.search(pattern, trade_zone, re.S) is None:
            errors.append(message)

    if "owned.reasons.selected_strategy=selected" not in trade_zone:
        errors.append("TradeZone: selected strategy provenance is not retained on the completed setup")
    if "m_lastSetup=owned;" not in trade_zone:
        errors.append("TradeZone: completed setup is not persisted through the owned last-setup path")
    if "return TradeSetup();" in trade_zone:
        errors.append("TradeZone: temporary TradeSetup return reintroduced in a fail-closed path")

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(f"\n{len(errors)} edge-lineage problem(s) found.", file=sys.stderr)
        return 1

    print("Edge-lineage validation: authoritative strategy selection, owned setup construction, thesis/provenance persistence, bridge contract, symmetric geometry validation, and fail-closed return path present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
