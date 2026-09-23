#!/usr/bin/env python3
"""Architecture and compile-safety checks for the authoritative MQL5 tree.

This is deliberately static. MetaEditor remains the authoritative MQL5
compiler; this gate catches structural failures that Linux CI can still see:
missing/case-mismatched includes, include cycles, duplicate class/struct
definitions, missing key method implementations, interface arity drift, and
the high-probability multi-trade placement/gating invariants.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "EA"
INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"', re.MULTILINE)
CLASS_RE = re.compile(r'^\s*class\s+([A-Za-z_]\w*)\b', re.MULTILINE)
STRUCT_RE = re.compile(r'^\s*struct\s+([A-Za-z_]\w*)\b', re.MULTILINE)


def read(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            pass
    return path.read_text(encoding="utf-8", errors="replace")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def normalized_include(src: Path, target: str) -> Path:
    return (src.parent / target).resolve()


def arg_count(signature: str) -> int:
    text = signature.strip()
    if not text:
        return 0
    depth = 0
    count = 1
    for ch in text:
        if ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            count += 1
    return count


def find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    state: dict[str, int] = {}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def dfs(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for nxt in graph.get(node, []):
            if nxt not in graph:
                continue
            if state.get(nxt, 0) == 0:
                dfs(nxt)
            elif state.get(nxt) == 1:
                try:
                    i = stack.index(nxt)
                    cycle = stack[i:] + [nxt]
                except ValueError:
                    cycle = [nxt, node, nxt]
                if cycle not in cycles:
                    cycles.append(cycle)
        stack.pop()
        state[node] = 2

    for node in graph:
        if state.get(node, 0) == 0:
            dfs(node)
    return cycles


def check_includes(sources: list[Path], graph: dict[str, list[str]], errors: list[str]) -> int:
    checked = 0
    for src in sources:
        src_key = rel(src)
        deps: list[str] = []
        for target in INCLUDE_RE.findall(read(src)):
            checked += 1
            resolved = normalized_include(src, target)
            if not resolved.exists():
                errors.append(f'{src_key}: missing #include "{target}"')
                continue
            try:
                target_key = rel(resolved)
            except ValueError:
                errors.append(f'{src_key}: #include escapes EA/: "{target}"')
                continue
            deps.append(target_key)
        graph[src_key] = deps
    return checked


def check_duplicates(sources: list[Path], errors: list[str]) -> None:
    classes: dict[str, list[str]] = {}
    structs: dict[str, list[str]] = {}
    for src in sources:
        text = read(src)
        for name in CLASS_RE.findall(text):
            classes.setdefault(name, []).append(rel(src))
        for name in STRUCT_RE.findall(text):
            structs.setdefault(name, []).append(rel(src))

    for name, files in sorted(classes.items()):
        if len(files) > 1:
            errors.append(f"duplicate class definition {name}: {', '.join(files)}")
    for name, files in sorted(structs.items()):
        if len(files) > 1:
            errors.append(f"duplicate struct definition {name}: {', '.join(files)}")


INTERFACE_CONTRACTS = {
    ("includes/Trading/StrategyTradeZone.mqh", "CTradeDecision"): {
        "Init": 11,
        "GenerateBuySetup": 0,
        "GenerateSellSetup": 0,
    },
    ("includes/Execution/MultiTradeEngine.mqh", "CMultiTradeEngine"): {
        "Init": 11,
        "Build": 3,
        "IsHedgingAccount": 0,
    },
    ("includes/Trading/RiskEngine.mqh", "CRiskEngine"): {
        "ValidateSetup": 4,
        "CalculateLotSize": 8,
        "RiskAmountForLots": 4,
    },
    ("includes/Decision/DecisionEngine.mqh", "CDecisionEngine"): {
        "Init": 7,
        "SeedNextId": 1,
        "Decide": 1,
    },
    ("includes/Execution/OrderManager.mqh", "COrderManager"): {
        "Init": 3,
        "Submit": 6,
        "MarkFilledFromPending": 3,
        "DecisionIdForTicket": 1,
        "HasLiveTradeForDecision": 2,
    },
}


def check_interfaces(sources: list[Path], errors: list[str]) -> None:
    by_rel = {rel(p): read(p) for p in sources}
    for (file_name, class_name), methods in INTERFACE_CONTRACTS.items():
        text = by_rel.get(file_name, "")
        if not text:
            errors.append(f"missing interface source: {file_name}")
            continue
        if not re.search(rf"\bclass\s+{re.escape(class_name)}\b", text):
            errors.append(f"{file_name}: class {class_name} is missing")
            continue
        for method, expected_arity in methods.items():
            defs = re.findall(rf"\b{re.escape(class_name)}::{re.escape(method)}\s*\(([^)]*)\)", text)
            if not defs:
                errors.append(f"{file_name}: {class_name}::{method} implementation is missing")
                continue
            actual = arg_count(defs[0])
            if actual != expected_arity:
                errors.append(
                    f"{file_name}: {class_name}::{method} expects {expected_arity} arguments, "
                    f"implementation has {actual}"
                )


def check_architecture(by_rel: dict[str, str], errors: list[str]) -> None:
    trade_zone = by_rel.get("includes/Trading/TradeZone.mqh", "")
    risk = by_rel.get("includes/Trading/RiskEngine.mqh", "")
    strategy = by_rel.get("includes/Trading/StrategyTradeZone.mqh", "")
    multi = by_rel.get("includes/Execution/MultiTradeEngine.mqh", "")
    ea = by_rel.get("MedisTouch_v2.8.mq5", "")

    if "class CTradeDecision" in trade_zone:
        errors.append("TradeZone.mqh still defines CTradeDecision; StrategyTradeZone must be the single authority")
    if '#include "StrategyTradeZone.mqh"' not in trade_zone:
        errors.append("TradeZone.mqh compatibility shim no longer forwards to StrategyTradeZone.mqh")
    if '#include "TradeZone.mqh"' in risk:
        errors.append("RiskEngine.mqh still depends on legacy TradeZone.mqh")
    if "class CTradeDecision" not in strategy:
        errors.append("StrategyTradeZone.mqh no longer defines the authoritative CTradeDecision")

    # The multi-trade planner belongs to the execution layer and should stay
    # pure: it must not reach into order submission or portfolio/risk services.
    forbidden = (
        "OrderManager.mqh",
        "PortfolioManager.mqh",
        "RiskEngine.mqh",
        "DecisionEngine.mqh",
    )
    for token in forbidden:
        if token in multi:
            errors.append(f"MultiTradeEngine.mqh is coupled directly to {token}; keep execution planning independent")

    gates = (
        "calibration_has_enough_data",
        "calibration_sample<m_minCalibrationSample",
        "setup.confidence<m_minRawConfidence",
        "setup.calibrated_probability<m_dualProbability",
        "m_requireHedging && !IsHedgingAccount()",
    )
    for gate in gates:
        if gate not in multi:
            errors.append(f"MultiTradeEngine.mqh missing high-probability dual-trade gate: {gate}")

    call_order = (
        "g_router.Decide(chosen)",
        "g_multiTrade.Build(decision.setup,availableSlots,plan)",
        "g_portfolio.AllowNewTradeBatch",
        "g_orders.Submit(legDecision,legLots[leg],InpUseMarketOrders,maxDeviation,ticket,leg)",
    )
    positions = [ea.find(token) for token in call_order]
    if any(i < 0 for i in positions):
        for token, pos in zip(call_order, positions):
            if pos < 0:
                errors.append(f"EA missing required execution-stage call: {token}")
    elif positions != sorted(positions):
        errors.append("EA execution order is invalid: router -> multi-trade plan -> portfolio gate -> order submission must remain monotonic")

    if 'if(decision.action==POLICY_EXECUTE_ONLY||decision.action==POLICY_EXECUTE_AND_SIGNAL)' not in ea:
        errors.append("Multi-trade planning is no longer restricted to executable decisions")


def main() -> int:
    if not ROOT.is_dir():
        print(f"error: missing EA directory: {ROOT}", file=sys.stderr)
        return 1

    sources = sorted(p for p in ROOT.rglob("*") if p.suffix in {".mq5", ".mqh"})
    if not sources:
        print("error: no MQL5 sources found", file=sys.stderr)
        return 1

    errors: list[str] = []
    graph: dict[str, list[str]] = {}
    include_count = check_includes(sources, graph, errors)
    check_duplicates(sources, errors)
    check_interfaces(sources, errors)
    by_rel = {rel(p): read(p) for p in sources}
    check_architecture(by_rel, errors)

    cycles = find_cycles(graph)
    for cycle in cycles:
        errors.append("include cycle: " + " -> ".join(cycle))

    print(
        f"MQL5 architecture validation: {len(sources)} source file(s), "
        f"{include_count} local include(s), {len(cycles)} cycle(s) detected"
    )
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(f"\n{len(errors)} architecture problem(s) found.", file=sys.stderr)
        return 1

    print("Architecture validation: include graph, duplicate definitions, interface arity, strategy authority, and high-probability execution invariants are clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
