# Gold Trend-Only Research Candidate — Holdout Review

**Status:** Research only; not approved for production  
**StrategyTune script:** `Midas Gold Trend-Only Research Candidate v1`  
**StrategyTune script ID:** `h345lkflaiy1h993tqu2wjjr`  
**Current compiled script version:** 6  
**Research branch:** `research/midas-gold-trend-only-v1`

## Test specification

- Instrument: Gold (IC Markets data provider)
- Interval: M15
- Historical window: 2025-01-01 through 2025-06-01
- Starting balance: USD 1,500
- Strategy: trend-only continuation
- Execution: StrategyTune bid/ask historical simulation
- Important limitation: StrategyTune's strategy execution model does not provide a separate commission or slippage model. These results must not be interpreted as fully cost-adjusted live performance.

## Position-level reconciliation

All performance figures below are grouped by the original `openingFillId`. Partial exit rows are not counted as independent winning trades.

### Both directions enabled — version 4 telemetry

| Measure | Result |
|---|---:|
| Independent opening positions | 249 |
| Closed execution rows | 475 |
| Position wins / losses | 195 / 54 |
| Position win rate | 78.31% |
| Gross profit | USD 58.59 |
| Gross loss | USD 60.39 |
| Profit factor | 0.97 |
| Net P&L | USD -1.80 |

This configuration failed the profitability test. The short side materially reduced results.

### Long-only ablation — version 5 telemetry

| Measure | Result |
|---|---:|
| Independent opening positions | 174 |
| Closed execution rows | 340 |
| Position wins / losses | 140 / 34 |
| Position win rate | 80.46% |
| Gross profit | USD 44.33 |
| Gross loss | USD 37.44 |
| Profit factor | 1.18 |
| Net P&L | USD +6.89 |
| Maximum drawdown (engine report) | USD 10.86 |

Long-only is a promising research hypothesis, not a validated production rule. It has only one historical holdout window and remains exposed to selection bias from the earlier experiments. It must be retested on a separate, untouched period before acceptance.

## Telemetry hardening

The research candidate now:

- Uses the feed's `priceDigits` for entry-price, stop-distance, and price-key serialization instead of hard-coded two/five decimal rounding.
- Uses a compact versioned 12-field entry lineage record with Unix UTC seconds.
- Joins entry lineage to saved session outcomes by the exact opening-lot ID / `openingFillId` key.
- Counts malformed records, duplicate lot IDs, precision mismatches, exported records, and truncated records.
- Explicitly marks the latest-close snapshot observer as non-authoritative; it cannot reconstruct multiple close events on one update.

The first combined-direction run exposed a real export-capacity defect: 249 entry records required 125 chunks, while the old 80-chunk cap exported only 160 records and truncated 89. The compact schema in version 5 reduced the long-only run to 44 chunks and exported all 174 entry records with no overflow.

The version 5 integrity check reported all 174 records as malformed because its digit-validation regular expression was over-escaped. The regex was corrected in version 6 and the script compiled successfully. **Version 6 has not yet been rerun**, so a clean integrity pass is still required.

## Acceptance gates before any production transfer

1. Rerun version 6 on this exact window and confirm `entryMapIntegrityValid=true`, zero malformed/duplicate/precision errors, and zero truncated records.
2. Freeze parameters and test long-only on a new untouched Gold period.
3. Compare both-direction, long-only, and short-only ablations on identical data and costs.
4. Add realistic commission and slippage assumptions, then stress spread and execution delay.
5. Require positive out-of-sample expectancy and profit factor after costs, acceptable drawdown, and stability across multiple regimes.
6. Port nothing into the production MQL5 EA until the native MetaTrader Strategy Tester reproduces the candidate behavior and all repository CI checks pass.

No production EA source, live configuration, or deployment was changed by this research work.
