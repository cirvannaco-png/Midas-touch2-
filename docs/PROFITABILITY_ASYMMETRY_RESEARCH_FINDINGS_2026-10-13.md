# Profitability Asymmetry Research Findings — 2026-10-13

## Decision

**Do not promote the EA candidate to live trading.** These StrategyTune runs are exploratory proxy tests of a separately implemented research strategy on IC Markets' recorded Gold (XAUUSD) M15 bid/ask data, not MT5 Strategy Tester results for the EA and not Exness execution results. They do not include commission, swaps, or slippage. The StrategyTune script's own custom position accounting is internally inconsistent (`accountingValid=false`), so this report derives trade outcomes from saved platform trade rows, groups partial-close rows by `openingFillId`, sums realized P&L, and excludes entry groups with an open remainder.

## Method

- Research script: `MT2 Dual-Lane Asymmetric Runner Lab v1`, ID `m10am23hi9v3zlt51oaskrja`, version 7.
- Instrument/data: IC Markets `Gold`, M15, account currency USD, starting balance USD 10,000; recorded bid/ask price stream (spread reflected in fills).
- Baseline: script defaults; strict, single-swing, continuation and micro-momentum lanes enabled.
- Exit candidate: same entry settings, but both standard and opportunity exits changed to TP1 2.2R, TP2 2.5R, min runner RR 2.2R, TP1 fraction 50%, TP2 fraction 20%.
- **Parameter-parity limitation found during follow-up audit:** in the MT5 EA, `InpMinRiskReward` is a setup-validation floor on `setup.tp1` versus stop distance (`CRiskEngine::ValidateSetupAtEntry`), while `InpPartialAtR` is the live partial-close trigger (`CPositionManager::OnTick`). The StrategyTune proxy's `tp1RR` is a realized partial-exit trigger, not a setup-validation floor. Therefore, its `tp1RR=2.2` experiment is not a parameter-faithful simulation of the EA's simultaneous `InpMinRiskReward=2.2` and `InpPartialAtR=2.5` changes. Results below are exploratory diagnostics, not a verdict on the exact MT5 candidate; a dedicated proxy entry-quality gate would be needed for tighter behavioral parity.
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

## Follow-up: strict-lane ablation and partial-exit stress test — 2026-10-13

To isolate the exit effect, additional paired runs disabled the proxy's single-swing, continuation, and micro-momentum lanes. This changes the experimental question: it is a **strict-lane diagnostic**, not a replication of the all-lanes report above. The same StrategyTune Gold M15 data stream and account settings were used within each date window. Results below group saved trade rows by `openingFillId`, combine partial closes, and exclude any entry with an open remainder.

### Strict lane — 2026-07-01 to 2026-09-01

| Metric | Baseline exits | Aggressive proxy exits (2.2R / 2.5R) |
|---|---:|---:|
| Fully closed opening fills | 22 | 19 |
| Net P&L on closed opening fills | -$191.85 | +$24.95 |
| Profit factor, grouped by opening fill | 0.289 | 1.081 |
| Win rate | 50.0% | 31.6% |
| Average winner | $7.08 | $55.45 |
| Average loser (absolute) | $24.52 | $23.67 |
| Expectancy per completed opening fill | -$8.72 | +$1.31 |
| Maximum consecutive losses | 6 | 6 |
| Platform-reported maximum drawdown | $226.21 | $181.31 |

The aggressive variant had **one open entry group at the end** with approximately $17.90 floating P&L; that is excluded from its +$24.95 realized P&L. This one window is directionally better for the aggressive proxy exits, but the sample is small and the same proxy's custom accounting flags remain invalid. It is not proof of durable profitability.

### Strict lane — 2026-09-01 to 2026-10-01

| Metric | Baseline exits | Aggressive proxy exits (2.2R / 2.5R) | Hybrid proxy exits (0.75R / 2.5R) | Baseline exits + tighter concurrency/risk cap |
|---|---:|---:|---:|---:|
| Fully closed opening fills | 12 | 12 | 12 | 10 |
| Net realized P&L | -$289.32 | -$486.22 | -$274.83 | -$270.15 |
| Grouped profit factor | 0.051 | 0.000 | 0.099 | 0.036 |
| Win rate | 25.0% | 0.0% | 25.0% | 20.0% |
| Average winner | $5.21 | — | $10.04 | $5.03 |
| Average loser (absolute) | $33.88 | $40.52 | $33.88 | $35.03 |
| Expectancy per completed opening fill | -$24.11 | -$40.52 | -$22.90 | -$27.01 |
| Maximum consecutive losses | 8 | 12 | 8 | 7 |
| Platform-reported maximum drawdown | $299.88 | $517.06 | $321.68 | $280.71 |

The hybrid configuration modestly reduced this month's loss relative to baseline but remained deeply unprofitable. Limiting the proxy to 2 concurrent lots and 0.50% portfolio risk reduced the number of entries but did not resolve negative expectancy. **No configuration passed a profitability gate.**

### Trade-level finding: delayed partials amplify adverse clusters

On 2026-09-04, the same three long entry groups were stopped at the same observed price of 4427.55, well beyond their recorded stop levels near 4459.9. With baseline exits, the third entry group partially exited earlier and booked about $5.58; with the 2.2R proxy partial trigger, the full group remained open and closed for approximately -$141.34. Two other concurrent long groups lost roughly $65.62 and $70.08. This illustrates two risks that must be treated separately:

1. Raising the first partial trigger can remove small, early realized winners in choppy conditions and leave the full size exposed until the stop is reached.
2. A stop level does not guarantee the fill price when the next available quote is beyond the stop. The example is a historical quote-stream gap/overshoot in the proxy, not a commission/slippage model and not evidence of identical Exness behavior.

This makes exact position sizing, concurrent same-direction exposure controls, gap/slippage stress, and true broker/tick-ledger reconciliation mandatory before using any R-target change in the EA.

## Parameter-parity correction

The MT5 source confirms that `InpMinRiskReward` is used by `CRiskEngine::ValidateSetupAtEntry` to reject a setup when the planned setup TP1's reward distance is below the configured multiple of stop distance. The live partial-close threshold is separately supplied by `InpPartialAtR` to `CPositionManager`. The StrategyTune experiment changed `tp1RR`, which makes the proxy wait longer to take a partial; it did **not** implement the same setup-validation gate as the EA. Consequently, the proxy experiments show that delayed partials can fail badly in some windows, but they do **not** provide a faithful A/B measurement of the exact EA changes in PR #76.

The next actual-EA experiment must be run in MT5 with identical input presets except for clearly isolated toggles: baseline setup R:R floor, candidate setup R:R floor, baseline partial threshold, and candidate partial threshold. First test the setup gate independently from the partial-exit threshold, then test the combined candidate. Capture the exact .set files, build hash, real-tick tester reports, deal rows including all costs, and open/censored positions. Until that exists, keep the EA behavior unchanged and PR #76 draft.

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

- Strict-lane matched baseline, 2026-07-01 to 2026-09-01: run `51c99075-bf42-43e3-8750-d7de68e8245d`, record `bccom0zeaqmk5hzsftvzwgf3`.
- Strict-lane asymmetric proxy, 2026-07-01 to 2026-09-01: run `093dfbc5-9f75-4910-8677-228b5cb3af2f`, record `fkh8y8o7y86d3zuurm24uz3r`.
- Strict-lane baseline, 2026-09-01 to 2026-10-01: run `517cde11-0f8f-4d63-8b5d-55ad472ea9ad`, record `vyaeul2pzb0lrjmeuovctd9a`.
- Strict-lane aggressive proxy, 2026-09-01 to 2026-10-01: run `f1a406a9-2a45-46ea-b5b5-581fc263895c`, record `br51akapy6biw9kt3s1vox0k`.
- Strict-lane hybrid proxy (TP1 0.75R / TP2 2.5R), 2026-09-01 to 2026-10-01: run `2cc3b5ec-567a-4e3f-bd37-744421c8d0cc`, record `gizdy1zwdpblk3tbhf5jcwwe`.
- Strict-lane baseline exits with two-lot / 0.50% portfolio-risk cap, 2026-09-01 to 2026-10-01: run `1813dfd7-14a6-4609-b03e-8efa08281ec0`, record `oc1llqbs7265d7nbyzlc4kz8`.

These identifiers preserve the audit trail; they are not evidence that the actual EA has been validated.
