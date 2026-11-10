# Gold payoff ablation — 2026-11-10

## Status

**Research-only. No EA source, live configuration, risk limits, or production behavior changed. No candidate is approved for promotion.**

This note records a controlled StrategyTune experiment on the saved Midas v2.9 Gold continuation-only research strategy. It is a platform proxy experiment, not an MT5 Strategy Tester result and not broker-forward evidence.

## Question

The existing continuation-only proxy showed a high count of winning closed trade records but negative net P&L. The hypothesis was that changing the first partial-profit trigger (TP1) could improve payoff without changing the entry logic.

The test varied only `continuationTP1RR`; all other saved strategy inputs remained at the compiled script defaults.

## Reproducibility

- Strategy: `MT2 v2.9 Gold Continuation-Only Ablation`
- StrategyTune script ID: `gbwv2tlv3tn17yw10ypcc8nz`
- Compiled version: 1
- Instrument: Gold
- Timeframe: 15 minutes
- Account currency: USD
- Starting balance: USD 10,000
- Baseline TP1: 0.25R
- Candidate TP1 values: 0.15R, 0.20R, 0.50R, 0.75R
- Research runs were not saved as user sessions (`save_session=false`).

Date windows:
- September 2026: 2026-09-01 00:00 UTC to 2026-09-30 23:59:59 UTC
- October 2026: 2026-10-01 00:00 UTC to 2026-10-31 23:59:59 UTC
- November partial window: 2026-11-01 00:00 UTC to 2026-11-06 23:59:59 UTC

## Results

All counts below are **closed trade records**, not unique entry decisions or independent positions. Partial closes can create multiple records for one opening fill. They must not be presented as the system's signal win rate.

| TP1 | Period | Net P&L (USD) | Closed records | Wins | Losses | Max drawdown (USD) | Attribution |
|---:|---|---:|---:|---:|---:|---:|---|
| 0.25R baseline | Sep | -38.96 | 168 | 149 | 19 | 99.37 | Invalid; 2 unmatched close records and P&L reconciliation delta -15.52 |
| 0.25R baseline | Oct | -9.05 | 130 | 114 | 16 | 67.09 | Invalid; 2 unmatched close records and P&L reconciliation delta -4.17 |
| 0.25R baseline | Nov 1–6 | -5.66 | 9 | 7 | 2 | 18.93 | Valid |
| 0.15R | Sep | -59.56 | 165 | 152 | 13 | 93.64 | Invalid; 1 unmatched close record and P&L reconciliation delta -15.25 |
| 0.15R | Oct | +5.17 | 131 | 121 | 10 | 33.82 | Valid; zero unmatched close records and P&L reconciliation delta approximately zero |
| 0.15R | Nov 1–6 | +3.71 | 10 | 9 | 1 | 8.48 | Valid, but only 5 opening entries in a partial week |
| 0.20R | Oct | +5.04 | 131 | 118 | 13 | 50.23 | Invalid; 2 unmatched close records and P&L reconciliation delta -7.70 |
| 0.50R | Oct | -34.06 | 120 | 95 | 25 | 82.10 | Invalid; 2 unmatched close records and P&L reconciliation delta +0.17 |
| 0.75R | Oct | -75.22 | 117 | 84 | 33 | 116.59 | Invalid; 2 unmatched close records and P&L reconciliation delta +3.86 |

### Run identifiers

| TP1 | Period | StrategyTune run ID |
|---:|---|---|
| 0.25R | Sep baseline | `f5790a8f-88c8-4d00-a6a8-bd651448ae87` |
| 0.25R | Oct baseline | `57fda98f-4d46-4528-b15c-e137fae8e485` |
| 0.25R | Nov 1–6 baseline | `7d40ee1c-4d6e-4111-9492-6cca9de223e7` |
| 0.15R | Sep | `d0d24032-a225-4b91-bc06-19042c0e0f34` |
| 0.15R | Oct | `b1d1280e-7be1-4170-ab0d-3761858696d0` |
| 0.15R | Nov 1–6 | `d4b3537d-d5ef-4112-ac04-7f786c676786` |
| 0.20R | Oct | `c0dd147b-e504-4801-9e33-3c76d93d56a1` |
| 0.50R | Oct | `d5c1b3c6-404e-4ea0-8a4d-324501627d95` |
| 0.75R | Oct | `8874f325-5366-4b1b-9a05-32dec148af7f` |

## Interpretation

1. The 0.15R TP1 candidate is promising only in the October proxy window and the very small November partial window. It loses materially in September. This is not robust across regimes or time.
2. Moving TP1 later to 0.50R and 0.75R materially worsened October results and drawdown in this proxy.
3. The 0.20R October result is not admissible as evidence because position attribution failed.
4. The baseline continuation-only strategy was negative in all three inspected periods: September, October, and November 1–6.
5. A high closed-record win count is not equivalent to a high entry-level win rate. The strategy can generate several partial-close records from one opening fill.
6. StrategyTune's current simulation does not model broker commission or an independent slippage charge. Recorded bid/ask spreads are present, but the results are not fully cost-inclusive.
7. Several variants fail their own position-attribution reconciliation. Those results are diagnostic only and must not be used to rank or promote strategies.

## Decision

**Do not promote 0.15R, 0.20R, 0.50R, or 0.75R. Keep the EA and its live exit settings unchanged.**

The test does not establish a positive, stable, net-of-cost trading edge. It only narrows the next research question: entry quality and adverse excursion need to be measured at the unique-decision / unique-opening-fill level, with exact position attribution, before more exit tuning is justified.

## Next research priorities

1. Use the repository's fail-closed MT5 evidence pipeline to establish exact `SignalID → decision_id → opening fill → all closing deals` attribution, including every partial close and open remainder.
2. Compare baseline versus candidate on identical real-tick MT5 Strategy Tester data, preserving source/build hash, .set files, deal history, point-value specification, and data hash.
3. Attribute MAE/MFE and time-to-adverse-excursion by strategy family, sweep grade, BOS strength, entry chase distance, session, and market regime.
4. Test one entry-quality hypothesis at a time. Avoid adding another global gate unless it shows incremental value over the existing structural evidence.
5. Include commission, swaps, fees, measured or conservative slippage, gap/overshoot stress, chronological walk-forward folds, and a genuinely untouched locked OOS period.
6. Reject any run with unmatched close records, position-attribution mismatch, missing costs, or incomplete data.

## Evidence boundary

StrategyTune is useful for controlled exploratory ablations, but its runs are not substitutes for the MQL5 EA's actual MT5 Strategy Tester execution model or the selected broker's accounting. A profitable proxy window is not a profitability claim. This document changes no trading behavior.


## Supplementary Gold regime-specialist review — 2026-11-10

A review of the existing StrategyTune v2.12 Gold Regime-Specialist Hybrid runs adds an important warning. These are existing 15-minute StrategyTune records, not new MT5 tests. All amounts are USD on a USD 10,000 starting balance.

| Period | Net P&L | Closed records | Wins / losses | Max drawdown | Attribution |
|---|---:|---:|---:|---:|---|
| 2025 Q1 | -34.66 | 379 | 330 / 49 | 106.76 | Invalid; 2 unmatched close records, 3 missed close events, P&L delta -7.86 |
| 2025 Q2 | -28.96 | 384 | 338 / 46 | 96.85 | Invalid; 1 unmatched close record, 6 missed close events, P&L delta +25.56 |
| 2025 Q3 | -167.98 | 349 | 294 / 55 | 242.37 | Invalid; 2 unmatched close records, 3 missed close events, P&L delta -6.97 |
| 2025 Q4 | +13.16 | 388 | 347 / 41 | 95.07 | Invalid; 1 unmatched close record, 1 missed close event, P&L delta -0.61 |

Run IDs:
- Q1: `26854da3-8577-4554-8cf4-8c8ab060c773`
- Q2: `16ca6c1a-d048-487c-b49e-f6f35a11857d`
- Q3: `589025ed-426e-4720-b37e-077115c87866`
- Q4: `fe60cb0f-7b33-4f08-ba42-0273c3bad26c`

The 2025 full-year run (`54defed6-8f19-4cd8-86ae-29739ef976f4`) reported -68.98 USD but stopped at the 1,000 order-operation limit on 2025-04-28. It is explicitly incomplete and must not be represented as a full-year result. Each quarterly report also truncated six custom-stat keys because the strategy exceeded the platform's custom-stat limit. The position-attribution checks above are available in the returned fields; missing custom fields must not be inferred as zero.

The Q3 loss is materially worse than the other quarters. Q4's small positive result does not rescue the candidate: every quarterly window failed position attribution, and the full-year run was cut short. Closed-record win counts are not unique-entry win rates.

### Cross-engine LONA check and execution limits

The saved LONA 1.0.5 regime-gated validator has historical XAUUSD daily reports, but they are not a valid independent confirmation of the 15-minute StrategyTune runs. The regime-enabled daily report recorded zero trades; the earlier regime-disabled report recorded only three trades. Both reports have null date bounds and the simulation's initial cash was approximately USD 345, not USD 10,000. They are too small and too poorly matched to compare meaningfully.

A fresh LONA intraday XAUUSD run was refused because global intraday data is unavailable on the current Free plan. A fresh daily run was also refused for insufficient credits. StrategyTune's attempted fresh comparison was likewise blocked by insufficient credits after resolving the instrument correctly as `Gold` from IC Markets (not `XAUUSD`). No fresh cross-engine comparison is claimed here.

### Decision

Do not promote v2.12 or its regime logic. The available evidence is negative or inadmissible: three losing quarters, one small positive but attribution-invalid quarter, and an incomplete full-year run. The next valid experiment requires a matched baseline/challenger run with attribution repaired, fewer exported custom statistics, and enough compute to finish every planned fold. Until then, preserve the EA and risk configuration unchanged.
