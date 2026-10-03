# Midas Touch — Hierarchical Decision Architecture

## Purpose

Midas Touch separates **signal evidence** from **trade admission**.

Raw confidence remains a diagnostic/ranking value. It is not authoritative proof that a trade exists.

The authoritative path is:

```
MARKET DATA
  ↓
MARKET REGIME
  ↓
LIQUIDITY + STRUCTURE
  ↓
STRUCTURAL VALIDATOR
  ↓
ENTRY QUALITY
  ↓
ENVIRONMENT MEMORY
  ↓
TRADE / WAIT / REJECT
  ↓
EXECUTION POLICY
  ↓
RISK ENGINE
  ↓
TRADE MANAGEMENT
  ↓
OUTCOME ATTRIBUTION
  ↓
CALIBRATION / RECALIBRATION
```

## Structural state machine

The production SMC chain is represented as an ordered lifecycle:

```
NO_STRUCTURE
  ↓
LIQUIDITY_IDENTIFIED
  ↓
LIQUIDITY_SWEPT
  ↓
VALID_DISPLACEMENT
  ↓
CONFIRMING_BOS
  ↓
CAUSAL_FVG
  ↓
LOCATION_VALID
  ↓
FRESHNESS_VALID
  ↓
INVALIDATION_DEFINED
  ↓
STRUCTURALLY_VALID
```

Any hard invalidation terminates the setup for trading.

## Decision states

Every generated setup has one of:

- `DECISION_REJECT`
- `DECISION_WAIT`
- `DECISION_TRADE`

The execution router accepts only `DECISION_TRADE`.

A setup in `WAIT` may be retained for telemetry and later lifecycle transitions, but it is never sent to the broker.

## Setup lifecycle

The setup lifecycle is:

```
DETECTED
  ↓
ARMED
  ↓
WAITING_RETEST
  ↓
RETEST_CONFIRMED
  ↓
ENTRY_ELIGIBLE
  ↓
execution
```

Unfilled or invalid setups transition to `EXPIRED`.

A tested FVG is treated as evidence that a zone retest occurred; a chase/spread failure produces `WAITING_RETEST`.

## Evidence families

The trade-quality firewall groups correlated evidence into families:

- Structure
- Liquidity
- Location
- Execution
- Environment

This prevents a single causal market event from being counted as many independent additive confirmations.

The family-capped quality score is separate from raw confidence.

## Risk architecture

Structural invalidation is immutable.

Dynamic protection may:

- tighten the stop;
- move to breakeven;
- trail;
- partially protect;

but it must not widen structural risk.

Portfolio controls include:

- portfolio open-risk cap;
- per-symbol position limits;
- correlation-group limits;
- optional rolling H1 return-correlation exposure guard.

## Calibration

Calibration data is persisted under a versioned schema filename so a strategy/model revision does not silently mix with stale calibration observations.

The evidence-gated calibration decision is intentionally optional until sufficient locked-OOS and MT5 evidence exists.

## Strict structural-validity research gate

The production validator can distinguish a complete SMC chain from a chain that is structurally complete but degraded in quality. The optional InpRequireSMCStructuralValidity gate treats STRUCTURE_DEGRADED as a hard structural rejection, so later score, environment, or calibration evidence cannot rescue it.

This gate defaults **OFF** on the research branch. Promotion requires a baseline-versus-candidate comparison showing acceptable trade-count retention and improvement in loss containment and/or expectancy across locked unseen periods, followed by MetaEditor and MT5 Strategy Tester parity validation.

## Empirical gates intentionally OFF by default

The following remain feature-gated because architecture correctness is not proof of trading edge:

- environment hard block;
- causal-FVG hard requirement;
- single-swing inducement fallback;
- portfolio rolling-correlation hard guard;
- calibrated-probability admission gate.

These can be promoted only after:

1. production/research parity;
2. multi-period locked OOS evaluation;
3. trade-count stability;
4. no-look-ahead verification;
5. MT5 Strategy Tester parity;
6. documented ablation evidence.

## Compilation boundary

GitHub CI can validate:

- include resolution;
- duplicate definitions;
- interface arity;
- architectural invariants;
- Python/research tests.

MetaEditor remains the authoritative MQL5 compiler.

Therefore a green CI result means **structurally validated**, not “MetaEditor compiled” unless a real MetaEditor build has been run and recorded.

## Production promotion rule

No architecture change is considered a proven trading improvement merely because it raises a backtest metric on one period.

Promotion requires stable evidence across unseen periods and live-engine parity.


## Closed-bar structural integrity

Production inducement detection ignores the forming bar for sweep, BOS, displacement follow-through, and impulse extension decisions. Cross-timeframe FVG causality is evaluated from event timestamps and the actual FVG timeframe rather than comparing raw bar indices from different series.

## First-class abstention

A missing strategy, invalid structural chain, failed execution condition, degraded environment, or failed risk geometry produces an explicit DECISION_REJECT or DECISION_WAIT setup with a blocking layer and reason. These states are persisted to the signal CSV instead of disappearing as inactive candidates.

## Evidence-family caps

Family scores are hard-capped at:

- Structure: 30
- Liquidity: 25
- Location: 20
- Execution: 15
- Environment: 10

Structure no longer imports environment evidence. This prevents cross-family leakage and reduces correlated double-counting.

## Risk promotion

All admitted setups begin at minimal risk class. Standard/high-conviction sizing requires calibrated outcome evidence and positive expected R; elevated classes also require environment-memory evidence, with high conviction requiring a QUALIFIED environment state. Raw confidence cannot promote risk class.

## Lifecycle

The lifecycle now includes DETECTED -> ARMED -> WAITING_RETEST -> RETEST_CONFIRMED -> ENTRY_ELIGIBLE -> FILLED -> MANAGED -> CLOSED.

EXPIRED is used for rejected, stale, invalidated, or otherwise abandoned setups. Partial exits move a filled setup to MANAGED; only finalization moves it to CLOSED.

## Attribution

Signal and outcome logs retain decision state, blocking layer, decision reason, quality score, structural state/stage, lifecycle, expected return, and regime identity. Provenance also includes liquidity archetype, sweep measurements, displacement, BOS age/distance, FVG causality, and invalidation distance.
