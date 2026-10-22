# Multi-Timeframe Structure Alignment Gate

## Status

Research-only. The EA input `InpRequireMtfStructureAlignment` defaults to `false`. No live strategy behavior changes unless the input is explicitly enabled. This gate is not a claim of improved win rate or profitability.

## Decision contract

When enabled, a proposed direction must pass every distinct context supplied to the scoring engine:

1. A directional trend state agrees with the proposal.
2. The most recent confirmed BOS exists and points in the proposed direction.
3. The BOS event's stored bar index resolves to the same candle timestamp, guarding event/candle provenance.
4. BOS freshness is measured against that context's completed bars. `InpMtfMaxBosAgeBars` is interpreted independently for each timeframe and is clamped to 1–500.
5. A newer opposing CHoCH blocks the direction; an older CHoCH cannot overrule a later confirmed BOS.

If the trend and BOS roles use the same timeframe, that context is checked once. If they use distinct timeframes, both must pass. Missing or inconsistent evidence fails closed while the research gate is enabled. When disabled, the pre-existing scoring path remains in control.

## Validation needed before promotion

Run the actual MT5 EA on identical symbol, timeframe, date windows, real-tick data, spreads, commissions, swaps, slippage assumptions, risk profile, and execution settings:

- Baseline: gate OFF.
- Candidate variants: gate ON with BOS-age limits (e.g. 10, 20, 30 bars) selected before inspecting the final holdout.
- Compare trade count, setup rejection reasons, cost-inclusive expectancy, profit factor, maximum equity drawdown, consecutive losses, time in market, and results by symbol/session/regime.
- Use a development window for selection, walk-forward folds for stability, and a locked out-of-sample period not used to tune the age threshold.
- Archive source/build hash, input set, tester report, full deals, and accounting reconciliation. Verify MetaEditor compilation for the exact tested commit.

Do not enable this gate in production merely because source contracts or CI pass. Keep the production default OFF until matched MT5 evidence demonstrates a robust net improvement without unacceptable opportunity loss or risk concentration.
