# Payoff Asymmetry and Entry-Precision Candidate (v2.82)

## Why this candidate exists

The prior position-management defaults closed 50% of a position at +2R. If the remaining 50% subsequently exits at breakeven, the partial has realized only +1.0R on the original full-position risk basis before fees. A full stop is about -1.0R before gap risk and costs. Commission, spread, and slippage can therefore make the average net winner materially smaller than the average net loser, even when the partial target was hit.

This is a mechanical hypothesis explaining the observed asymmetry, not a claim that it accounts for every losing trade. Confirm it with broker-deal outcomes and the actual MT5 tester.

## Candidate changes

- Raise the minimum TP1-to-stop ratio from 1.5R to 1.8R.
- Move the 50% partial realization threshold from +2.0R to +2.5R. If the other half subsequently exits at entry, the partial locks +1.25R gross on original position risk, versus +1.0R before this change. Reaching +2.5R may be less frequent, so expectancy must be measured rather than assumed to improve.
- Increase the manual final target from 2.0R to 2.4R, remaining above the manual target validation floor.
- Enable the existing minimum sweep-grade, setup-freshness (maximum five bars since BOS), and anti-chase (maximum 0.75 ATR) gates by default in this research candidate.
- Require a five-point directional-confidence advantage when both directional setups are active, avoiding arbitrary selection when the competing setups are nearly tied.
- Align the outcome simulator's configured breakeven threshold and ATR trail multiplier with the corresponding dynamic-stop inputs, reducing avoidable configuration drift.
- Bump strategy/calibration/weight-set labels so candidate evidence is explicitly attributable.

## What remains an approximation

The shadow outcome simulator is bar-OHLC based. It does not reproduce every tick-level broker fill, the live dynamic stop's +0.75R activation, confirmed structural-stop anchoring, or all multi-leg execution effects. Its outcomes are diagnostic evidence, not a replacement for MT5 Strategy Tester deal history. The costs used in tests must reflect the actual account and symbol.

## Required validation before promotion

Run the unchanged main-branch baseline and this candidate against the same XAUUSD tick-data snapshot, MT5 terminal/build, timeframe, date range, spreads, commissions, slippage, fill policy, initial balance, leverage, and risk percentage. Export the actual .set file, HTML tester report, deal-history CSV with commissions/swaps/fees and position identity, open-position CSV, and data hash for every variant. Freeze a chronological locked-OOS interval before reviewing candidate results.

Evaluate full-period and locked-OOS: net expectancy in R, average winner and loser in R and cash, profit factor, win rate with uncertainty, maximum equity drawdown, consecutive losses, trade count, costs per trade, and performance by strict/continuation lane and market regime. Do not promote solely because win rate rises or losses shrink in a small sample. Require positive locked-OOS expectancy, PF above 1 after all costs, reasonable sample sufficiency, and stability across neighboring configurations.

The current free-tier research tooling has not completed a matched intraday comparison. Therefore this branch is a test candidate only; it is not evidence of consistent profitability and must not be treated as approved for live deployment.
