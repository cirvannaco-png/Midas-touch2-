#!/usr/bin/env python3
"""Static contract checks for Midas-touch2 order-flow CSV writers and analyzer.

This validates source-level schemas and feature gates only. It does not compile
MQL5 or prove that terminal-side FileWrite calls succeed at runtime.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EA_PATH = ROOT / "EA" / "MedisTouch_v2.8.mq5"
PY_PATH = ROOT / "tools" / "order_flow_research.py"
MODULE_PATH = ROOT / "EA" / "includes" / "Analysis" / "OrderFlowDiagnostics.mqh"

EVIDENCE_REQUIRED = {
    "schema_version", "event_key", "symbol", "timeframe", "bar_end_epoch",
    "pressure_ratio", "diagnostic_status", "bullish_sweep_reclaim",
    "bearish_sweep_reclaim", "absorption_proxy", "exhaustion_proxy",
    "data_quality", "data_stale", "pressure_progress_divergence",
    "continuation_hypothesis", "reversal_hypothesis", "auction_context_available",
    "value_area_poc", "value_area_vah", "value_area_val",
    "value_area_source_quality", "value_area_source", "auction_location",
}
ATTRIBUTION_REQUIRED = {
    "schema_version", "signal_id", "decision_id", "decision_fingerprint",
    "event_key", "symbol", "timeframe", "direction", "signal_epoch",
    "attribution_status", "smc_inducement_valid", "smc_liquidity_swept",
    "smc_bos_confirmed", "smc_sweep_grade", "smc_bos_strength", "smc_time_decay",
}


def header_fields(source: str, start_marker: str) -> list[str]:
    start = source.find(start_marker)
    if start < 0:
        raise ValueError(f"missing source marker: {start_marker}")
    section = source[start:]
    match = re.search(r"uint\s+headerBytes\s*=\s*FileWrite\(handle,(.*?)\);", section, re.S)
    if not match:
        raise ValueError(f"missing FileWrite header after: {start_marker}")
    fields = re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1))
    if not fields:
        raise ValueError(f"header has no string fields after: {start_marker}")
    return fields


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def section_between(source: str, start_marker: str, end_marker: str) -> str:
    """Extract a source section between unique function markers."""
    start = source.find(start_marker)
    if start < 0:
        raise ValueError(f"missing source marker: {start_marker}")
    end = source.find(end_marker, start + len(start_marker))
    if end < 0:
        raise ValueError(f"missing source marker: {end_marker}")
    if end <= start:
        raise ValueError(f"invalid source section: {start_marker} -> {end_marker}")
    return source[start:end]


def main() -> int:
    errors: list[str] = []
    try:
        ea = EA_PATH.read_text(encoding="utf-8")
        analyzer = PY_PATH.read_text(encoding="utf-8")
        module = MODULE_PATH.read_text(encoding="utf-8")
        evidence_fields = header_fields(ea, "bool AppendOrderFlowEvidence")
        attribution_fields = header_fields(ea, "bool AppendOrderFlowSignalAttribution")
    except (OSError, ValueError) as exc:
        print(f"order-flow contract validation: {exc}", file=sys.stderr)
        return 1

    missing_evidence = sorted(EVIDENCE_REQUIRED - set(evidence_fields))
    missing_attribution = sorted(ATTRIBUTION_REQUIRED - set(attribution_fields))
    require(not missing_evidence,
            f"evidence CSV header missing analyzer fields: {missing_evidence}", errors)
    require(not missing_attribution,
            f"attribution CSV header missing fields: {missing_attribution}", errors)
    require(len(evidence_fields) == len(set(evidence_fields)),
            "evidence CSV header contains duplicate column names", errors)
    require(len(attribution_fields) == len(set(attribution_fields)),
            "attribution CSV header contains duplicate column names", errors)

    for token, description in (
        ('"order-flow-evidence-v3"', "evidence row schema literal"),
        ('"order-flow-attribution-v3"', "attribution row schema literal"),
        ('"MedisTouch_OrderFlowEvidence_v3_"', "evidence filename version"),
        ('"MedisTouch_OrderFlowAttribution_v3_"', "attribution filename version"),
    ):
        require(token in ea, f"EA missing {description}: {token}", errors)

    # v3 carries decision lineage plus SMC context. The analyzer must still
    # accept v1/v2 attribution exports created before SMC context was added.
    for field in ("decision_id", "decision_fingerprint"):
        require(field in attribution_fields,
                f"v3 attribution CSV header missing decision lineage field: {field}", errors)
    for field in ("smc_inducement_valid", "smc_liquidity_swept", "smc_bos_confirmed",
                  "smc_sweep_grade", "smc_bos_strength", "smc_time_decay"):
        require(field in attribution_fields,
                f"v3 attribution CSV header missing SMC context field: {field}", errors)
    require(all(f'"{schema}"' in analyzer for schema in (
                "order-flow-attribution-v1", "order-flow-attribution-v2",
                "order-flow-attribution-v3")),
            "analyzer must support v1/v2 compatibility and current v3 attribution", errors)

    require('{"order-flow-evidence-v2", "order-flow-evidence-v3"}' in analyzer,
            "analyzer must retain legacy v2 support and parse the v3 schema", errors)
    require(all(f'"{schema}"' in analyzer for schema in (
                "order-flow-attribution-v1", "order-flow-attribution-v2",
                "order-flow-attribution-v3")),
            "analyzer must retain v1/v2 compatibility and parse v3 lineage/context", errors)
    for metric in ("longest_loss_streak", "longest_win_streak",
                   "observed_calendar_days", "trades_per_30_calendar_days"):
        require(f'"{metric}"' in analyzer,
                f"research report is missing risk/frequency metric: {metric}", errors)

    expected_statuses = (
        "BAR_HISTORY_UNAVAILABLE", "BAR_CONTEXT_UNAVAILABLE",
        "TICK_HISTORY_ERROR", "NO_TICKS", "INVALID_OR_INSUFFICIENT_TICKS",
        "STALE_PROXY", "OK_PROXY",
    )
    for status in expected_statuses:
        require(status in ea, f"missing explicit diagnostic status: {status}", errors)

    # These source-level guards protect the diagnostic calculation from NaN,
    # infinity, malformed bar geometry, and mismatched array/count inputs.
    # They do not replace a native MetaEditor compile or terminal runtime test.
    for token, description in (
        ("!MathIsValidNumber(priorHigh)", "finite prior-level guard"),
        ("!MathIsValidNumber(barClose)", "finite completed-bar guard"),
        ("barClose<barLow || barClose>barHigh", "completed-bar range guard"),
        ("!MathIsValidNumber(atr)", "finite ATR guard"),
        ("count>ArraySize(ticks)", "tick-count/array-bound guard"),
        ("!MathIsValidNumber(bid)", "finite bid guard"),
        ("!MathIsValidNumber(ask)", "finite ask guard"),
        ("double mid=bid*0.5+ask*0.5;", "overflow-safe midpoint arithmetic"),
        ("!MathIsValidNumber(pressureThreshold)", "finite pressure-threshold guard"),
    ):
        require(token in module, f"order-flow module missing {description}", errors)

    require("datetime evaluationTime=0" in module,
            "order-flow analysis must accept an explicit evaluation timestamp", errors)
    require("extreme finite quotes retain a finite midpoint/progress proxy" in
            (ROOT / "EA" / "tests" / "OrderFlowDiagnostics.mq5").read_text(encoding="utf-8"),
            "native order-flow tests must cover extreme finite midpoint arithmetic", errors)
    require("tickTimeMsc>(long)evaluationTime*1000" in module,
            "order-flow analysis must reject future ticks beyond the evaluation boundary", errors)
    require("datetime referenceTime=(evaluationTime>0 ? evaluationTime : TimeCurrent())" in module,
            "staleness must be anchored to the supplied evaluation timestamp", errors)
    require(
        "g_orderFlowDiagnostics.Analyze(ticks,copied,priorHigh,priorLow," in ea and
        "barHigh,barLow,barClose,atr,of,barEnd)" in ea,
        "production analysis must pass the closed-bar end timestamp", errors)

    require('input bool InpEnableOrderFlowDiagnostics=false;' in ea,
            "order-flow diagnostics must remain disabled by default", errors)
    require('if(!InpEnableOrderFlowDiagnostics || g_fvgCtx==NULL)' in ea,
            "order-flow sampling must remain behind the explicit opt-in guard", errors)

    # Phase-1 invariant: order-flow diagnostics may collect/attribute evidence,
    # but must not enter setup selection or risk/execution branches. Keep this
    # guard structural so later refactors cannot silently promote a proxy into
    # a trade filter before independent research and review.
    selection_start = ea.find("TradeSetup buySetup=g_decision.GenerateBuySetup()")
    selection_end = ea.find(
        "if(!chosen.active||chosen.creation_time==g_lastLoggedTime)return;",
        selection_start,
    )
    require(selection_start >= 0 and selection_end > selection_start,
            "could not isolate the canonical setup-selection section", errors)
    if selection_start >= 0 and selection_end > selection_start:
        selection_section = ea[selection_start:selection_end]
        require(not any(token in selection_section for token in
                        ("OrderFlow", "orderFlow", "g_lastOrderFlow")),
                "order-flow diagnostics must not affect setup selection/confidence", errors)

    router_start = ea.find("TradeDecisionRecord decision=g_router.Decide(chosen);")
    fingerprint_end = ea.find("decision.decision_fingerprint=DecisionFingerprintFor(decision);", router_start)
    attribution_call = ea.find(
        "AppendOrderFlowSignalAttribution(chosen,decision);", router_start
    )
    execution_start = ea.find(
        "if(!decision.valid||decision.action==POLICY_IGNORE)return;", router_start
    )
    require(router_start >= 0 and fingerprint_end > router_start and
            attribution_call > fingerprint_end and execution_start > attribution_call,
            "decision attribution must occur after fingerprint creation and before execution routing", errors)
    if execution_start >= 0:
        execution_end = ea.find("// Persistent per-symbol/per-magic emergency latch", execution_start)
        if execution_end < 0:
            execution_end = len(ea)
        execution_section = ea[execution_start:execution_end]
        require(not any(token in execution_section for token in
                        ("OrderFlow", "orderFlow", "g_lastOrderFlow")),
                "order-flow evidence must not influence risk, exits, or execution", errors)

    # Defense in depth: every member access on the local snapshot must stay
    # within the evidence writer and diagnostic log. Its proxy fields are not
    # eligible inputs to any scorer, router, sizing component or order manager.
    try:
        evidence_writer = section_between(
            ea, "bool AppendOrderFlowEvidence(", "void AttachOrderFlowAuctionContext("
        )
        diagnostic_runner = section_between(
            ea, "void LogOrderFlowDiagnostics()", "bool AppendOrderFlowSignalAttribution("
        )
        remaining = ea
        for section in (evidence_writer, diagnostic_runner):
            require(section in remaining,
                    "could not isolate order-flow evidence/logging sections", errors)
            remaining = remaining.replace(section, "", 1)
        require(
            re.search(r"\bof\s*\.", remaining) is None,
            "OrderFlowSnapshot fields may only be read in evidence/logging sections",
            errors,
        )
        for token in (
            "g_scoring", "g_risk.", "g_riskGuard.", "g_router.Decide",
            "g_decision.Generate", "g_orders.Submit", "g_portfolio.",
            "CalculateLotSize", "chosen.confidence", "chosen.stop_loss",
            "chosen.final_tp",
        ):
            require(token not in diagnostic_runner,
                    f"diagnostic runner must not enter trade policy: {token}", errors)
    except ValueError as exc:
        errors.append(f"diagnostic isolation contract: {exc}")

    print(f"Order-flow CSV contract: {len(evidence_fields)} evidence columns, "
          f"{len(attribution_fields)} attribution columns")
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(f"{len(errors)} contract error(s).", file=sys.stderr)
        return 1
    print("CSV schema, version, status, opt-in gate and diagnostic-isolation checks passed.")
    print("Note: this is static validation, not a MetaEditor compilation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
