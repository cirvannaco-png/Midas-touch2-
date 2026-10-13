# Profitability Asymmetry Research Findings — 2026-10-13

## Decision

**Do not promote the EA candidate to live trading.** These StrategyTune runs are exploratory proxy tests of a separately implemented research strategy on IC Markets' recorded Gold (XAUUSD) M15 bid/ask data, not MT5 Strategy Tester results for the EA and not Exness execution results. They do not include commission, swaps, or slippage. The StrategyTune script's own custom position accounting is internally inconsistent (`accountingValid=false`), so this report derives trade outcomes from saved platform trade rows, groups partial-close rows by `openingFillId`, sums realized P&L, and excludes entry groups with an open remainder.

## Method

- Research script: `MT2 Dual-Lane Asymmetric Runner Lab v1`, ID `m10am23hi9v3zlt51oaskrja`, version 7.
- Instrument/data: IC Markets `Gold`, M15, account currency USD, starting balance USD 10,000; recorded bid/ask price stream (spread reflected in fills).
- Baseline: script defaults; strict, single-swing, continuation and micro-momentum lanes enabled.
- Exit candidate: same entry settings, but both standard and opportunity exits changed to TP1 2.2R, TP2 2.5R, min runner RR 2.2R, TP1 fraction 50%, TP2 fraction 20%.
- Cost limitation: StrategyTune does not apply commission or slippage and this strategy does not model swaps. Results are therefore **not net-of-all-trading-costs**.
- Unit: completed opening-fill groups, with partial closes combined. Max consecutive losses is computed on fully closed opening-fill groups sorted by last close time. P&L uses the platform's row data.
- Maximum drawdown below is the platform's reported account drawdown; the platform result may include account-state effects that differ from the grouped completed-fill metric.

## Results

All windows ran to their requested end dates in this proxy environment. A separate longer 2025 run was cut short by the 1,000-operation limit and is excluded from this table.

### Development window — 2025-01-01 to 2025-03-01

| Metric | Baseline | Exit candidate |
|---|---:|---:|
| Fully closed opening fills | 201 | 170 |
| Net realized P&L on fully closed fills | -$337.42 | -$42.67 |
| Position-level profit factor | 0.643 | 0.967 |
| Win rate | 58.7% | 32.9% |
| Average winner | $5.14 | $22.52 |
| Average loser (absolute) | $11.38 | $11.44 |
| Average winner / average loser | 0.452 | 1.969 |
| Expectancy per completed opening fill | -$1.68 | -$0.25 |
| Maximum consecutive losses | 4 | 18 |
| Platform-reported max drawdown | $396.66 | $343.69 |

The exit hypothesis materially increased average winner relative to average loser and reduced the loss, but did **not** produce positive expectancy or a profit factor above 1 in this development window. The loss streak worsened substantially.

Two intermediate exit variants were also tested in this same development window only; neither was carried into the holdout periods:

| Exit-only variant | Fully closed opening fills | Net P&L on complete fills | Position-level PF | Win rate | Average win / loss | Expectancy per fill | Max loss streak | Platform max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TP1 0.75R / TP2 1.8R | 202 | -$384.89 | 0.683 | 48.0% | 0.739 | -$1.91 | 8 | $459.63 |
| TP1 1.0R / TP2 2.0R | 193 | -$409.84 | 0.679 | 43.0% | 0.900 | -$2.12 | 10 | $498.55 |

Both intermediate variants remained unprofitable in development. This weakens the case that simply moving the partial and runner targets to a moderate R multiple will solve the payoff issue. The aggressive 2.2R/2.5R test gave the best win/loss asymmetry of these tested exit-only variants, but still failed positive expectancy on development and the later holdout. No intermediate variant was selected based on OOS results.


### First inspected holdout window — 2026-05-01 to 2026-07-01

| Metric | Baseline | Exit candidate |
|---|---:|---:|
| Fully closed opening fills | 223 | 176 |
| Platform-reported closed P&L | +$34.43 | +$423.21 |
| Position-level profit factor | 1.045 | 1.360 |
| Win rate | 66.8% | 39.8% |
| Average winner | $5.15 | $22.84 |
| Average loser (absolute) | $9.92 | $11.09 |
| Average winner / average loser | 0.519 | 2.059 |
| Expectancy per completed opening fill | +$0.15 | +$2.40 |
| Maximum consecutive losses | 6 | 14 |
| Platform-reported max drawdown | $162.15 | $362.13 |

This period favoured the exit candidate, but the candidate also had a much longer loss streak and larger drawdown. This period has now been inspected and must no longer be treated as an untouched holdout.

### Second holdout window — 2026-07-01 to 2026-09-01

| Metric | Baseline | Exit candidate |
|---|---:|---:|
| Fully closed opening fills | 228 | 200 |
| Platform-reported closed P&L | -$295.90 | -$454.76 |
| Position-level profit factor | 0.691 | 0.692 |
| Win rate | 60.5% | 26.5% |
| Average winner | $4.82 | $19.29 |
| Average loser (absolute) | $10.69 | $10.05 |
| Average winner / average loser | 0.451 | 1.920 |
| Expectancy per completed opening fill | -$1.30 | -$2.27 |
| Maximum consecutive losses | 7 | 18 |
| Platform-reported max drawdown | $370.00 | $505.29 |

This later window rejects the idea that the exit-only hypothesis is consistently profitable: the candidate lost more than baseline, profit factor stayed well below 1, and the losing streak reached 18. The second window had fixed parameters before this test session, but it cannot be represented as globally untouched because prior exploratory research may have examined the dates.

## Assessment against the requested evidence

- **Improved post-cost expectancy:** not established. Cost-complete net expectancy is unavailable; raw simulated P&L is negative in the development window and the second holdout.
- **Healthier winner/loser ratio:** achieved in this proxy. The position-level average win/loss ratio increased to roughly 1.9–2.1 in the candidate windows.
- **Profit factor > 1 after costs:** failed as a robust criterion. Candidate PF was 0.967 in development, 1.360 in the first holdout, and 0.692 in the second.
- **Acceptable drawdown and losing streak:** not demonstrated. The candidate reached an 18-position loss streak and platform-reported drawdown of about 5.05% in the second holdout on a USD 10,000 start.
- **Positive locked out-of-sample:** failed consistency check. One two-month window was positive, the next was negative; the first window is no longer locked after inspection.
- **Enough completed trades:** each two-month window has hundreds of lot-close rows and 170–228 completed opening-fill groups, but the effective sample spans only two months per window, the data source differs from Exness and trading costs are incomplete. This does not substitute for a longer, frozen MT5 test.

## Next validation gate

1. Keep PR #76 as draft and do not merge/promote based on this proxy.
2. Run the actual compiled MT5 EA baseline and candidate on the **same Exness-representative real-tick snapshot**, same terminal/EA build, same spread/fill settings, initial balance, leverage and risk inputs. Preserve each .set file, HTML report, complete deal CSV, open-position IDs and data hash.
3. Account for deal profit, commission, fees, swaps and conservative measured slippage. Reconcile summed deal cash P&L to tester balance/equity; reject a run when accounting is incomplete or unexplained deltas exceed a stated tolerance.
4. Freeze an out-of-sample interval before any more tuning. Report completed **positions**, not partial-close rows: net expectancy in cash and R, average net winner/loser in cash and R, payoff ratio, profit factor, win rate, equity drawdown, maximum consecutive losses, trade count, long/short, lane, and regime splits. Report open/censored positions separately.
5. Predeclare acceptance conditions before seeing new results. At minimum require positive cost-complete expectancy, PF materially above 1 after costs, positive untouched OOS performance, acceptable drawdown/loss streak, no accounting errors, and adequate sample size across more than one market regime. Only then consider a small-risk forward/demo validation; do not switch directly to live deployment.

## Run identifiers for reproducibility

- Development baseline: StrategyTune run `5361edfe-00fd-449e-b8c6-74856e5d5d60`, record `l0s96qzv884gbdst5mjzfjc9`.
- Development exit candidate: run `6a022901-7aad-46c7-a498-5ffdcc7b45b2`, record `nc9s5s05d6mbibee61ma7xyb`.
- First inspected holdout baseline: run `40287737-b775-4cd3-be05-36fb7830719a`, record `aqyszj8bdtznqm8n8p6l1kma`.
- First inspected holdout exit candidate: run `6fa2ee8b-063a-4173-ba0f-aa99242b4ec8`, record `mnewrj4kxk1krfpht6wz2b3v`.
- Second holdout baseline: run `db4160ad-f930-4d2c-ab7f-4a98df55b02d`, record `zxe8ktn1bvuq67z5a84ttnqd`.
- Second holdout exit candidate: run `6477849d-326a-49e1-b5fe-71c594abc220`, record `eq7rpg394rlvygq8a86gpvdm`.

These identifiers preserve the audit trail; they are not evidence that the actual EA has been validated.
