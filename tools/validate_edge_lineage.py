#!/usr/bin/env python3
"""Static gate for the authoritative strategy -> setup lineage.

This is intentionally complementary to MetaEditor: it cannot type-check
MQL5, but it can fail CI when a future refactor removes one of the explicit
contracts that make the strategy-selection path auditable.
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
        "BuildAuthoritativeStrategy",
        "GenerateBuySetup",
        "GenerateSellSetup",
        "selected_strategy",
    ],
    "EA/includes/Decision/DecisionEngine.mqh": [
        "ValidateSetupGeometry",
        "setup.invalidation",
        "setup.stop_loss",
    ],
}


def main() -> int:
    errors: list[str] = []
    for rel, tokens in REQUIRED.items():
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"missing required file: {rel}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in tokens:
            if token not in text:
                errors.append(f"{rel}: required contract token missing: {token}")

    trade_zone = (ROOT / "EA/includes/Trading/TradeZone.mqh").read_text(encoding="utf-8", errors="replace")
    if "if(owned.active)" not in trade_zone:
        errors.append("TradeZone: authoritative strategy path no longer requires an owned active setup")
    if re.search(r"if\s*\(owned\.active\).*?return owned;", trade_zone, re.S) is None:
        errors.append("TradeZone: owned strategy setup is not returned explicitly")

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(f"\n{len(errors)} edge-lineage problem(s) found.", file=sys.stderr)
        return 1

    print("Edge-lineage validation: strategy authority, owned builders, setup geometry, and fail-closed return path present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
