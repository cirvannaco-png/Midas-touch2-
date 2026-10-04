#!/usr/bin/env python3
"""Architecture and compile-safety checks for the authoritative MQL5 tree.

This is deliberately static. MetaEditor remains the authoritative MQL5
compiler; this gate catches structural failures that Linux CI can still see:
missing/case-mismatched includes, include cycles, duplicate class/struct
definitions, missing key method implementations, interface arity drift, and
the high-probability portfolio multi-trade placement/gating invariants for the current Midas Touch tree.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "EA"
INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"', re.MULTILINE)
CLASS_RE = re.compile(r'^\s*class\s+([A-Za-z_]\w*)\b[^;{]*\{', re.MULTILINE)
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
            defs = re.findall(rf"\b{re.escape(class_name)}::{re.escape(method)}\s*\(([^)]*)\)", text)
            inline = re.findall(rf"\b{re.escape(method)}\s*\(([^)]*)\)\s*{{", text)
            if not defs and not inline:
                errors.append(f"{file_name}: {class_name}::{method} implementation is missing")
                continue
            actual = arg_count(defs[0] if defs else inline[0])
            if actual != expected_arity:
                errors.append(
                    f"{file_name}: {class_name}::{method} expects {expected_arity} arguments, "
                    f"implementation has {actual}"
                )


def check_architecture(by_rel: dict[str, str], errors: list[str]) -> None:
    trade_zone = by_rel.get("includes/Trading/TradeZone.mqh", "")
    risk = by_rel.get("includes/Trading/RiskEngine.mqh", "")
    strategy = by_rel.get("includes/Trading/StrategyTradeZone.mqh", "")
    quality = by_rel.get("includes/Decision/DecisionQuality.mqh", "")
    config = by_rel.get("includes/Core/Config.mqh", "")
    fvg = by_rel.get("includes/SmartMoney/FVG.mqh", "")
    inducement = by_rel.get("includes/SmartMoney/Inducement.mqh", "")
    environment_memory = by_rel.get("includes/Trading/EnvironmentStrategyMemory.mqh", "")
    outcome_live = by_rel.get("includes/Trading/OutcomeTrackerLive.mqh", "")
    outcome_backtest = by_rel.get("includes/Trading/OutcomeTracker.mqh", "")
    decision_engine = by_rel.get("includes/Decision/DecisionEngine.mqh", "")
    dynamic_stop = by_rel.get("includes/Execution/DynamicStopEngine.mqh", "")
    publisher = by_rel.get("includes/Signals/SignalPublisher.mqh", "")
    multi = by_rel.get("includes/Portfolio/MultiTradeEngine.mqh", "")
    ea = by_rel.get("MedisTouch_v2.8.mq5", "")
    strategy_builders = by_rel.get("includes/Trading/StrategySetupBuilders.mqh", "")
    momentum = by_rel.get("includes/Strategies/MomentumBreakout.mqh", "")
    mean_reversion = by_rel.get("includes/Strategies/MeanReversion.mqh", "")
    key_level = by_rel.get("includes/Strategies/KeyLevelReaction.mqh", "")
    regime = by_rel.get("includes/Regime/RegimeDetector.mqh", "")
    market_phase = by_rel.get("includes/SmartMoney/MarketPhase.mqh", "")
    liquidity = by_rel.get("includes/SmartMoney/Liquidity.mqh", "")
    fvg_engine = by_rel.get("includes/SmartMoney/FVG.mqh", "")
    value_area = by_rel.get("includes/SmartMoney/ValueAreaEngine.mqh", "")

    if "class CTradeDecision" in trade_zone:
        errors.append("TradeZone.mqh still defines CTradeDecision; StrategyTradeZone must be the single authority")
    if '#include "StrategyTradeZone.mqh"' not in trade_zone:
        errors.append("TradeZone.mqh compatibility shim no longer forwards to StrategyTradeZone.mqh")
    if '#include "TradeZone.mqh"' in risk:
        errors.append("RiskEngine.mqh still depends on legacy TradeZone.mqh")
    if "class CTradeDecision" not in strategy:
        errors.append("StrategyTradeZone.mqh no longer defines the authoritative CTradeDecision")
    if '#include "../Decision/DecisionQuality.mqh"' not in strategy:
        errors.append("StrategyTradeZone.mqh is missing hierarchical DecisionQuality integration")
    for token in ("class CStructuralValidator", "class CTradeQualityFirewall", "DECISION_TRADE", "DECISION_WAIT", "DECISION_REJECT"):
        if token not in quality:
            errors.append(f"DecisionQuality.mqh missing required architecture contract: {token}")
    for token in ("ENUM_STRUCTURAL_STATE", "ENUM_DECISION_STATE", "ENUM_RISK_CLASS", "ENUM_SETUP_LIFECYCLE", "ENUM_FIREWALL_LAYER"):
        if token not in config:
            errors.append(f"Config.mqh missing decision architecture enum: {token}")
    if "FVG_INVALIDATED" not in fvg or "cd.close < zone.bottom" not in fvg or "cd.close > zone.top" not in fvg:
        errors.append("FVG lifecycle is missing symmetric adverse-close invalidation")
    for token in ("ENUM_LIQUIDITY_SCOPE", "ENUM_LIQUIDITY_ARCHETYPE", "STRUCTURE_STAGE_FVG_NONCAUSAL", "SETUP_FILLED", "SETUP_MANAGED", "SETUP_CLOSED"):
        if token not in config:
            errors.append(f"Config.mqh missing lifecycle/provenance contract: {token}")
    if "Never compare raw bar indices across those series" not in strategy or "PeriodSeconds(m_fvgCtx.candles.Timeframe())" not in strategy or "zone.time<=ind.bosTime" not in strategy:
        errors.append("StrategyTradeZone.mqh still permits cross-timeframe causal FVG comparison by raw bar index")
    for token in ("RiskClassSizingMultiplier", "RISK_CLASS_HIGH_CONVICTION", "RISK_CLASS_STANDARD", "RISK_CLASS_MINIMAL", "expected_return_r"):
        if token not in config:
            errors.append(f"Config.mqh missing risk-class sizing contract: {token}")
    if "IsTighter(isBuy,candidate,currentSL)" not in dynamic_stop:
        errors.append("DynamicStopEngine.mqh missing immutable-tightening-only stop invariant")
    partial_zone = by_rel.get("includes/Trading/OutcomeTracker.mqh", "")
    if "void COutcomeTracker::ApplyPartial" in partial_zone:
        partial_section = partial_zone[partial_zone.index("void COutcomeTracker::ApplyPartial"):partial_zone.index("bool COutcomeTracker::IntrabarReplayGeneric")]
        if "SETUP_CLOSED" in partial_section:
            errors.append("OutcomeTracker ApplyPartial incorrectly closes the setup lifecycle")
        if "SETUP_MANAGED" not in partial_section:
            errors.append("OutcomeTracker ApplyPartial missing managed lifecycle transition")
    if "void COutcomeTracker::FinalizeExit" in partial_zone:
        if "p.setup.setup_lifecycle=SETUP_CLOSED" not in partial_zone:
            errors.append("OutcomeTracker FinalizeExit missing closed lifecycle transition")
    if "p.setup.setup_lifecycle=SETUP_CLOSED" not in outcome_live:
        errors.append("OutcomeTrackerLive Finalize missing closed lifecycle transition")
    for token in ("g_logger.LogSetup(buySetup", "g_logger.LogSetup(sellSetup", "REJECT/WAIT is first-class telemetry"):
        if token not in ea:
            errors.append(f"EA missing first-class reject/wait telemetry: {token}")
    if "TradeSetup CTradeDecision::BuildRejected" not in strategy:
        errors.append("StrategyTradeZone.mqh missing first-class rejected setup constructor")
    logger = by_rel.get("includes/Core/SignalLogger.mqh", "")
    for token in ("DecisionState", "BlockingLayer", "DecisionReason", "QualityScore", "Lifecycle", "ExpectedReturnR", "RegimeID"):
        if token not in logger:
            errors.append(f"SignalLogger.mqh missing decision provenance column: {token}")
    for token in ("liquidity_scope", "liquidity_archetype", "bos_distance_atr", "bos_age_bars", "fvg_causal", "invalidation_distance_atr", "expected_return_r", "regime_id"):
        if token not in publisher:
            errors.append(f"SignalPublisher.mqh missing structural decision provenance field: {token}")
    for token in ("structureType", "liquidityPoolPrice", "sweepPenetrationATR", "sweepRejectionRatio", "sweepFollowThrough", "displacementATR"):
        if token not in inducement:
            errors.append(f"Inducement.mqh missing structural provenance telemetry: {token}")
    if "IsDegraded(const EnvironmentMemoryEvidence" not in environment_memory:
        errors.append("EnvironmentStrategyMemory.mqh missing explicit degraded-evidence predicate")
    for token in ("maeR", "mfeR", "timeToMAE", "timeToMFE"):
        if token not in outcome_live or token not in outcome_backtest:
            errors.append(f"Outcome trackers missing MAE/MFE timing telemetry: {token}")
    # Structural integrity must be observable and must remain anchored to
    # the production sweep event, not a reconstructed proxy.
    for token in ("double sweepPrice;", "datetime sweepTime;"):
        if token not in config:
            errors.append(f"Config.mqh missing authoritative sweep provenance field: {token}")
    for token in ("r.sweepPrice=forBuy?sweepCandle.low:sweepCandle.high;", "r.sweepTime=sweepCandle.time;"):
        if token not in inducement:
            errors.append(f"Inducement.mqh missing authoritative sweep event provenance: {token}")
    for token in ("out.sweep_price = ind.sweepPrice;", "out.sweep_time = ind.sweepTime;"):
        if token not in by_rel.get("includes/Analysis/Scoring.mqh", ""):
            errors.append(f"Scoring.mqh missing sweep provenance propagation: {token}")
    if "setup.invalidation=forBuy?(setup.reasons.sweep_price-0.05*atr):(setup.reasons.sweep_price+0.05*atr);" not in strategy:
        errors.append("StrategyTradeZone.mqh does not anchor structural invalidation to the authoritative sweep")
    if "double entry=ResolveExecutionEntry(setup);" not in strategy:
        errors.append("StrategyTradeZone.mqh does not use the canonical execution entry price for SMC target construction")
    if "p.entryRef = ResolveExecutionEntry(setup);" not in outcome_backtest or "p.sizingEntryPrice = ResolveExecutionEntry(setup);" not in outcome_backtest:
        errors.append("OutcomeTracker.mqh does not use the canonical execution entry price")
    durable_save_pos = ea.find("if(!g_store.Save(decision))")
    tracker_pos = ea.find("g_tracker.AddSetup(chosen,decision.decision_id,decision.decision_fingerprint)")
    execute_gate_pos = ea.find("if(decision.action==POLICY_EXECUTE_ONLY||decision.action==POLICY_EXECUTE_AND_SIGNAL)")
    if durable_save_pos < 0 or tracker_pos < durable_save_pos or execute_gate_pos < 0 or tracker_pos > execute_gate_pos:
        errors.append("Outcome tracking is admitted before durable executable decision acceptance")
    decision_store = by_rel.get("includes/Decision/DecisionStore.mqh", "")
    for token in ("string p[40]", "if(n>=39)", "rec.setup.reasons.structural_state", "rec.setup.calibrated_probability", "rec.setup.reasons.quality_score"):
        if token not in decision_store:
            errors.append(f"DecisionStore.mqh missing durable decision lineage field/restore logic: {token}")
    if "p[39]=DoubleToString(rec.setup.calibration_lower_bound,4)" not in decision_store:
        errors.append("DecisionStore.mqh missing calibration lower-bound persistence")
    if "if(n>=40) rec.setup.calibration_lower_bound=StringToDouble(f[39]);" not in decision_store:
        errors.append("DecisionStore.mqh missing calibration lower-bound restore")
    for token in ("setup.setup_lifecycle=SETUP_EXPIRED", "q.decision==DECISION_TRADE?SETUP_ENTRY_ELIGIBLE:SETUP_EXPIRED"):
        if token not in strategy and token not in quality:
            errors.append(f"StrategyTradeZone/DecisionQuality lifecycle mapping missing: {token}")
    for token in ("setup.decision_state!=DECISION_TRADE", "setup.risk_class<RISK_CLASS_STANDARD", "setup.expected_return_r<=0.0"):
        if token not in multi:
            errors.append(f"MultiTradeEngine.mqh missing downstream risk-quality gate: {token}")
    if "setup.decision_state!=DECISION_TRADE" not in outcome_live or "setup.setup_lifecycle!=SETUP_ENTRY_ELIGIBLE" not in outcome_live:
        errors.append("OutcomeTrackerLive.mqh can admit non-TRADE or pre-entry-eligible setups")
    if "setup.decision_state!=DECISION_TRADE" not in outcome_backtest or "setup.setup_lifecycle!=SETUP_ENTRY_ELIGIBLE" not in outcome_backtest:
        errors.append("OutcomeTracker.mqh can admit non-TRADE or pre-entry-eligible setups")
    for token in ("setup.decision_state == DECISION_REJECT", "setup.decision_state == DECISION_WAIT", "setup.decision_state != DECISION_TRADE"):
        if token not in decision_engine:
            errors.append(f"DecisionEngine.mqh missing authoritative decision-state guard: {token}")
    for token in ("InpEnableDecisionArchitecture", "InpEnableStructuralValidator", "InpRequireSMCStructuralValidity", "InpEnableEnvironmentHardBlock", "InpRequireCausalFVG", "InpMinQualityScore", "InpDecisionRequireCalibration"):
        if token not in ea:
            errors.append(f"MedisTouch_v2.8.mq5 missing decision architecture input: {token}")
    if "g_decision.ConfigureDecisionArchitecture" not in ea:
        errors.append("MedisTouch_v2.8.mq5 missing DecisionArchitecture configuration wiring")
    for token in (
        "InpSweepFollowThroughATRMult=1.2",
        "InpSweepFollowThroughBodyRatio=0.6",
        "g_scoring.ConfigureSweepQuality",
        "followThroughATRMult",
        "followThroughBodyRatio",
    ):
        if token not in ea and token not in inducement and token not in scoring:
            errors.append(f"Missing sweep follow-through threshold wiring/token: {token}")
    if "IsDisplacementBarWithThresholds" not in inducement:
        errors.append("Inducement.mqh does not expose the shared thresholded displacement helper")
    if "m_followThroughATRMult, m_followThroughBodyRatio" not in inducement:
        errors.append("Inducement.mqh sweep grading is not using independent follow-through thresholds")
    regime_stability = by_rel.get("includes/Regime/RegimeDetector.mqh", "")
    for token in ("ClassifyStable(datetime referenceTime)", "referenceTime==m_lastReferenceTime", "return REGIME_TRANSITION;"):
        if token not in regime_stability:
            errors.append(f"RegimeDetector.mqh missing conservative stability invariant: {token}")
    if "ConfigureRegimeStability" not in by_rel.get("includes/Analysis/Scoring.mqh", ""):
        errors.append("Scoring.mqh missing regime stability configuration")
    for token in ("InpRequireRegimeStability=false", "InpRegimeStabilityBars=2", "g_scoring.ConfigureRegimeStability"):
        if token not in ea:
            errors.append(f"MedisTouch_v2.8.mq5 missing regime stability wiring: {token}")

    # Actionable strategy routing must consume only completed bars.
    for file_name, source in (
        ("StrategySetupBuilders.mqh", strategy_builders),
        ("MomentumBreakout.mqh", momentum),
        ("MeanReversion.mqh", mean_reversion),
        ("KeyLevelReaction.mqh", key_level),
        ("RegimeDetector.mqh", regime),
        ("MarketPhase.mqh", market_phase),
    ):
        if "GetCandle(0)" in source or "GetATR(0)" in source or "Classify(0)" in source:
            errors.append(f"{file_name} contains open-bar decision evidence")
    if "HasNearbyLiquidityEvent(const BOSEvent &bos)" not in momentum or "m_liquidity.Timeframe()" not in momentum:
        errors.append("MomentumBreakout.mqh still correlates BOS and liquidity using incompatible raw bar indices")
    if "GetCandle(0)" in value_area or "GetATR(0)" in value_area or "TimeCurrent()" in value_area:
        errors.append("ValueAreaEngine.mqh contains forming-bar/time-now profile inputs")
    if "Timeframe() const" not in liquidity:
        errors.append("Liquidity.mqh does not expose its timeframe for cross-timeframe event correlation")
    if "zone.time = cd0.time;" not in fvg_engine or "zone.time = cd1.time;" in fvg_engine:
        errors.append("FVG.mqh is not anchoring FVG provenance to the completed formation bar")
    portfolio = by_rel.get("includes/Portfolio/PortfolioManager.mqh", "")
    for token in ("RollingCorrelation", "ConfigureCorrelationGuard", "m_enableCorrelationGuard"):
        if token not in portfolio:
            errors.append(f"PortfolioManager.mqh missing optional correlation exposure contract: {token}")

    session_filter = by_rel.get("includes/Core/SessionFilter.mqh", "")
    extended_levels = by_rel.get("includes/SmartMoney/ExtendedKeyLevels.mqh", "")
    if "datetime CSessionFilter::CurrentSessionStartServer()" not in session_filter:
        errors.append("SessionFilter.mqh missing server-time session boundary contract")
    if "CurrentSessionStartServer()" not in extended_levels:
        errors.append("ExtendedKeyLevels.mqh is not using server-time session boundaries")
    if "CurrentSessionStartGMT()" in extended_levels:
        errors.append("ExtendedKeyLevels.mqh compares GMT session boundaries directly with server-time bars")
    if "iTime(m_symbol, PERIOD_W1, 0)" not in extended_levels:
        errors.append("ExtendedKeyLevels.mqh weekly cache is not anchored to broker W1 bar time")
    
    keylevel = by_rel.get("includes/Strategies/KeyLevelReaction.mqh", "")
    for token in ("if(forBuy && z.bottom > price) continue;", "if(!forBuy && z.top < price) continue;"):
        if token not in keylevel:
            errors.append(f"KeyLevelReaction.mqh missing wrong-side zone guard: {token}")
    if "if(dist < 0) dist = 0.0;" in keylevel:
        errors.append("KeyLevelReaction.mqh still clamps wrong-side candidates to zero distance")
    position_manager = by_rel.get("includes/Execution/PositionManager.mqh", "")
    for token in ("m_tp1Done", "m_tp2Done", "CloseTargetSlice", "SyncTargetStage", "m_enableTargetLadder", "m_tp1PartialFraction", "m_tp2PartialFraction", "dec.setup.tp1", "dec.setup.tp2"):
        if token not in position_manager:
            errors.append(f"PositionManager.mqh missing target-ladder contract: {token}")
    for token in ("InpEnableTargetLadder=false", "InpTP1PartialFraction=0.50", "InpTP2PartialFraction=0.25",
                  "InpTP1PartialFraction+InpTP2PartialFraction>=1.0", "INIT_PARAMETERS_INCORRECT"):
        if token not in ea:
            errors.append(f"MedisTouch_v2.8.mq5 missing target-ladder safety contract: {token}")
    calibration = by_rel.get("includes/Trading/CalibrationEngine.mqh", "")
    quality_calibration = by_rel.get("includes/Decision/DecisionQuality.mqh", "")
    for token in ("GetConservativeProbability", "const double z = 1.96"):
        if token not in calibration:
            errors.append(f"CalibrationEngine.mqh missing conservative calibration contract: {token}")
    if "setup.calibration_lower_bound>=minCalibratedProbability" not in quality_calibration:
        errors.append("DecisionQuality.mqh high-conviction risk class is missing conservative calibration bound")
    for token in ("InpEnableCorrelationGuard=false", "InpCorrelationLookback", "InpCorrelationThreshold", "g_portfolio.ConfigureCorrelationGuard"):
        if token not in ea:
            errors.append(f"MedisTouch_v2.8.mq5 missing portfolio correlation guard wiring: {token}")

    # The multi-trade planner is a portfolio policy component. It may evaluate
    # eligibility/allocation, but it must not reach into order submission or
    # execution state directly.
    forbidden = (
        "OrderManager.mqh",
        "PortfolioManager.mqh",
        "RiskEngine.mqh",
        "DecisionEngine.mqh",
    )
    for token in forbidden:
        if token in multi:
            errors.append(f"MultiTradeEngine.mqh is coupled directly to {token}; keep portfolio policy independent")

    gates = (
        "MathIsValidNumber(setup.calibrated_probability)",
        "setup.calibrated_probability<0.0",
        "setup.calibrated_probability>100.0",
        "MathIsValidNumber(setup.confidence)",
        "setup.confidence<0.0",
        "setup.confidence>100.0",
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


# risk-class promotion must remain conservative even when calibration has enough samples
# and requires qualified environment memory for elevated classes.
