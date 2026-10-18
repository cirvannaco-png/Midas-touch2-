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
    "schema_version", "signal_id", "event_key", "symbol", "timeframe",
    "direction", "signal_epoch", "attribution_status",
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
        ('"order-flow-attribution-v1"', "attribution row schema literal"),
        ('"MedisTouch_OrderFlowEvidence_v3_"', "evidence filename version"),
        ('"MedisTouch_OrderFlowAttribution_v1_"', "attribution filename version"),
    ):
        require(token in ea, f"EA missing {description}: {token}", errors)

    require('{"order-flow-evidence-v2", "order-flow-evidence-v3"}' in analyzer,
            "analyzer must retain legacy v2 support and parse the v3 schema", errors)

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
        ("!MathIsValidNumber(pressureThreshold)", "finite pressure-threshold guard"),
    ):
        require(token in module, f"order-flow module missing {description}", errors)

    require("datetime evaluationTime=0" in module,
            "order-flow analysis must accept an explicit evaluation timestamp", errors)
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

    print(f"Order-flow CSV contract: {len(evidence_fields)} evidence columns, "
          f"{len(attribution_fields)} attribution columns")
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(f"{len(errors)} contract error(s).", file=sys.stderr)
        return 1
    print("CSV schema, version, status and opt-in gate checks passed.")
    print("Note: this is static validation, not a MetaEditor compilation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
