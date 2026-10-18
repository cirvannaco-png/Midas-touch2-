# Midas-touch2 Order-Flow Confirmation Engine

## Status and safety boundary

This document defines the implementation plan for integrating order-flow concepts into the existing MQL5 EA. The first implementation is **diagnostic-only**. The branch now contains `EA/includes/Analysis/OrderFlowDiagnostics.mqh` and an opt-in closed-bar hook in `EA/MedisTouch_v2.8.mq5`. The hook is disabled by default and does not change entries, exits, confidence, lot sizing, SL/TP, trailing stops, or execution. It has not yet been compiled in MetaEditor.

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
- [ ] Add persistent CSV fields and outcome linkage after confirming compatibility with current log consumers.
- Feed it only timestamped data available at decision time. Use closed bars for bar-based features; no future bars, hindsight pivots, or post-fill information.
- Integrate after data collection and before decision routing as a **diagnostic evidence object**. Keep the existing `CScoringEngine::CalculateConfidence()` arithmetic and all risk/execution controls unchanged in the first phase.
- Log feature values, data quality, source/timeframe, decision ID, symbol, direction, and outcome linkage to appended/versioned fields. Do not silently change existing CSV column positions or parsers.
- Add explicit inputs for enabling diagnostics and thresholds; defaults must preserve existing trading behavior.
- Preserve the production trailing stop, emergency stop, account risk profiles, spread/session/news guards, broker reconciliation, and restart recovery.
- Only after evidence review may a separate opt-in confirmation gate be introduced. A hard gate must fail closed when it is explicitly required but the required data is unavailable; diagnostic-only mode may report unavailable without blocking trades.

## Current implementation limits

- The initial module uses midpoint direction changes as a **tick-pressure proxy**. Its positive/negative values are tick counts, not traded volume and not aggressor-side delta.
- Sweep/reclaim is based on the last closed chart bar against a prior 20-bar range. It is a diagnostic event, not an order-flow-confirmed entry.
- Absorption and exhaustion are rough heuristics and can produce false positives; they must be validated and may need redesign.
- DOM, true footprint delta, stacked bid/ask imbalance, iceberg detection and spoofing detection are not implemented because a suitable Level-2/exchange feed has not been established.
- The diagnostic hook currently prints to the terminal log; it does not change trade behavior or write persistent outcome-linked fields.

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

Map the supplied Axia Fusio/Axia Futures lesson links and timestamps to each concept before asserting that a particular rule came from the creator. The repository owner should provide the exact channel/playlist/video URLs to distinguish the intended creator and avoid attributing concepts to the wrong source.
