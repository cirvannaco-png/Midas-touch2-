# Weekly/Monthly Higher-Timeframe Trailing Candidate

## Status

Research-only implementation on the payoff/precision candidate branch. The feature is **disabled by default** with `InpDynamicStopUseHTFReferenceLevels=false`. Source tests and a successful compile are necessary engineering checks, not proof of trading success. Do not switch it on for live trading until the matched MT5 test gate below passes.

## Defined behavior

When the feature is enabled, the position manager may choose a nearby, confirmed reference from the most recently completed higher-timeframe candle:

- BUY positions use the previous completed weekly/monthly low as support.
- SELL positions use the previous completed weekly/monthly high as resistance.
- The reference uses shift `1`, not shift `0`, so the in-progress week/month does not become a moving, unconfirmed level.
- The closest valid protective level is chosen from the chart-timeframe confirmed swing and eligible W1/MN1 references: highest valid support below market for BUY, or lowest valid resistance above market for SELL.
- References on the wrong side of market or more than `InpDynamicStopHTFMaxDistanceATR` ATR away are rejected. A value of zero disables HTF candidates while preserving the chart-swing anchor.
- If the relevant HTF history is unavailable or no eligible level exists, the regular structural/ATR fallback remains available.

The selected level is only an anchor candidate. `CDynamicStopEngine` remains authoritative: stop activation, ATR buffer, spread checks, broker stops/freeze distance, minimum improvement, and the rule against widening an existing stop are still enforced. Existing partial-close logic is unchanged.

## Inputs

- `InpDynamicStopUseHTFReferenceLevels`: master switch; defaults to `false` pending validation.
- `InpDynamicStopUseWeeklyReference`: enables previous completed W1 reference evaluation.
- `InpDynamicStopUseMonthlyReference`: enables previous completed MN1 reference evaluation.
- `InpDynamicStopHTFMaxDistanceATR`: maximum eligible reference distance; defaults to 4.0 ATR.

## Required MT5 validation

Run matched variants with the same EA commit, symbol, timeframe, tick-data snapshot, test dates, balance, leverage, position size/risk, spread model, commissions, swaps, fees, slippage, fill policy, and all other inputs. Freeze the holdout interval before reviewing the candidate.

The test matrix must include (1) BUY and SELL positions, (2) W1/MN1 rollovers, (3) missing or delayed HTF history, (4) price gaps through reference levels, (5) broker stop/freeze constraints, (6) wide spreads, (7) partial closes and runner states, and (8) restart/recovery with an already-tightened SL. Verify every proposed SL is on the correct side of market, never loosens an existing SL, and is persisted/recovered correctly.

Report completed-position net expectancy after all costs, profit factor, average winning/losing R, trade count, equity drawdown, maximum consecutive losses, spread/commission/swap/fee totals, SL-modification rejection rate, and outcomes around week/month boundaries. Include an untouched locked-OOS result and compare against the identical build with the feature off.

## Acceptance and safety gate

Do not declare the feature successful based on compile success, source assertions, a few profitable trades, gross P&L, or a development-period result. Promotion requires the cost-inclusive locked-OOS gate to pass, no regressions in execution recovery or stop monotonicity, adequate trade count and stable results across more than one market regime. The current research proxy is not genuine MT5 or selected-broker validation; therefore this candidate is not approved for live use.
