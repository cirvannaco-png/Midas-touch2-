# Midas Touch — Edge Control Architecture

## Objective

Improve trading edge without adding indicator noise. The system should maximize **robust net expected R after execution costs**, subject to portfolio, drawdown and uncertainty constraints.

## Existing authoritative market-state layer

`CRegimeDetector` already combines:

- BOS-backed trend structure
- ATR-percentile volatility
- market phase / compression / sweep-displacement context

and classifies the state as `TRENDING`, `RANGING`, `TRANSITION`, or `UNDEFINED`.

The correct next step is not another regime classifier. It is to make this state authoritative for strategy eligibility and eventually strategy ownership.

## Current edge controls pushed in this revision

1. `UNDEFINED` regime is explicit abstention.
2. Momentum/breakout challengers cannot win after `BREAKOUT_FAILED` or `BREAKOUT_EXHAUSTION`.
3. Mean reversion cannot challenge while `REVERSION_TREND_CONFLICT` is active.
4. Key-level strategy ownership requires an actual reaction (`REJECTION`, `RETEST`, `FAILED_BREAK`, or `ABSORPTION`), not merely a raw break/acceptance.
5. Heterogeneous strategy scores are never summed.
6. The SMC setup cannot silently impersonate a selected challenger; the existing setup boundary remains fail-closed.

## Next edge layer: conditional expectancy

Resolved observations already retain regime, strategy, score, probability, expected return and execution-cost information. The target statistic is:

`E[R_net | regime, strategy, setup_context]`

where `R_net` includes realized outcome less measured execution costs.

Capital should only be increased when the relevant population has sufficient sample size and statistical reliability. Unknown evidence remains baseline/abstention rather than being treated as positive edge.

## Candidate ranking

The intended decision order is:

`market state -> eligible strategies -> candidate setup -> calibrated probability -> expected net R -> portfolio admission -> execution`

Probability and expected return remain separate. A high win probability is not sufficient if payoff or execution cost makes expected R negative.

## Abstention

Midas should explicitly allow `NO TRADE` when:

- regime is undefined
- setup evidence is contradictory
- expected net R does not clear the cost and uncertainty buffer
- sample size is insufficient for a learned conditional edge
- execution conditions invalidate the expected edge
- portfolio admission is unavailable

## Validation before enabling learned allocation

No learned threshold or strategy weight should be promoted merely because it improves an in-sample backtest. Required evidence:

1. temporal train/test separation
2. walk-forward validation
3. regime × strategy sample sufficiency
4. transaction-cost and slippage stress
5. parameter perturbation / sensitivity testing
6. controlled demo forward test
7. production telemetry and rollback path

CI is intentionally paused during this development pass. A paused pipeline is **not** evidence of passing validation; restore CI before production promotion.
