# Midas-touch2 Order-Flow Research Runbook

Status: operational procedure for controlled research only. This document does not authorize a live-trading change.

## 1. Safe capture mode

Start in the **MT5 Strategy Tester**, not on a live account. The EA's order-flow diagnostics are disabled by default because tick-history reads, logging and CSV writes are synchronous. Using the Tester with execution disabled avoids sending broker orders while collecting comparable records.

Use the same EA build, symbol, chart timeframe, date window and modelling mode for all runs. For the first capture, use a model with the most complete tick history available for the symbol and dates; record the exact data provider and modelling mode in your experiment notes.

Set these inputs for a research-only capture:

| Input | Capture value | Reason |
|---|---:|---|
| `InpEnableExecution` | `false` | Router should not authorize automated broker execution |
| `InpEnableSignals` | `true` | Keep candidate decisions observable |
| `InpEnableOrderFlowDiagnostics` | `true` | Write the v3 closed-bar evidence and v3 attribution |
| `InpLogSignals` | `true` | Required to create the paired signal row used by direct attribution |
| `InpTrackOutcomes` | `true` | Record outcomes from the EA's outcome tracker |
| `InpFVGTF` | The timeframe under study | Must match the evidence/attribution files and experiment record |

Do not use this configuration as permission to attach the EA to a live chart. In particular, use the Strategy Tester for the first run; do not rely on disabling automated entry alone to protect pre-existing open positions or other account activity.

## 2. Files to collect

After the Strategy Tester run completes, copy the generated files out of its file sandbox and preserve the originals unchanged:

- `MedisTouch_OrderFlowEvidence_v3_<symbol>_<timeframe>.csv`
- `MedisTouch_OrderFlowAttribution_v3_<symbol>_<timeframe>.csv`
- `MedisTouch_Signals_<symbol>.csv`
- `MedisTouch_Outcomes_v2_<symbol>.csv`

File names can contain MT5 enum strings such as `PERIOD_M15`. Confirm actual names rather than renaming files by assumption. Preserve the original evidence and record the EA commit, symbol, timeframe, date range, modelling mode, tester settings, and any missing-history messages.

If the attribution export is present, use it. The analyzer then requires exact `SignalID → event_key` lineage plus decision ID/fingerprint; it intentionally does not switch to nearest-time matching when a direct link is absent or invalid.

## 3. Run the outcome-linked analyzer

From the repository root, place the exports in an `exports/` directory and run (replace the example `EURUSD` and timeframe when needed):

```bash
python tools/order_flow_research.py \
  --evidence "exports/MedisTouch_OrderFlowEvidence_v3_EURUSD_PERIOD_M15.csv" \
  --signals "exports/MedisTouch_Signals_EURUSD.csv" \
  --outcomes "exports/MedisTouch_Outcomes_v2_EURUSD.csv" \
  --attribution "exports/MedisTouch_OrderFlowAttribution_v3_EURUSD_PERIOD_M15.csv" \
  --output "order_flow_research_report.json" \
  --holdout-fraction 0.30 \
  --min-sample 30
```

The analyzer exits with a readable validation error rather than silently repairing malformed input. It excludes unresolved, unfilled, stale, invalid or wrongly linked records from outcome metrics and reports their rejection counts. It also reports:

- direct-attribution rejections and missing/unusable evidence-event counts;
- realized-R expectancy, profit factor, drawdown, streaks and observed trade frequency where timestamps support it;
- long/short and regime/context breakdowns with unique evidence-event counts;
- purged chronological train/holdout metrics;
- quote-update-rate proxy distributions for matched, training and holdout rows, plus prior-only activity-regime splits.

Treat the number of **unique evidence events** as an important dependency check: multiple signals tied to the same bar do not become independent samples. A minimum-sample flag is descriptive, not proof of an edge.

## 4. Diagnostics OFF/ON parity

Run two Strategy Tester captures on identical inputs and dates. Change only `InpEnableOrderFlowDiagnostics` between OFF and ON. Keep execution disabled in both runs.

Compare signal/candidate count, direction, confidence, SL/TP, router action, signal IDs and tracker/outcome records. Also inspect log timing and test determinism: synchronous `CopyTicksRange` and CSV I/O can affect processing time even though order-flow feature values are not consumed by the scorer or execution policy.

Any unexplained difference in decisions or state transitions blocks promotion. A matching candidate list is not sufficient to prove matching fill timing on a live terminal.

## 5. Interpret the added activity proxy correctly

`quote_update_rate_hz_proxy` is the validated closed-bar tick count divided by nominal timeframe seconds. The regime compares the current closed bar with the median of up to 20 prior valid bars, requiring at least five, from the same symbol/timeframe/UTC-day run. A ratio at least 1.50 is labelled `EXPANSION`; a ratio at most 0.67 is labelled `CONTRACTION`; intermediate ratios are `NORMAL`. The baseline resets at UTC-day boundaries and after a gap longer than one nominal bar.

This estimates **broker quote-update cadence**, not executed trade count, traded volume, aggressor-side delta, exchange CVD, or consolidated DOM. Broker tick density may vary by feed and instrument. Do not import these fixed descriptive labels into entry logic or assume they generalize across instruments.

## 6. Promotion gate

Do not merge an entry gate or deploy the diagnostics on a live account based on compile status, synthetic tests, educator examples, or proxy values alone. Before any candidate feature is considered for a separate gate, require:

1. reviewed ON/OFF parity and target-terminal CSV coverage;
2. matched baseline/challenger tests with representative spread, commission, slippage and swap/financing costs;
3. chronological walk-forward and untouched locked out-of-sample data with sufficient resolved independent evidence events and uncertainty estimates;
4. Exness demo-forward observations and broker order/deal reconciliation;
5. human review of all rejection counts, ambiguous outcomes, data-source limitations and safety controls.

Keep `InpEnableOrderFlowDiagnostics=false` by default outside a controlled research run. Existing entry policy, confidence, sizing, exits, SL/TP, trailing stop, emergency stop, ledger and execution logic must remain unchanged throughout Phase 1.
