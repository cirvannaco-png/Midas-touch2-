# Order-Flow Research Tool

## Purpose and limitations

The feature branch adds an optional, diagnostic-only order-flow proxy to the EA plus a standard-library Python utility for joining proxy snapshots to the existing signal/outcome exports. It is research instrumentation, not a strategy promotion system. On tested code commit `53b1770c444a911f2f96aa6227947083fa83d62f`, [MetaTrader 5 EA Compile](https://github.com/cirvannaco-png/Midas-touch2-/actions/runs/39136659878), [Midas Touch CI](https://github.com/cirvannaco-png/Midas-touch2-/actions/runs/39136659979), and [Order-Flow Research and MQL5 Structural Checks](https://github.com/cirvannaco-png/Midas-touch2-/actions/runs/39136659973) passed. The order-flow research suite ran 37 tests; schema checks confirmed 37 evidence columns and 16 attribution columns. MetaEditor and synthetic Strategy Tester checks passed, but these results do not establish diagnostic ON/OFF parity on a full trading run, statistical edge, locked holdout performance, or Exness demo-forward behavior. On exact head `e3f089d4e9b4c350a922fed5b024a5765b3e64db`, GitHub Actions run [39129140510](https://github.com/cirvannaco-png/Midas-touch2-/actions/runs/39129140510) passed MetaEditor compilation with 0 errors and 0 warnings; Midas Touch CI run [39129140499](https://github.com/cirvannaco-png/Midas-touch2-/actions/runs/39129140499) and order-flow research run [39129140488](https://github.com/cirvannaco-png/Midas-touch2-/actions/runs/39129140488) also passed. These results do not establish diagnostic runtime correctness or trading profitability.

The diagnostic timeframe is the EA's configured InpFVGTF, which also appears in the current signal log's EntryTF field. The logger tracks that timeframe's bar boundary independently from the chart timeframe, uses its ATR context, and writes a separate versioned evidence file for the symbol/timeframe. This avoids silently joining snapshots from a different timeframe.

## Evidence CSV

When InpEnableOrderFlowDiagnostics is true, the EA writes:

- MedisTouch_OrderFlowEvidence_v3_<symbol>_<timeframe>.csv

The version-3 evidence CSV retains the v2 fields and appends pressure-progress divergence, separate continuation/reversal hypothesis tags, and auction context (POC/VAH/VAL, source quality/source identifier, and the completed close location relative to the profile). Missing/invalid windows are written as quality=0 diagnostic rows instead of silently disappearing. The analyzer still accepts legacy v2 evidence files.

The input remains false by default. Enabling it causes synchronous tick-history reads, terminal logging and CSV file I/O before normal setup evaluation. The diagnostic values do not feed the setup scorer, but I/O may affect live fill timing. Do not enable in live trading before compilation, decision-path tests and demo-forward review.

## Exact signal attribution

When `InpEnableOrderFlowDiagnostics` and `InpLogSignals` are enabled, the EA appends a separate `MedisTouch_OrderFlowAttribution_v3_<symbol>_<timeframe>.csv` row for each successfully logged signal. It carries the exact existing `SignalID`, event key, router `decision_id`, and `decision_fingerprint`, then snapshots existing SMC context: inducement validity, liquidity-sweep and BOS flags, sweep grade, BOS strength, and time-decay. The analyzer keeps backward compatibility with v1 (basic signal/event link) and v2 (decision lineage) exports; v3 requires valid lineage and all six SMC fields. This makes order-flow proxy results stratifiable by pre-existing SMC context without adding any entry or risk gate. Attribution status is `MATCHED` when a fresh evidence row was successfully written and `NO_USABLE_EVENT` otherwise. A referenced event whose status is unavailable/stale is excluded from analysis.

Pass `--attribution` to use exact SignalID-to-event joins. When the attribution file is supplied, the analyzer does **not** fall back to nearest-time matching for signals without a valid link. Without that optional file, the analyzer retains its explicitly reported nearest-prior-time mode.

## Analyze exported evidence

Copy the evidence CSV, attribution CSV (for exact joins), and the EA files MedisTouch_Signals_<symbol>.csv and MedisTouch_Outcomes_v2_<symbol>.csv into a research folder, then run from the repository root. Add `--attribution MedisTouch_OrderFlowAttribution_v3_EURUSD_PERIOD_M1.csv` to the command to enable strict direct linkage:

    python tools/order_flow_research.py --evidence MedisTouch_OrderFlowEvidence_v3_EURUSD_PERIOD_M1.csv --attribution MedisTouch_OrderFlowAttribution_v3_EURUSD_PERIOD_M1.csv --signals MedisTouch_Signals_EURUSD.csv --outcomes MedisTouch_Outcomes_v2_EURUSD.csv --output order_flow_research_report.json

The analyzer:
- accepts v2 and v3 schemas, requires proxy-only quality, excludes stale/invalid rows from outcome metrics, and counts unavailable windows for coverage review;
- derives a UTC-day-reset cumulative midpoint tick-count pressure proxy and a pressure/price divergence tag; these are not true exchange CVD or traded volume;
- stratifies outcomes by auction location and separately tagged continuation/reversal hypotheses;
- derives `quote_update_rate_hz_proxy` from validated v3 closed-bar tick counts divided by nominal timeframe seconds. The activity regime compares only with up to 20 preceding valid bars in the same symbol/timeframe/UTC day, requires at least five, resets after a gap longer than one bar, and labels ratio >= 1.50 as `EXPANSION`, <= 0.67 as `CONTRACTION`, otherwise `NORMAL`; missing baselines stay `INSUFFICIENT_HISTORY` rather than being imputed;
- joins by exact SignalID/event key when the attribution file is supplied (never falling back on failed links), or otherwise by exact symbol/timeframe to the most recent bar boundary no later than the signal creation epoch, with a configurable maximum gap. By default, the match window is the duration of one recognized signal timeframe bar; unknown periods are rejected unless a positive explicit override is supplied;
- excludes unfilled signals, missing/non-finite R values, missing outcome epochs, and outcomes resolving before their signal;
- fails closed on conflicting duplicate IDs instead of silently picking one;
- reports expectancy in R, profit factor, maximum drawdown in R, total R and win/loss/scratch counts;
- uses a chronological holdout and purges training observations whose outcomes resolve at or after the holdout start;
- reports join rejections, breaks down outcomes by direction, symbol, timeframe, session, regime, volatility regime and selected strategy where those signal columns are available, and never automatically promotes a feature or alters a live policy.
- reports both matched trade count and unique evidence-event count, including events shared by multiple signals; repeated signals referencing one proxy snapshot must not be treated as independent evidence.
- reports net realized expectancy in R, profit factor, maximum drawdown in R, longest winning/losing streaks, total R, and an observed trade frequency normalized to 30 calendar days when valid signal timestamps span a non-zero interval. Frequency is `null` when no trustworthy time span exists; short samples can make the normalized rate unstable and it is descriptive, not a forecast. The report also includes descriptive quote-update-rate and ratio distributions (count, mean, median, p90, min and max) for all matched trades, training rows and chronological holdout rows.

Direct mode joins the signal ID to the stored event key; the signal ID is inherited from the EA's existing logging schema and the analyzer also verifies symbol, timeframe, direction, chronology and usable evidence status. The fallback mode remains time-based. Review attribution coverage and rejection counts before interpreting results.

## Checks

Run:

    python -m unittest discover -s tests -p test_order_flow_research.py -v
    python tools/validate_mql5.py EA

The GitHub Actions workflow under .github/workflows/order-flow-research.yml runs these Python tests and structural include-tree validation. The exact head has also passed the separate MetaEditor compile workflow; however, no diagnostic-specific Strategy Tester ON/OFF equivalence, matched-cost performance experiment, locked-OOS evaluation, or Exness demo-forward test has been evidenced. Those gates remain mandatory before any execution integration.
