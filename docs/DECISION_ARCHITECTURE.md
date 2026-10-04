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

## Conservative calibration for elevated risk

The calibrated probability remains the empirical bucket win rate. In addition, Midas computes a 95% Wilson lower confidence bound for the same bucket. The lower bound is not substituted for the displayed probability; it is a conservative uncertainty measure used only when considering high-conviction risk.

This prevents a small bucket with an apparently excellent observed win rate from automatically qualifying for elevated sizing. Standard risk continues to use the empirical probability only when its existing positive-expected-R and environment requirements are satisfied.

## Regime stability research gate

The raw regime classifier can move between TRENDING, RANGING, and TRANSITION as its component reads change. An optional stability gate now requires the same actionable regime to appear on consecutive completed decision bars before peer-strategy routing can use it. Until confirmation, routing is conservatively treated as REGIME_TRANSITION; REGIME_UNDEFINED also fails closed.

InpRequireRegimeStability defaults OFF. The gate is a research candidate, not a claimed edge: promotion requires locked OOS evidence that reduced regime churn improves loss containment/expectancy without destructive trade-count collapse, followed by MetaEditor plus MT5 Strategy Tester parity.

## Target ladder research gate

Midas assigns a target ladder from resting liquidity and higher-timeframe levels:

- TP1: nearest eligible internal liquidity;
- TP2: next eligible external liquidity beyond TP1;
- TP3/final: a valid weekly liquidity level when available, otherwise a deterministic ATR fallback.

A feature-gated target-management path can realize a partial at TP1, a second partial at TP2, and leave the final target on the runner. `InpEnableTargetLadder` defaults OFF until locked OOS testing demonstrates better loss containment and/or expectancy without unacceptable payoff or trade-count degradation.

## Sweep follow-through displacement hardening

The SMC chain distinguishes the initial impulse from the displacement that should follow an internal liquidity sweep.

The production detector now exposes separate thresholds for these two events:

- `InpImpulseATRMult` / `InpImpulseBodyRatio` govern the initial impulse;
- `InpSweepFollowThroughATRMult` / `InpSweepFollowThroughBodyRatio` govern the post-sweep follow-through bar.

The v2.16 controls default to the existing `1.2 ATR` and `0.60 body-ratio` values, so adding the separation does not change production behavior by itself.

This separation exists for controlled ablation. A post-sweep micro-displacement can be materially smaller than the initial impulse; however, relaxing the thresholds is a behavior change and must not be promoted from a single backtest. Promotion requires multi-period locked OOS evidence, adequate trade-count retention, outcome attribution, and MetaEditor/MT5 Strategy Tester parity.

## Strict structural-validity research gate

The production validator can distinguish a complete SMC chain from a chain that is structurally complete but degraded in quality. The optional InpRequireSMCStructuralValidity gate treats STRUCTURE_DEGRADED as a hard structural rejection, so later score, environment, or calibration evidence cannot rescue it.

This gate defaults **OFF** on the research branch. Promotion requires a baseline-versus-candidate comparison showing acceptable trade-count retention and improvement in loss containment and/or expectancy across locked unseen periods, followed by MetaEditor and MT5 Strategy Tester parity validation.

## Empirical gates intentionally OFF by default

The following remain feature-gated because architecture correctness is not proof of trading edge:

- strict SMC structural-validity hard gate (InpRequireSMCStructuralValidity);
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
