# Research evidence audit — 24 October 2026

## Decision

**No strategy is promoted. Live trading remains blocked.** This audit is a record of completed exploratory checks, not a claim of profitability or a substitute for a locked, cost-inclusive out-of-sample study. StrategyTune scripts are research proxies; they are not the same runtime as the MQL5 EA.

## Completed matched StrategyTune checks

Both saved StrategyTune scripts were compiled when tested:

- **Causal variant:** `Midas Touch 2 Causal Research v2.1 Stop Guard`, script id `lzmsy4cracouh2ke701fei8k`, script version 3, `minQuality=62`.
- **Strict-threshold variant:** `Midas Touch 2 Strict Tier D v9 Stop Guard`, script id `y174sqzvqpjeoybnv8gghgh0`, script version 2, `minQuality=101`.

Matched conditions: Gold / IC Markets feed, M15, USD account, $10,000 starting balance per independent run, `riskFraction=0.25`, `maxDailyTrades=3`, `maxConcurrentLots=3`. Other inputs remained at each script's saved defaults. The only intended input difference between variants is `minQuality`. Date ranges are UTC and each window restarts the account at $10,000.

**Cost limitation:** the StrategyTune run interface did not accept explicit overrides for commission, slippage, or swaps. The strategy evaluates executable-side bid/ask quotes, but these runs must not be described as fully net-of-all-costs or promoted as proof of positive net expectancy. These were post-hoc historical robustness checks, not pre-registered untouched OOS folds.

| Window (UTC) | Variant | Run ID | Platform P&L | Max drawdown | Closed lots | Diagnostic position wins / losses | Diagnostic position win rate |
|---|---|---|---:|---:|---:|---:|---:|
| 2026-06-01 to 2026-07-01 | Causal | `d746b9bf-c4dd-4114-ae82-1a36fc893578` | +$9.00 | $56.36 | 126 | 53 / 12 (65 positions) | 81.54% |
| 2026-06-01 to 2026-07-01 | Strict threshold | `2f3a500f-9abb-4f03-86fb-6705cae24194` | +$1.56 | $48.07 | 126 | 53 / 12 (65 positions) | 81.54% |
| 2026-07-01 to 2026-08-01 | Causal | `24747412-626b-4bb0-9403-2516b9e05526` | +$0.25 | $72.64 | 137 | 53 / 14 (67 positions) | 79.10% |
| 2026-07-01 to 2026-08-01 | Strict threshold | `8998bf8c-ac2c-4d69-80a1-cf9c423eaf15` | +$65.80 | $33.88 | 139 | 55 / 13 (68 positions) | 80.88% |
| 2026-08-01 to 2026-09-01 | Causal | `96f12fcf-2ff0-41f6-a361-17f185f808c8` | -$24.52 | $59.78 | 116 | 48 / 14 (62 positions) | 77.42% |
| 2026-08-01 to 2026-09-01 | Strict threshold | `a5ea6edb-50d2-48e6-ad99-f9192d87330d` | +$11.78 | $45.36 | 120 | 50 / 12 (62 positions) | 80.65% |
| 2026-09-16 to 2026-10-16 | Causal | `23e62035-89ac-487a-88bb-8aa32ad3e5e9` | -$8.03 | $67.75 | 135 | 56 / 13 (69 positions) | 81.16% |
| 2026-09-16 to 2026-10-16 | Strict threshold | `db1de72f-b2ff-489f-b4a2-6f2aa4c66801` | +$16.27 | $47.67 | 137 | 57 / 12 (69 positions) | 82.61% |

All P&L and drawdown figures above are the StrategyTune engine's aggregates in USD. “Closed lots” are not equivalent to independent parent positions; the strategy's own grouped position statistics are shown separately and remain diagnostic.

### Findings and data-quality flags

1. **The 87% position-level win-rate target is not established.** Diagnostic grouped rates in these runs ranged from 77.42% to 82.61%, below 87%. The strict-threshold script explicitly reports `positionAttributionTrusted=0` and `closeEventStreamAvailable=0`; those custom grouped rates therefore cannot be treated as audited ground truth.
2. **Results depend heavily on the regime and variant.** The causal variant's platform P&L summed across its four independently reset windows is -$23.30, before explicit commission/slippage/swap charges. The strict variant's corresponding simple sum is +$95.41 on separate account resets, also before those charges. This sum is descriptive only: it is not compounded performance, not a locked OOS estimate, and not proof of a tradable edge.
3. **One causal-window attribution mismatch must be fixed.** In the July 2026 causal run, platform/account P&L is +$0.25 but strategy-captured closed P&L is +$13.78, with one unmatched close record (a $13.53 discrepancy). Do not use that window to validate per-position or tier attribution until the defect is explained and reconciled.
4. **Long-window runs hit the test harness operation cap.** Two research runs requested 2026-07-01 through 2026-10-16, but both stopped at 1,000 order operations and only reached mid-September. They are **incomplete and excluded from the evidence table**:
   - Causal: `77871903-b47e-4b13-8307-559775b089ed`, cut at 2026-09-16 12:30:00 UTC.
   - Strict threshold: `8598cc47-7234-4668-b380-f84287c154c0`, cut at 2026-09-15 18:11:36 UTC.
   Their partial P&L/drawdown must not be represented as full-period performance. CI/evidence automation should fail closed when this warning appears.
5. **This is not yet the MQL5 EA's profitability test.** StrategyTune's script engine, order semantics, available costs, and instrument feed differ from MT5/Exness. Native MetaEditor/Strategy Tester policy tests prove compilation and policy behavior, not market edge.

## LONA cross-checks already present

These are historical reports with different data frequencies and assumptions, so they are corroborating warnings rather than a matched comparison:

- The 1-day `Dual-Lane Asymmetric Runner Validator (Cadence-Safe Session Gate) v1.0.4 — Run #4` report used $10,000 initial cash and a 0.0005 commission setting, recorded 27 trades, -$8.56 P&L, 59.26% winning trades, profit factor 0.82, and expectancy -$0.32.
- A related report with **0 closed trades and 3 open trades** is not a realized-win result; its small positive marked value cannot validate expectancy.
- A regime-gated research report started with $344.69 and returned +$1.46 across just 3 closed trades at 100% wins. Three trades are far too few to establish the claimed hit rate or an edge.
- These LONA reports do not by themselves establish a complete Exness-specific spread/commission/slippage/swap model, and they are not equivalent to the production EA.

## Required experiment before promotion

1. Fix the July causal close-attribution mismatch and make untrusted attribution a hard rejection in the evaluation pipeline.
2. Make any backtest that hits `tradeActionLimit`, leaves unresolved/open trades, or emits incomplete-data warnings **ineligible** for promotion.
3. Run the exact packaged EA build in MT5 Strategy Tester using Exness symbol specs and real tick history, with spread, commission, slippage, and swaps represented; export per-parent-position realized P&L and reconcile each fill/partial close/stop modification.
4. Lock three chronological walk-forward folds and one untouched OOS period before examining those results. Use matched baseline/candidate runs with identical dates, symbols, risk, costs, and inputs; include confidence intervals, net expectancy, PF, equity drawdown, loss streaks, and symbol/session/regime stratification.
5. Forward-test the exact EA on Exness demo and reconcile broker history against the execution ledger before live consideration.

## Small-account risk is a constraint, not a bug

At KSh 1,500, 0.5% is KSh 7.50 planned stop risk. Keep the sizer fail-closed when the smallest broker-allowed trade exceeds this budget; do not force a minimum lot to meet a daily trade count. That account may be too small to validate XAUUSD live and should be used only for sizing diagnostics until broker-specific symbol/stop calculations prove otherwise. Risk limits and trailing-stop requirements must be validated as explicit profiles rather than silently relaxing the production hard ceiling.
