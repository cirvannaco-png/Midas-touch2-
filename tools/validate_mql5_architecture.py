#!/usr/bin/env python3
"""Static architecture and compile-safety gate for the MQL5 tree.

MetaEditor remains the authoritative MQL5 compiler. This gate catches
structural failures Linux CI can prove: unresolved/case-mismatched includes,
include cycles, duplicate type definitions, key interface arity drift,
legacy decision-authority duplication, and multi-trade placement/gates.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "EA"
INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"', re.MULTILINE)
CLASS_RE = re.compile(r'^\s*class\s+([A-Za-z_]\w*)\b[^;{]*\{', re.MULTILINE)
STRUCT_RE = re.compile(r'^\s*struct\s+([A-Za-z_]\w*)\b', re.MULTILINE)
ENUM_RE = re.compile(r'^\s*enum\s+([A-Za-z_]\w*)\b', re.MULTILINE)


def read(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            pass
    return path.read_text(encoding="utf-8", errors="replace")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def normalize_include(src: Path, target: str) -> Path:
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
            if state.get(nxt, 0) == 0:
                dfs(nxt)
            elif state.get(nxt) == 1:
                i = stack.index(nxt)
                cycle = stack[i:] + [nxt]
                if cycle not in cycles:
                    cycles.append(cycle)
        stack.pop()
        state[node] = 2

    for node in graph:
        if state.get(node, 0) == 0:
            dfs(node)
    return cycles


def check_includes(
    sources: list[Path],
    graph: dict[str, list[str]],
    errors: list[str],
) -> int:
    checked = 0
    all_paths = {p.resolve() for p in sources}

    for src in sources:
        src_key = rel(src)
        deps: list[str] = []
        for target in INCLUDE_RE.findall(read(src)):
            checked += 1
            resolved = normalize_include(src, target)
            if not resolved.exists():
                errors.append(f'{src_key}: missing #include "{target}"')
                continue
            try:
                target_key = rel(resolved)
            except ValueError:
                errors.append(f'{src_key}: #include escapes EA/: "{target}"')
                continue
            if resolved not in all_paths:
                errors.append(f'{src_key}: include resolves outside source set: "{target}"')
                continue

            # Explicit case comparison keeps this invariant portable across
            # case-sensitive Linux and case-insensitive developer workstations.
            declared = src.parent / target
            actual_parts = resolved.parts
            declared_parts = declared.parts
            if len(actual_parts) == len(declared_parts):
                for actual, expected in zip(actual_parts, declared_parts):
                    if actual != expected:
                        errors.append(f'{src_key}: #include case mismatch "{target}"')
                        break

            deps.append(target_key)
        graph[src_key] = deps

    return checked


def collect_duplicates(sources: list[Path], errors: list[str]) -> None:
    for kind, pattern in (
        ("class", CLASS_RE),
        ("struct", STRUCT_RE),
        ("enum", ENUM_RE),
    ):
        names: dict[str, list[str]] = {}
        for src in sources:
            for name in pattern.findall(read(src)):
                names.setdefault(name, []).append(rel(src))
        for name, files in sorted(names.items()):
            if len(files) > 1:
                errors.append(f"duplicate {kind} definition {name}: {', '.join(files)}")


INTERFACE_CONTRACTS = {
    ("includes/Trading/StrategyTradeZone.mqh", "CTradeDecision"): {
        "Init": 11,
        "GenerateBuySetup": 0,
        "GenerateSellSetup": 0,
    },
    ("includes/Portfolio/MultiTradeEngine.mqh", "CMultiTradeEngine"): {
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
            defs = re.findall(
                rf"\b{re.escape(class_name)}::{re.escape(method)}\s*\(([^)]*)\)",
                text,
            )
            inline = re.findall(
                rf"\b{re.escape(method)}\s*\(([^)]*)\)\s*\{{",
                text,
            )
            if not defs and not inline:
                errors.append(f"{file_name}: {class_name}::{method} implementation is missing")
                continue
            actual = arg_count(defs[0] if defs else inline[0])
            if actual != expected_arity:
                errors.append(
                    f"{file_name}: {class_name}::{method} expects {expected_arity} "
                    f"arguments, implementation has {actual}"
                )


def check_architecture(
    by_rel: dict[str, str], sources: list[Path], errors: list[str]
) -> None:
    legacy = by_rel.get("includes/Trading/TradeZone.mqh", "")
    strategy = by_rel.get("includes/Trading/StrategyTradeZone.mqh", "")
    risk = by_rel.get("includes/Trading/RiskEngine.mqh", "")
    multi = by_rel.get("includes/Portfolio/MultiTradeEngine.mqh", "")
    orders = by_rel.get("includes/Execution/OrderManager.mqh", "")
    ea = by_rel.get("MedisTouch_v2.8.mq5", "")

    if "class CTradeDecision" in legacy:
        errors.append("TradeZone.mqh still defines CTradeDecision; StrategyTradeZone must be the single authority")
    if '#include "StrategyTradeZone.mqh"' not in legacy:
        errors.append("TradeZone.mqh compatibility shim no longer forwards to StrategyTradeZone.mqh")
    if '#include "TradeZone.mqh"' in risk:
        errors.append("RiskEngine.mqh still depends on legacy TradeZone.mqh")
    if "class CTradeDecision" not in strategy:
        errors.append("StrategyTradeZone.mqh no longer defines the authoritative CTradeDecision")
    if '#include "../Monitoring/ProductionMonitor.mqh"' not in orders:
        errors.append("OrderManager.mqh must explicitly include ProductionMonitor.mqh")

    # Direct consumers must depend on the authoritative router, not the
    # compatibility shim.
    for src in sources:
        r = rel(src)
        if r == "includes/Trading/TradeZone.mqh":
            continue
        if re.search(r'#include\s+"(?:[^"]*/)?TradeZone\.mqh"', read(src)):
            errors.append(
                f"{r}: direct include of legacy TradeZone.mqh is forbidden; "
                "use StrategyTradeZone.mqh"
            )

    # Multi-trade is portfolio policy, not order submission or decision logic.
    forbidden = (
        "OrderManager.mqh",
        "RiskEngine.mqh",
        "DecisionEngine.mqh",
        "BrokerAdapter.mqh",
    )
    for token in forbidden:
        if token in multi:
            errors.append(f"Portfolio/MultiTradeEngine.mqh is coupled directly to {token}")

    gates = (
        "setup.calibration_has_enough_data",
        "setup.calibration_sample<m_minCalibrationSample",
        "MathIsValidNumber(setup.calibrated_probability)",
        "setup.confidence<m_minRawConfidence",
        "MathIsValidNumber(setup.confidence)",
        "setup.calibrated_probability<m_dualProbability",
        "m_requireHedging && !IsHedgingAccount()",
        "fractionTotal-1.0",
    )
    for gate in gates:
        if gate not in multi:
            errors.append(f"MultiTradeEngine.mqh missing invariant: {gate}")

    call_order = (
        "g_router.Decide(chosen)",
        "g_multiTrade.Build(decision.setup,availableSlots,plan)",
        "g_portfolio.AllowNewTradeBatch",
        "g_orders.Submit(legDecision,legLots[leg],InpUseMarketOrders,maxDeviation,ticket,leg)",
    )
    positions = [ea.find(token) for token in call_order]
    for token, position in zip(call_order, positions):
        if position < 0:
            errors.append(f"EA missing required execution-stage call: {token}")
    present = [p for p in positions if p >= 0]
    if len(present) == len(call_order) and present != sorted(present):
        errors.append(
            "EA execution order violated: decision -> multi-trade plan -> "
            "portfolio gate -> order submission"
        )

    if "decision.action==POLICY_EXECUTE_ONLY||decision.action==POLICY_EXECUTE_AND_SIGNAL" not in ea:
        errors.append("EA no longer restricts multi-trade planning to executable decisions")


def main() -> int:
    if not ROOT.is_dir():
        print(f"error: missing EA directory: {ROOT}", file=sys.stderr)
        return 1

    sources = sorted(
        p for p in ROOT.rglob("*") if p.suffix.lower() in {".mq5", ".mqh"}
    )
    if not sources:
        print("error: no MQL5 sources found", file=sys.stderr)
        return 1

    errors: list[str] = []
    graph: dict[str, list[str]] = {}
    checked = check_includes(sources, graph, errors)
    collect_duplicates(sources, errors)
    check_interfaces(sources, errors)
    by_rel = {rel(p): read(p) for p in sources}
    check_architecture(by_rel, sources, errors)

    cycles = find_cycles(graph)
    for cycle in cycles:
        errors.append("include cycle: " + " -> ".join(cycle))

    print(
        f"MQL5 architecture validation: {len(sources)} source file(s), "
        f"{checked} include(s), {len(cycles)} cycle(s)"
    )
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(f"\n{len(errors)} architecture problem(s) found.", file=sys.stderr)
        return 1

    print("MQL5 architecture validation: clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
