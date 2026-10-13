# Cost, Walk-Forward, Monte Carlo, Regime and Locked-OOS Protocol
Date: 2026-10-13
Status: research-only; no promotion or live-trading approval

## 1. Decision boundary

Every performance claim must use actual MT5 Strategy Tester exports generated from the EA build being assessed. StrategyTune proxy results are not substitutes for the EA, Exness execution, tick-level drawdown, or broker accounting. The prior proxy runs revealed an 18-loss maximum streak and negative expectancy in development and the second inspected holdout. Treat streak reduction as a hypothesis to test, not as an outcome already achieved.

Do not merge or deploy the candidate, or enable higher-timeframe trailing by default, on the strength of Python tests or a MetaEditor compile alone.

## 2. Cost accounting before scoring any run

Use the same Exness-representative real-tick bid/ask dataset, instrument specification, tester model, EA build, initial balance, leverage, sizing, fill policy, and date boundaries for each paired variant.

Retain the actual .set input file, HTML tester report, complete deals CSV, open-position ID CSV, and tick-data/dataset archive. Hash every artifact. Deal CSVs must explicitly include commission, swap, and fee fields—even when a value is genuinely zero. Missing cost fields mean the test is not scoreable; a parser must not silently turn missing data into zero. Net position results are the sum of deal profit + commission + swap + fee across every opening and closing deal.

With real-tick fills, the baseline bid/ask spread is already reflected in execution prices. Do not charge that spread a second time. Stress incremental spread widening above the observed baseline and incremental slippage per executed fill. The stress harness requires the account-currency value of one symbol point per 1.0 lot from the exact tester symbol specification. Record its source and hash. It is not acceptable to guess that value. The standard stress grid is additional full-spread widening of 0, 2, and 5 points crossed with 0, 1, and 2 extra slippage points per deal-side fill; add wider stresses if observed broker data supports them.

Run the cost/robustness diagnostic after exporting actual MT5 deals:

    python tools/cost_stress_monte_carlo.py --deals candidate_deals.csv --open-positions candidate_open_positions.csv --point-value-per-lot VALUE_FROM_TESTED_SYMBOL_SPEC --initial-balance 10000 --start 2025-01-01T00:00:00Z --end 2026-09-01T00:00:00Z --spread-widening-points 0,2,5 --slippage-points-per-fill 0,1,2 --train-months 4 --test-months 2 --folds 4 --simulations 10000 --seed 20261013 --output cost-stress.json

Replace VALUE_FROM_TESTED_SYMBOL_SPEC only with the confirmed value for the tested symbol/account currency. The example development sample ends on 2026-09-01 and must exclude the reserved OOS interval below. This harness estimates closed-position/settlement drawdown; it cannot reconstruct MT5 tick-by-tick equity drawdown. Keep the native Strategy Tester equity drawdown report as an independent measure.

## 3. Chronological walk-forward

Freeze entry/exit parameters, costs, regime definitions, and success criteria before evaluating each fold. A fold's test interval must occur strictly after its train interval. If parameters are tuned at all, do that only within the training segment and freeze them before the corresponding test segment. The committed harness reports chronological train/test windows for a fixed configuration; it does not perform the parameter fitting step and must not be described as a full automatic walk-forward optimizer.

Report all fold outcomes, including empty/low-sample folds; do not cherry-pick a profitable fold. Each fold should show net P&L, PF, net expectancy per fully closed position, loss streak, closed-position drawdown, number of completed/censored/open positions, and the native MT5 tester equity curve/drawdown where available. Use enough years and regimes to include trend, range/chop, high volatility, low volatility, gaps, and spread spikes. If the history is too short for four meaningful folds, reduce the number of folds explicitly rather than treating empty folds as evidence.

## 4. Monte Carlo: what it answers and does not answer

Run at least 10,000 fixed-seed simulations for reproducibility. Report P05/P50/P95 drawdown and consecutive-loss streak. The trade-order shuffle without replacement preserves the observed outcomes and total net P&L but changes sequence risk; it illustrates path dependence. The bootstrap with replacement also changes the sampled outcome distribution and final balance, illustrating sampling uncertainty. These are not predictions of future returns and do not model serial regime dependence; interpret them alongside chronological walk-forward folds and the native tick-level MT5 equity curve. If loss clusters are regime-dependent, also resample within chronological/regime blocks as a separate, clearly labeled robustness analysis rather than relying on independent shuffles.

## 5. Trend-versus-chop experiment

InpRequireTrendingRegime is a new research-only input and must remain false in the standard candidate preset until evaluated. The experimental gate permits entries only when the existing classifier says TRENDING; RANGING, TRANSITION, or undefined reads fail closed while the gate is enabled. Its classifier must use completed candles to avoid regime repainting. This gate may cut valid range setups and may lower trade count, so it is not automatically an improvement.

Run a paired OFF-versus-ON comparison with every other input, source build, data hash, spread/cost model, risk setting, and test window identical. Compare both aggregate results and segment results for TRENDING, RANGING, TRANSITION, volatility quantiles, long/short direction, and session. Report trades avoided, percentage reduction in maximum loss streak, PF, cost-complete expectancy, native equity drawdown, closed-position drawdown, losing streak distribution and opportunity cost. Do not change the regime classifier/threshold after inspecting a fold's test results. If the research implementation is changed, that version requires new validation folds and a new OOS interval.

## 6. Matched weekly/monthly trailing-stop toggle experiment

Run the exact same EA source/build, terminal build, tick dataset, symbol, period, initial balance, leverage, risk sizing, fill policy, and all non-trailing inputs. The only intended .set difference is InpDynamicStopUseHTFReferenceLevels=false versus true. Keep InpDynamicStopUseWeeklyReference=true, InpDynamicStopUseMonthlyReference=true, and the same InpDynamicStopHTFMaxDistanceATR value in both presets; with the master switch off, the references are inert.

Export the .set, HTML report, deals, open positions, and identical data archive for each run. Compare costs, net expectancy, PF, loss streak, stop-modification counts/rejections, native MT5 equity DD, and per-position closed DD on the development/validation period. Inspect SL-change audit logs for monotonic stop movement, wrong-side stops, rollover behaviour, unavailable HTF history, weekly/monthly boundaries, gaps, spread spikes, broker stop/freeze levels, partial closes, and restart recovery. A Python source-contract check does not prove live stop modifications are valid.

Keep HTF reference trailing off by default unless all required engineering checks and robust cost-complete validation pass. The weekly and monthly anchors may be overly distant, poorly timed, or harmful; no success is assumed.

## 7. Locked out-of-sample reservation

Prior recorded proxy tests in the current research log end on 2026-09-01. Reserve [2026-09-01T00:00:00Z, 2026-10-01T00:00:00Z) as the candidate's locked-OOS entry window, with maturity observation through 2026-10-14T00:00:00Z so eligible positions have time to close. Before relying on it, confirm the interval has not been inspected, used for tuning, or included in any external or unrecorded analysis. If it has been touched, this is not a fresh OOS set; select a later genuinely untouched interval and register it before viewing its metrics.

No metrics, charts, per-trade outcomes, or filtered subsets from this interval may be queried for model choice before the configuration, cost stresses, scoring rules and promotion criteria are frozen. Run and score it once after that freeze. Include only positions opened in the OOS interval and fully closed before 2026-10-14; positions still open or crossing the boundary remain censored and separately counted. Do not repair a poor OOS result by tuning the same interval. Any post-OOS change requires a newly reserved future OOS interval.

## 8. Minimum promotion evidence

All must be satisfied before a demo-forward test is considered: cost-complete positive expectancy; robust out-of-sample PF greater than 1 across more than one market regime; transparent trade/censoring counts; acceptable native MT5 equity drawdown and Monte Carlo P95 drawdown/streak risk; no unexplained deal-history/accounting differences; reproducible matched .set/build/data hashes; successful stop safety/restart/reconciliation tests; and a locked OOS interval evaluated only once. A green pipeline is an engineering prerequisite, not profitability evidence.
