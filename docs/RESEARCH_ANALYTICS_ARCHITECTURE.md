# Midas-Touch Research Analytics Architecture

## Purpose

This layer extends the existing Midas-Touch research stack with feature importance,
clustered MDA, paired counterfactual replay analysis, scale-out value analysis,
and a fail-closed research validation gate.

It is deliberately outside the live EA decision path.

## Authority boundary

The live system remains authoritative for:

- market structure and inducement
- confidence/scoring
- strategy selection
- calibration
- decision admission
- risk sizing
- portfolio admission
- MultiTrade/Dual Trade
- execution and reconciliation

The research layer may measure those outputs, compare controlled variants, and
produce evidence. It must not silently write learned weights, thresholds, exits,
or routing decisions back into the EA.

## Feature importance

tools/research/feature_importance.py implements repeated held-sample permutation
importance. A feature is considered useful only when permuting it degrades the
caller-supplied metric.

The result is diagnostic evidence, not a live scoring weight.

For Midas-Touch, candidate features can include market-structure, liquidity,
trend, session, volatility, FVG, HTF order-block, value-area, volume, and other
telemetry fields. Feature importance must be evaluated on a held sample.

## Clustered MDA

tools/research/clustered_mda.py groups highly correlated features by absolute
Pearson correlation and permutes each group jointly.

This directly addresses the evidence-duplication class of problem already found in
the live scoring audit: two differently named fields can still represent one
underlying market fact. Clustered MDA asks how much predictive information the
whole evidence family contributes after the family's members are treated as one.

Correlation clusters should be learned from training data and reused against
validation/OOS data to avoid leakage.

## Counterfactual analysis

tools/research/counterfactual.py accepts only paired scenario variants. Every
scenario used in the comparison must have exactly one baseline and one candidate
variant with realized R.

This is intentionally stricter than slicing historical trades by a flag. A
historical subset is attribution; a same-scenario replay with alternate logic is
counterfactual evidence.

## Scale-out value analysis

tools/research/scale_out_value.py compares explicitly tagged exit-policy replay
variants, including full-exit and scale-out policies.

The analyzer reports:

- expectancy and median R
- win rate and profit factor
- max drawdown
- MFE capture
- MAE
- average holding time
- transaction-cost telemetry
- paired expectancy delta
- paired outperformance fraction

It refuses to synthesize a scale-out result from final R or MFE alone.

## Walk-forward and locked OOS

The repository already provides leakage-resistant rolling walk-forward windows,
locked-OOS provenance validation, and promotion evidence gates.

The new research validation gate consumes those existing results. A research
candidate must have sufficient locked-OOS trades and consistent walk-forward
folds before entering promotion review.

Minimum default evidence:

- 30 locked-OOS trades
- 3 consistent walk-forward folds
- feature-importance evidence
- clustered-MDA evidence
- paired counterfactual evidence
- scale-out replay evidence when the change affects exits

A divergent walk-forward result fails closed. Missing evidence is not interpreted
as a pass.

## Promotion boundary

The sequence is:

TRAIN
-> VALIDATION
-> LOCKED OOS
-> FEATURE IMPORTANCE
-> CLUSTERED MDA
-> COUNTERFACTUAL REPLAY
-> SCALE-OUT REPLAY when exit logic changes
-> PROMOTION REVIEW

No single metric, feature importance rank, optimizer result, or favorable in-sample
backtest can promote a change by itself.

## Interaction with the existing live architecture

The new files under tools/research/ are research infrastructure. They do not
replace EA/includes/Analysis/Scoring.mqh, StrategySelector, StrategyTradeZone,
RiskEngine, PortfolioManager, MultiTradeEngine, or execution code.

This separation prevents research experimentation from becoming accidental live
behavior and preserves the existing Midas-Touch architecture's fail-closed
decision boundaries.
