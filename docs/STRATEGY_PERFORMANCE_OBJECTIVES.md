# Strategy performance objectives: 600% net return and 87% win rate

## Status

These are **aspirational research objectives, not promised or demonstrated results**. Current StrategyTune evidence does not meet them: the 60% TP1 / 20% TP2 exit candidate remains negative in two of three tested windows, and the revised entry-filter candidate underperformed its baseline on the untouched June–September 2026 window.

The latest research used USD-denominated StrategyTune capital and IC Markets data/cost assumptions; it is **not** proof of results on a KSh 1,500 Exness account. Any claim for the actual account requires its account currency, Exness symbol contract, volume minimum, commission, spread, slippage and swaps to be represented accurately.

## Exact definitions before a run can count

- **600% cumulative net return:** net realized profit after commission, swap, fees and a declared spread/slippage model equals six times starting equity; end equity before deposits/withdrawals is seven times starting equity. For KSh 1,500, that means KSh 9,000 net profit and KSh 10,500 ending equity before deposits/withdrawals and tax.
- **87% accuracy:** at least 87% of completed positions are net winners, computed at the position level after all partial exits, commissions, swaps and fees are consolidated. Do not count individual deal rows or partial exits as independent trades.
- **Horizon:** declare the test start and end dates in the experiment manifest before running. Use a one-year horizon for the initial planning target unless a different horizon is explicitly approved. Never change the horizon after inspecting results to make a target appear achieved.
- **Account profile:** record the selected EA profile and account balance/currency. A result from the large-account 15–20% profile cannot be used as evidence for the conservative KSh 1,500 small-account profile.

## Experimental protocol

1. **Lock the baseline.** Save the exact EA source SHA, compiled EX5 hash, terminal build, symbol, timeframe, profile, tick-data hash, spread, commission, slippage, swaps, order-fill rules and volume contract. Keep a copy of every input preset and report.
2. **Use chronological validation.** Tune only within the development window. Use three chronological folds and then a locked out-of-sample window. Do not re-tune on the locked period. If data are too short, report insufficient evidence rather than relabeling a development window as out of sample.
3. **Measure position-level outcomes.** Report net expectancy in currency and R, win rate with a 95% Wilson confidence interval, profit factor, mean win/loss, maximum equity drawdown, worst loss streak, exposure and completed-position count. A high win rate without positive net expectancy is a failure.
4. **Stress execution costs.** Include actual base costs and separately apply predeclared adverse spread-widening and slippage stress. Recalculate the same metrics under stress; do not charge historic spread twice.
5. **Preserve safety limits.** Never increase risk, widen drawdown limits, bypass the execution ledger, disable dynamic stops, override broker minimum volume, or force entries just to meet a return/trade-count objective. On the KSh 1,500 profile, planned stop risk stays at or below 0.5% per trade (KSh 7.50 at that equity), with a one-position cap. If minimum permitted volume exceeds the budget, reject the trade.
6. **Demand repeatability.** The candidate must show positive cost-adjusted expectancy in each validation fold, not only a pooled headline. Report all losses, drawdowns, blocked trades, open-position censoring, and uncertainty. Do not market or promote 600% / 87% unless they are reproduced on untouched out-of-sample data under the declared costs and account profile.

## Current decision

No candidate is currently approved as meeting either target. Preserve the production entry/stop rules and the current demo safety gates while gathering correctly matched Exness evidence. Profit targets can guide what to study; they must not override risk and execution controls.
