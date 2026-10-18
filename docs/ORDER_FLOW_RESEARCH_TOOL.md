# Order-Flow Research Tool

## Purpose and limitations

The feature branch adds an optional, diagnostic-only order-flow proxy to the EA plus a standard-library Python utility for joining proxy snapshots to the existing signal/outcome exports. It is research instrumentation, not a strategy promotion system. The MQL5 changes are not yet compiled in MetaEditor, and these metrics do not establish profitability.

The diagnostic timeframe is the EA's configured InpFVGTF, which also appears in the current signal log's EntryTF field. The logger tracks that timeframe's bar boundary independently from the chart timeframe, uses its ATR context, and writes a separate versioned evidence file for the symbol/timeframe. This avoids silently joining snapshots from a different timeframe.

## Evidence CSV

When InpEnableOrderFlowDiagnostics is true, the EA writes:

- MedisTouch_OrderFlowEvidence_v2_<symbol>_<timeframe>.csv

The version-2 evidence CSV includes schema version, deterministic event key, symbol, timeframe, bar start/end epoch, prior range, completed-bar OHLC, ATR, valid tick count, proxy data quality, pressure ratio, counts of midpoint-up/down changes, price progress, closed-bar sweep/reclaim flags, heuristic absorption/exhaustion flags, stale status, first/last tick timestamps in milliseconds where available, and a diagnostic status such as OK_PROXY, STALE_PROXY, NO_TICKS, TICK_HISTORY_ERROR or BAR_CONTEXT_UNAVAILABLE. Missing/invalid windows are written as quality=0 diagnostic rows instead of silently disappearing.

The input remains false by default. Enabling it causes synchronous tick-history reads, terminal logging and CSV file I/O before normal setup evaluation. The diagnostic values do not feed the setup scorer, but I/O may affect live fill timing. Do not enable in live trading before compilation, decision-path tests and demo-forward review.

## Exact signal attribution

When `InpEnableOrderFlowDiagnostics` and `InpLogSignals` are enabled, the EA appends a separate `MedisTouch_OrderFlowAttribution_v1_<symbol>_<timeframe>.csv` row for each successfully logged signal. The row uses the exact existing `SignalID` and the event key persisted by the evidence writer. It does not change the historical signal/outcome CSV schemas. Attribution status is `MATCHED` when an evidence row was successfully written and `NO_EVENT_KEY` otherwise. A referenced event whose status is unavailable/stale will still be excluded from analysis.

Pass `--attribution` to use exact SignalID-to-event joins. When the attribution file is supplied, the analyzer does **not** fall back to nearest-time matching for signals without a valid link. Without that optional file, the analyzer retains its explicitly reported nearest-prior-time mode.

## Analyze exported evidence

Copy the evidence CSV, attribution CSV (for exact joins), and the EA files MedisTouch_Signals_<symbol>.csv and MedisTouch_Outcomes_v2_<symbol>.csv into a research folder, then run from the repository root. Add `--attribution MedisTouch_OrderFlowAttribution_v1_EURUSD_PERIOD_M1.csv` to the command to enable strict direct linkage:

    python tools/order_flow_research.py --evidence MedisTouch_OrderFlowEvidence_v2_EURUSD_PERIOD_M1.csv --attribution MedisTouch_OrderFlowAttribution_v1_EURUSD_PERIOD_M1.csv --signals MedisTouch_Signals_EURUSD.csv --outcomes MedisTouch_Outcomes_v2_EURUSD.csv --output order_flow_research_report.json

The analyzer:
- requires the version-2 schema and proxy-only quality, excludes stale/invalid rows from metrics, and counts unavailable windows for coverage review;
- joins by exact SignalID/event key when the attribution file is supplied (never falling back on failed links), or otherwise by exact symbol/timeframe to the most recent bar boundary no later than the signal creation epoch, with a configurable maximum gap. By default, the match window is the duration of one recognized signal timeframe bar; unknown periods are rejected unless a positive explicit override is supplied;
- excludes unfilled signals, missing/non-finite R values, missing outcome epochs, and outcomes resolving before their signal;
- fails closed on conflicting duplicate IDs instead of silently picking one;
- reports expectancy in R, profit factor, maximum drawdown in R, total R and win/loss/scratch counts;
- uses a chronological holdout and purges training observations whose outcomes resolve at or after the holdout start;
- reports join rejections, breaks down outcomes by direction, symbol, timeframe, session, regime, volatility regime and selected strategy where those signal columns are available, and never automatically promotes a feature or alters a live policy.
- reports both matched trade count and unique evidence-event count, including events shared by multiple signals; repeated signals referencing one proxy snapshot must not be treated as independent evidence.

Direct mode joins the signal ID to the stored event key; the signal ID is inherited from the EA's existing logging schema and the analyzer also verifies symbol, timeframe, direction, chronology and usable evidence status. The fallback mode remains time-based. Review attribution coverage and rejection counts before interpreting results.

## Checks

Run:

    python -m unittest discover -s tests -p test_order_flow_research.py -v
    python tools/validate_mql5.py EA

The GitHub Actions workflow under .github/workflows/order-flow-research.yml runs these Python tests and the structural include-tree validation. Those checks do not compile MQL5. The exact EA and included module must still compile in MetaEditor, and the feature must pass Strategy Tester, matched-cost, out-of-sample, and demo-forward gates before any execution integration.
