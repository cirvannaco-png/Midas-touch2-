# Prediction, Regime, Allocation and Recovery Governance

## 1. Three-number prediction contract

A Midas prediction contains three different quantities and they must never be
serialized under a single `confidence`/`percent` field:

- `model_score`: raw model output in `[0,1]`.
- `calibrated_probability`: empirical probability learned from resolved,
  appropriately separated outcomes; it is **not** `model_score * 100`.
- `expected_return`: empirical expected R after the configured payoff/cost
  distribution is applied.

A score such as `0.92` therefore remains `0.92`; it may calibrate to `0.73`
and have an expected return such as `0.31R`. Illustrative calibration numbers
are never shipped as constants.

Calibration is versioned. Every prediction carries `model_version`,
`calibration_version`, `regime_version`, and `portfolio_version`.

## 2. Evidence states

`UNKNOWN`, `UNDERPERFORMING`, and `PROVEN` are separate states.

- `UNKNOWN`: minimum sample has not been reached. Use the conservative
  baseline allocation. This is not evidence of a negative edge.
- `UNDERPERFORMING`: sufficient observations exist, but the statistical
  reliability/expectancy gate fails. Use the conservative baseline.
- `PROVEN`: sample sufficiency and statistical reliability pass. A validated
  allocation may be used, subject to portfolio caps.

No unseen regime/strategy bucket is silently assigned zero allocation merely
because evidence is absent.

## 3. Regime authority

Regime is classified only from observable inputs:

- volatility state
- trend state
- liquidity state
- spread/execution state
- news state
- shock indicator
- correlation/exposure state

The classification is deterministic:

`SHOCK` takes precedence when objective shock/news/execution thresholds are
met; otherwise a clean observable environment is `NORMAL`; all remaining
cases are `TRANSITION`.

The exact `RegimeSnapshot` is persisted with the prediction, including the
regime definition version.

## 4. Allocation authority

The intended authoritative sequence is:

```text
Detect regime
    -> identify regime + strategy bucket
    -> check minimum sample
    -> statistical reliability gate
       NO  -> conservative baseline
       YES -> empirically validated allocation
```

Strategy-specific scoring must not independently decide exposure and then
be overridden by Portfolio. Strategy modules provide evidence; Regime
classifies the environment; Portfolio is the capital-allocation authority.

## 5. Regime/strategy empirical dataset

Resolved observations retain:

`regime, strategy, model_score, calibrated_probability, expected_return,
outcome_R, win/loss, MFE, MAE, holding_time, costs`

This preserves attribution so performance from one strategy or regime cannot
contaminate another bucket.

## 6. Fault-injection recovery contract

Recovery is judged against broker truth, not merely against whether a recovery
function ran. The recovery invariant is:

```text
inject failure -> restart/reconcile -> broker truth -> deterministic state
```

The required test matrix is:

| Boundary/failure | Required assertion |
|---|---|
| decision created crash | no phantom execution; durable decision is recoverable |
| decision persisted crash | exactly one decision after restart |
| order submitted crash | broker order/position becomes source of truth |
| broker accepted crash | no duplicate submission |
| position filled crash | fill and volume reconstructed from broker |
| SL modified crash | broker SL wins over stale local SL |
| partial close crash | remaining volume reconciles exactly |
| position closed crash | terminal broker state is restored and outcome is persisted once |
| terminal restart | same state after reconciliation |
| EA restart | same state after reconciliation |
| network interruption | retry/reconcile is idempotent |
| backend unavailable | execution state remains broker-authoritative |
| duplicate execution request | one broker exposure only |
| delayed broker response | no blind duplicate submission |
| rejected order | rejected state, no invented position |
| rejected SL modification | actual broker SL retained; protection is not assumed |
| partial fill | actual filled volume reconciled |
| partial close interruption | actual remaining position reconciled |
| stale configuration | configuration/version mismatch blocks unsafe continuation |
| configuration mismatch | exact version fingerprint is retained and mismatch is explicit |
| missing local state | reconstruct from broker truth |
| corrupted local state | discard/repair from broker truth |
| broker position without local record | create a reconciliation-required record from broker truth |
| local record without broker position | mark reconciliation required; never invent a live position |

The recovery operation is idempotent: reconciling an already reconciled state
against the same broker snapshot must produce the identical state.

## 7. Production promotion rule

These governance primitives are a contract, not permission to deploy an
untested strategy. Promotion still requires compile validation, historical
backtest, out-of-sample/forward validation, EA/backend parity, and broker
fault-injection evidence.
