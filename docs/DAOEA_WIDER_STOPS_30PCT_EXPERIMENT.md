# DaoEA wider-stop experiment — MidasTouch2 small account

## Status

Research-only protocol. This document does not change EA defaults, authorize deployment, or claim that any candidate is profitable. The production source of truth remains `main`. Work is isolated on `research/dao-wider-stops-30pct`.

## Account and risk invariant

- Starting capital supplied by the operator: KSh 1,500.
- Intended risk setting: 30% of current equity per trade, constant as a percentage (not a fixed KSh 450 amount).
- If the trading account itself is denominated in KES, the first planned stop-risk budget is KSh 450. If the broker account is denominated in another currency, use the actual MT5 account equity and account-currency conversion; do not hardcode KSh or assume an FX rate.
- All primary stop-distance arms must use exactly the same 30% risk input and identical portfolio/execution settings. Position size must be recalculated from the new stop price. Never keep the old lot size after widening the stop.
- The broker minimum volume must not be forced when its calculated stop-loss exceeds the budget. Reject the trade instead.
- A stop-loss is not a guaranteed maximum loss: gaps, slippage, execution rejection, commission and spread can cause realized loss to exceed the planned stop risk.

**Safety finding:** 30% risk per trade is extremely aggressive. A single planned stop loss removes 30% of current equity; consecutive losses compound. The experiment must remain in Strategy Tester and demo until separately reviewed. No live deployment or live-eligibility change is authorized.

## Current implementation facts

The current EA exposes `InpMaxSLDistanceATR=1.5`, `InpSLBufferATR=0.25`, `InpDynamicStopATRMult=1.50`, activation at `+0.75R`, and breakeven at `+1.00R`.

Important distinction: `InpMaxSLDistanceATR` is a validation ceiling; raising it alone does not move the generated stop farther away. The stop-generation buffer (`InpSLBufferATR`) and the resulting realized entry-to-stop distance must be inspected in the generated setup and verified from tester artifacts. The dynamic trailing multiplier affects the ATR fallback trailing distance; a supplied structural anchor may override that fallback.

The production EA also has a risk profile validator requiring per-trade risk below the daily-loss cap, and the portfolio risk cap cannot exceed that daily cap. A 30% setting therefore requires explicit, internally consistent test-only risk limits. Do not bypass validation or copy extreme research limits into production by default.

## Matched stop experiment

Use four primary arms, all with identical entries, signals, 30% per-trade risk, broker/account contract, execution costs, data, timeframe, EA build, tester build, sessions, partial exits, breakeven rules and portfolio settings.

| Arm | Stop-generation buffer | Maximum accepted SL distance | ATR trailing multiplier | Question |
|---|---:|---:|---:|---|
| A — baseline | 0.25 ATR | 1.50 ATR | 1.50 | Control |
| B — wider initial SL | 0.3125 ATR (1.25×) | 1.875 ATR (1.25×) | 1.50 | Does added structural room improve outcomes? |
| C — wider trail | 0.25 ATR | 1.50 ATR | 1.875 (1.25×) | Does a looser ATR trail retain more trend profit? |
| D — both wider | 0.3125 ATR | 1.875 ATR | 1.875 | Is there an interaction between the two changes? |

These multipliers are predeclared test candidates, not recommended production values. First verify the stop-generation code: if `InpSLBufferATR` is not the only parameter controlling the actual initial stop, document and isolate every parameter that materially changes the stop geometry before running. Do not silently change entry criteria, reward/risk thresholds, take-profit levels, partial-close settings or other strategy parameters to make an arm trade more often.

Because the current `tools/risk_trailing_experiment.py` comparator validates a different five-arm schema (including a specific trailing-only C and separate risk arms D/E), it must be extended and unit-tested before it can compare this four-arm contract. Do not mislabel the existing five-arm report as evidence for this experiment.

## Execution and evidence requirements

1. Preserve the current `main` commit and current defaults as the baseline.
2. Pin a single immutable real-tick dataset and hash it; use the same interval and locked out-of-sample window for all arms.
3. Export each arm's actual MT5 `.set`, HTML report, deals CSV, open-position IDs, and native balance/equity curve. Record EA source SHA, EA build, terminal build, broker, symbol, timeframe, account currency, leverage, contract/tick specification, spread, commission, swap, slippage assumptions and fill policy.
4. Use the same instrument-specific costs for every arm, including realistic commission, historical spread, swap and explicit adverse slippage/spread stress without double-charging costs already present in the tester.
5. Reconcile all positions and partial/final closes against the execution ledger before trusting metrics. Incomplete positions must not be fabricated as closed outcomes.
6. Report net expectancy, profit factor, mean win/loss, realized R, stop-out attribution, profit given back by trailing, maximum equity drawdown, consecutive losses, rejected trades due to minimum volume, and locked-OOS results. Include the account-currency amounts as well as percentages.
7. Use paired trade/market-period analysis where possible; inspect whether wider stops simply increase loss size or improve net expectancy. Do not select a candidate from in-sample profit alone.
8. Run the selected frozen candidate on the operator-selected MT5 broker's demo account with restart/recovery, emergency stop, broker stop/freeze-level, partial-close and ledger reconciliation checks.

## Promotion gates

No candidate is promoted unless:
- The four-arm comparison and its tests pass on the exact candidate commit.
- Native MetaTrader compilation succeeds for the exact source and all required includes.
- Genuine matched Strategy Tester artifacts exist and are hash-verified.
- The trade ledger reconciles and all close-capture discrepancies are resolved.
- The frozen candidate improves cost-inclusive out-of-sample expectancy without breaching predeclared equity drawdown constraints.
- Demo forward validation is complete.

A green source-level test or a plausible backtest is not proof of profitability. No production or live-account setting is changed by this protocol.
