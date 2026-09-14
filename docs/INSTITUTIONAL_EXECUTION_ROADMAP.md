# Institutional Execution Roadmap

## Objective

Evolve Midas Touch 2 from `decision -> broker -> execution` into a broker-neutral systematic execution stack while preserving the existing EA/backend separation, fail-closed controls, governance, and backtest/forward-test contracts.

## Target lifecycle

`Alpha -> Portfolio -> Pre-Trade Risk -> OMS -> Execution Policy -> Smart Order Router -> Venue Adapter -> Fills -> Reconciliation -> TCA -> Surveillance -> Outcome/Calibration -> Governance`

## Implemented foundation on the institutional-execution branch

- Canonical broker-neutral execution models and order states.
- Explicit `UNKNOWN` and `RECOVERY_REQUIRED` states.
- Idempotent OMS contract.
- Venue quote and health model.
- Smart order routing score based on liquidity coverage, fill reliability, spread/slippage and latency.
- Market/adaptive execution-policy selection.
- Fail-closed pre-trade gate for exposure, loss, spread, venue health and configuration authorization.
- Signed TCA/implementation-shortfall calculation.
- Broker/OMS reconciliation contract that freezes when state is unavailable or ambiguous.
- Deterministic execution surveillance for venue, rejection, slippage, latency and duplicate-order anomalies.

## Next parallel workstreams

### Execution connectivity

1. `IExecutionVenue` adapter contract.
2. MT5 venue adapter around `BrokerAdapter.mqh`.
3. Simulator venue for backtest/execution-cost parity.
4. FIX gateway boundary in the backend; FIX must not be embedded in the EA.
5. Multi-broker venue registry and health reporting.

### Execution algorithms

1. Market.
2. Passive/limit.
3. TWAP child-order scheduler.
4. VWAP volume-profile scheduler.
5. POV participation scheduler.
6. Adaptive policy using urgency, spread, volatility, liquidity and fill probability.

All algorithms must be deterministic under simulation and must not introduce future-data access.

### TCA

Track decision price, arrival price, broker acknowledgement, first fill, final fill, average fill, spread, slippage, market impact, implementation shortfall and opportunity cost.

Break down results by symbol, venue, strategy, regime, session, volatility and execution policy.

### Reconciliation

Continuously reconcile backend OMS, EA state, broker orders, positions and fills. Any ambiguous state freezes new exposure until reconciliation completes.

### Surveillance

Monitor p50/p95/p99 latency, rejection rate, slippage, partial-fill rate, duplicate submissions, venue health and unexpected exposure. Critical anomalies must fail closed.

### Research and validation

Execution-aware backtesting must model spread, commission, slippage, latency, partial fills and policy-specific execution costs. Promotion gates must use out-of-sample/walk-forward evidence rather than in-sample P&L alone.

## Non-negotiable invariants

- No duplicate exposure after timeout or ambiguous acknowledgement.
- No retry of unknown/permanent broker outcomes.
- No routing to an unhealthy venue.
- No new exposure when pre-trade risk fails.
- No promotion without complete required evidence.
- No look-ahead in routing, TCA benchmarks, simulation or calibration.
- Exact configuration/model hash remains attached to every executable order.

## Production sequence

`implement -> unit test -> integration test -> simulation -> execution-cost backtest -> parity -> CI -> controlled forward test -> production gate`

This roadmap deliberately builds on the existing Midas architecture rather than replacing it.
