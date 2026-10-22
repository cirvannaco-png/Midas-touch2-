# SMC Structural Chain Experiment Protocol

## Objective

Reduce false-positive SMC entries and improve average realized R by identifying which
parts of the causal chain carry independent information:

liquidity -> sweep -> displacement -> BOS -> causal FVG -> premium/discount -> freshness -> invalidation

This protocol is research-only. It does not authorize a live trading-rule change.

## Authoritative population

Use the production-parity accepted setup population on the entry timeframe.

Primary analysis population:

1. valid inducement sequence;
2. weak BOS;
3. premium/discount failure;
4. an otherwise eligible production FVG candidate;
5. resolved outcome with unambiguous realized R.

Do not redefine these conditions inside the research notebook.

## Structural splits

Run each split independently and then in controlled combinations.

### Sweep / liquidity

- inducement structure type
- sweep grade: A / B / C
- immediate sweep-follow-through displacement: yes / no
- penetration ATR:
  - <= 0.10
  - 0.10-0.30
  - 0.30-0.60
  - > 0.60
- rejection ratio:
  - < 0.50
  - 0.50-0.75
  - >= 0.75

### BOS

- BOS strength:
  - < 0.33
  - 0.33-0.66
  - >= 0.66
- bars since BOS:
  - 1
  - 2-3
  - 4-5
  - >5

### FVG

Only use the winning FVG selected by production scoring.

- state: fresh / tested
- age:
  - 0-1 bars
  - 2-3 bars
  - >3 bars
- distance from current price in ATR:
  - <= 0.50
  - 0.50-1.00
  - 1.00-1.25

Mitigated and invalidated zones are not eligible production FVG candidates and must not
be reintroduced as positive samples.

## Outcome metrics

For every slice and combination report:

- trade count
- win rate
- profit factor
- expectancy per trade
- average R
- median R
- sum R
- max drawdown
- largest losing streak
- average MFE
- average MAE
- average holding time

Always show the trade count beside the performance metric.

## Time split

Evaluate separately on:

- 2023
- 2024
- 2025
- 2026 OOS

Never pool all years first and then call the result robust.

## Robustness requirements

A candidate filter is research-eligible only when:

- locked-OOS expectancy is positive;
- profit factor is >= 1.0;
- no required metric is missing/non-finite;
- OOS degradation from validation is <= 35%;
- at least one nearby parameter configuration within 10% of the primary OOS expectancy remains viable;
- the effect is not explained only by an extreme collapse in trade count;
- walk-forward folds remain directionally consistent.

Feature importance, clustered MDA, and paired counterfactual evidence are required before
promotion review, consistent with docs/RESEARCH_ANALYTICS_ARCHITECTURE.md.

## Promotion rule

Do not modify production scoring or gates because a single slice is attractive.

Promotion requires all of:

TRAIN -> VALIDATION -> LOCKED OOS -> feature importance -> clustered MDA ->
paired counterfactual replay -> walk-forward consistency -> MT5 parity.

If any required evidence is unavailable, the candidate remains research-only.

## Current compute boundary

StrategyTune is currently at its daily free-plan compute cap. No new profitability result
is implied by this protocol or by the telemetry branch until a fresh backtest actually runs.
