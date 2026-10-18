# Midas-touch2 Order-Flow Confirmation Engine

## Status and safety boundary

This document records the implementation and validation plan for the existing MQL5 EA. Order-flow remains diagnostic-only and disabled by default. The current feature branch adds version-3 per-closed-bar evidence, explicit value-area context, separate continuation/reversal research hypotheses, deterministic evaluation-time/stale-data handling, version-2 decision-linked attribution, and outcome-analysis support with legacy schema compatibility. At code commit `64aa0e5b183cbf377121aff6284c114a9adae796`, [MetaTrader 5 EA Compile](https://github.com/cirvannaco-png/Midas-touch2-/actions/runs/39133610479), [Midas Touch CI](https://github.com/cirvannaco-png/Midas-touch2-/actions/runs/39133610491), and [Order-Flow Research and MQL5 Structural Checks](https://github.com/cirvannaco-png/Midas-touch2-/actions/runs/39133610496) all passed. MetaEditor reported 0 errors and 0 warnings for the EA, companion indicator, and all four policy-test programs. Native Strategy Tester synthetic tests reported zero assertion failures for order-flow diagnostics and the existing position-management, account-risk, and dynamic-stop policies. The research suite ran 29 Python tests successfully and validated 37 evidence columns plus 10 attribution columns. These checks do not prove trading profitability or live decision-path parity. Keep all existing entries, confidence, sizing, exits, SL/TP, trailing stops, emergency stop, and execution policy unchanged. Diagnostic ON/OFF parity, matched-cost performance evaluation, locked out-of-sample testing, runtime CSV coverage review, and Exness demo-forward validation remain outstanding.

The canonical EA source is `EA/`; do not implement new behavior under legacy `mql5/` or the non-production `medis_touch/` reference tree.

## Concepts to cover

1. **Aggression / delta:** classify available tick events conservatively. A quote/tick-direction estimate is a proxy, not exchange-traded bid/ask footprint delta.
2. **Cumulative delta and divergence:** maintain a bounded per-session or per-bar signed-volume proxy; flag price/delta disagreement only as evidence, never a standalone reversal signal.
3. **Liquidity sweeps and failed breakouts:** join existing liquidity/inducement/sweep evidence with post-sweep rejection or acceptance, and require completed-bar confirmation to avoid repainting.
4. **Absorption proxy:** flag high estimated aggression with limited price progress near a pre-existing level; never claim hidden institutional orders were directly observed from ordinary MT5 forex/CFD data.
5. **Exhaustion:** identify diminishing price progress / participation after extension, with a separate continuation-vs-reversal interpretation and no automatic fade.
6. **Imbalance / pressure:** identify persistent one-sided tick pressure where data quality supports it; do not fabricate footprint stacked imbalances from OHLC alone.
7. **Auction context / volume profile:** reuse the existing ValueArea implementation for POC/VAH/VAL where valid. Keep tick-volume profile distinct from exchange traded volume and distinguish acceptance from rejection.
8. **Large orders / iceberg / DOM / spoofing:** enable only when a suitable, time-stamped Level-2 feed exists. Do not infer iceberg orders or spoofing from candle data or a broker's incomplete DOM snapshot.
9. **Momentum breakout and pullback continuation:** use pressure and follow-through as optional confirmation for existing BOS/FVG continuation setups.
10. **Absorption reversal / high-low-volume reversal / stop-run continuation:** model as separately tagged hypotheses, not one generic signal. Test each independently and include both long and short directions.

## Integration design

- [x] Add a self-contained module under `EA/includes/Analysis/` with a quality/status field (valid/proxy-only/unavailable) and stale-data flag.
- [x] Add an opt-in, closed-bar diagnostic hook that logs pressure proxy, sweep/reclaim flags, absorption proxy and exhaustion proxy; default OFF.
- [x] Add versioned per-bar evidence CSV and a separate exact SignalID-to-event-key attribution CSV. Attribution v2 records the router decision ID and decision fingerprint after routing, without changing legacy signal/outcome CSV schemas; the research analyzer remains compatible with historical v1 attribution files.
- Feed it only timestamped data available at decision time. Use closed bars for bar-based features; no future bars, hindsight pivots, or post-fill information.
- Integrate after data collection and before decision routing as a **diagnostic evidence object**. Keep the existing `CScoringEngine::CalculateConfidence()` arithmetic and all risk/execution controls unchanged in the first phase.
- Log feature values and data quality to the versioned evidence CSV; preserve a separate exact SignalID-to-event-key attribution CSV for outcome linkage. Review both outputs and their schema compatibility before research. Do not silently change existing CSV column positions or parsers.
- Add explicit inputs for enabling diagnostics and thresholds; defaults must preserve existing trading behavior.
- Preserve the production trailing stop, emergency stop, account risk profiles, spread/session/news guards, broker reconciliation, and restart recovery.
- Only after evidence review may a separate opt-in confirmation gate be introduced. A hard gate must fail closed when it is explicitly required but the required data is unavailable; diagnostic-only mode may report unavailable without blocking trades.

## Version-3 research evidence

The version-3 evidence schema appends pressure-versus-price-progress divergence, separately tagged continuation and sweep/reclaim reversal hypotheses, and the existing ValueArea engine's POC/VAH/VAL levels, source quality/source identifier, and close location. Auction location is contextual only: one close above VAH does not prove acceptance, and one wick does not prove a stop hunt or institutional activity.

The research analyzer retains compatibility with legacy v2 files. It computes a UTC-day-reset cumulative midpoint tick-count pressure proxy and an explicitly labeled cumulative-pressure/price divergence. These are quote-direction counts, not executed volume, exchange CVD, or market-wide order-flow visibility. All new labels are descriptive research features, not live trading rules.

## Current implementation limits

- The initial module uses midpoint direction changes as a **tick-pressure proxy**. Its positive/negative values are tick counts, not traded volume and not aggressor-side delta.
- Sweep/reclaim is based on the last closed chart bar against a prior 20-bar range. It is a diagnostic event, not an order-flow-confirmed entry.
- Absorption and exhaustion are rough heuristics and can produce false positives; they must be validated and may need redesign.
- DOM, true footprint delta, stacked bid/ask imbalance, iceberg detection and spoofing detection are not implemented because a suitable Level-2/exchange feed has not been established.
- The diagnostic hook writes versioned per-bar evidence and a separate exact SignalID-to-event-key attribution file when signal logging is enabled. Direct attribution is preferred. The analyzer's optional time-based fallback must be explicitly reported and must never be used when an attribution file was supplied but a link is missing or invalid.

## Validation gates

1. Compile the EA and indicator in MetaEditor; the repository's include validator alone is not an MQL5 compiler.
2. Unit-test feature math with synthetic ticks/bars: buy pressure, sell pressure, neutral flow, sweep-and-reclaim, breakout acceptance, absorption proxy, exhaustion, missing ticks, stale timestamps, and gaps.
3. Verify no look-ahead/repainting and deterministic replay on the same recorded data.
4. Run matched backtests against the unchanged baseline with identical symbols, dates, spreads, commissions, swaps, slippage, sizing, and execution assumptions.
5. Evaluate net expectancy in R, profit factor, maximum drawdown, trade count, average trade, loss streaks, long/short split, session/regime split, and calibration. Avoid optimizing only win rate.
6. Use chronological walk-forward and locked out-of-sample data; require adequate resolved sample size and confidence intervals before promotion.
7. Forward-test on Exness demo and reconcile every signal/order/outcome before any live deployment.

## Promotion rule

No claim of improved profitability, higher accuracy, or production readiness is allowed until the EA compiles, tests pass, and a predeclared out-of-sample comparison beats the baseline after realistic costs without unacceptable drawdown. A YouTube lesson is a hypothesis source, not evidence that a trading rule has an edge.

## Source-learning checklist

Use [`docs/ORDER_FLOW_LESSON_MAP.md`](ORDER_FLOW_LESSON_MAP.md) for the verified educator/exchange sources, lesson-level concept mapping, and the corresponding Midas-touch2 research hypotheses. The verified educator name is Axia Futures; “Axia Fusio” remains unverified. Do not attribute a specific rule to a teacher unless the exact lesson/video and timestamp are recorded. All extracted rules remain hypotheses until independently tested.
