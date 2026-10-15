# MT2 Win–Loss Asymmetry Guard — Research Record

## Ownership and isolation

- **Project:** Midas-Touch2
- **Subsystem:** Exit-policy research / scale-out analysis
- **Architectural layer:** Research and analytics; not the authoritative EA decision or execution path
- **Change type:** Isolated experiment and validation protocol
- **StrategyTune artifact:** `MT2 Win-Loss Asymmetry Guard Lab v1`
- **StrategyTune script ID:** `x6icbrxw78jpll0pf5juy9b3`
- **Compiled StrategyTune version:** 3
- **Production status:** Not promoted. No MQL5 EA or production backend change is included in this experiment.

The repository's research/live boundary remains in force. This record specifies a candidate and its validation contract; it does not enable the exit policy in the EA.

## Why this experiment exists

A prior baseline reference run over 2024-10-07 to 2025-01-05 reported 189 grouped positions, 144 wins and 45 losses (76.19% position-level win rate), but net P&L was **-$299.90**. The reported average winner was about **+$5.58** and average loser about **-$24.51**. The strategy could therefore win most positions and still lose money because the average loss materially exceeded the average win.

A different recent-window reference (2026-07-01 to 2026-10-06) reported positive net P&L, but that does not establish robustness across regimes. These are prior reference results, not results for this candidate.

The target is positive **net expectancy per position** and a healthier average-win/average-loss ratio, not win rate in isolation.

## Candidate exit profile

| Input | Candidate value |
|---|---:|
| TP1 | +0.50R |
| Close at TP1 | 65% of initial position |
| TP2 | +1.50R |
| Close at TP2 | 20% of initial position |
| Remaining runner after both scale-outs | 15% |
| Stop protection after TP1 | +0.08R |
| Trailing stop after TP2 | 1.5 ATR |
| Maximum hold | 180 M15 bars |
| Risk per new position | 0.25% of balance |
| Portfolio open-risk ceiling | 2.25% |
| Daily entry target | At least 3 when valid setups are available |
| Daily cap | 6 by default; use 3 in the primary controlled comparison |

The TP2 close is defined as a fraction of the **initial** position; the strategy translates it into a fraction of the then-remaining quantity. The script maintains a 15% runner after both partial exits.

## Hypothesis and arithmetic checks

At TP1, the first scale-out realizes 0.65 × 0.50R = **+0.325R**. If the remaining 35% then exits at the +0.08R protective stop, it contributes another 0.35 × 0.08R = **+0.028R**, for a nominal **+0.353R** trade before execution costs.

Under the deliberately simplified two-outcome case of +0.353R winners and -1R losers, the break-even win rate is approximately 73.9% before costs. Real outcomes vary because some trades reach TP2, the runner's trailing stop can exit at different R values, and execution costs matter. This arithmetic is a sanity check, **not a forecast**.

The key hypothesis is that the larger TP1 payout, the 1.5R second target and the remaining runner improve average realized R per winner enough to outweigh any reduction in TP1 hit rate. Only paired backtest evidence can confirm or reject it.

## Controlled test protocol

Use identical strategy-entry logic and common run settings for every exit candidate:

- Instrument/data: StrategyTune `Gold`, provider `icmarkets`, M15.
- Starting balance/account currency: USD 10,000.
- Risk fraction: 0.25%; portfolio open-risk ceiling: 2.25%; concurrent lots: 9.
- Primary comparison: min daily entries = 3, max daily entries = 3 to control for entry count.
- Reference windows: 2026-07-01 through 2026-10-06, and 2024-10-07 through 2025-01-05.
- Save each session and reconcile positions by `openingFillId`; multiple rows caused by scale-outs are not separate entries.
- Use the platform's aggregate account P&L as the authority for net P&L. Do not substitute incomplete script-side `lastClosedTrade` instrumentation for the session ledger.
- Run a separate max-6-entry comparison only after the controlled max-3 comparison, to measure the extra-opportunity policy without mixing it into the exit-only experiment.
- Declare a previously unused locked-OOS window before inspecting candidate results; the two reference windows above are **not** to be called locked OOS because they have already been inspected during research.

### Required metrics

Record net P&L, expectancy in R, mean and median winning R, mean and median losing R, average winner/average loss, position-level win rate, profit factor, maximum drawdown, MAE/MFE, 2R and 3R reach rates, average holding time, position-level outcome by entry tier, daily entry compliance, and winning/losing movement in broker-normalized pips. Use the actual instrument/broker pip-size metadata; do not assume a universal Gold pip convention.

The standard StrategyTune report groups partial-close rows differently from independent positions. All position-level win/loss statistics must group by `openingFillId`.

## Known limitations and risks

1. StrategyTune has currently refused fresh cloud runs because the free account exhausted its daily compute budget (reported 11 minutes used against a 10-minute limit). **No backtest result exists for this candidate yet.**
2. StrategyTune's documented automated backtest does not model commission or slippage. Recorded bid/ask prices account for spread, but a positive result still needs separate cost stress and parity review before it could support promotion.
3. A daily trade count is not an unconditional instruction to take weak signals. Fallback tiers require separate expectancy-by-tier review. If the minimum cannot be reached with validated opportunities, record the shortfall rather than treating a low-quality forced entry as success.
4. Custom script-side closed-trade instrumentation can miss multiple close records on a single update. The saved session ledger grouped by `openingFillId` is the source for position-level results.
5. StrategyTune is a research artifact, not the MT5 EA. Its API, entry/exit timing, symbol metadata and fills must not be assumed to match the production EA.

## Promotion gate

This candidate stays research-only until it passes the existing repository research gates:

1. Reproducible controlled comparisons and complete finite metrics.
2. Positive locked-OOS expectancy and profit factor greater than 1 after execution-cost stress.
3. At least 30 locked-OOS positions and 3 consistent walk-forward folds, with no divergent fold hidden by aggregate results.
4. Scale-out replay evidence demonstrating the exit-policy improvement; report paired expectancy delta and outperformance fraction where scenario pairing is available.
5. Sensitivity/plateau checks around TP1, TP2, trailing ATR and stop offset, rather than accepting one sharp parameter optimum.
6. EA/Strategy Tester parity, MQL5 compilation, green CI, controlled demo forward test and rollback path before any production promotion.

A compile-successful StrategyTune script is not a performance certification. A favorable in-sample or recent-period result alone does not pass this gate.
