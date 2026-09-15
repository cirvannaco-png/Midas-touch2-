# Midas Institutional Readiness Checklist

This checklist separates **software maturity** from external infrastructure and broker validation.

## Completed in repository

- [x] Canonical TradeSetup contract and fail-closed strategy pipeline
- [x] Fail-closed pre-trade risk and persistent portfolio admission
- [x] Governed OMS/execution policy and venue abstraction
- [x] Durable parent/child/client-order recovery journal
- [x] EA/backend execution parity records
- [x] Reconciliation and late/partial-fill recovery coverage
- [x] Execution TCA primitives for arrival price, slippage, spread and impact
- [x] Prediction separation: model score / calibrated probability / expected return
- [x] Regime-aware allocation with sample sufficiency
- [x] Model/strategy/configuration lineage primitives
- [x] Backend execution lineage propagated into the durable state journal
- [x] Institutional promotion evidence gate
- [x] Portfolio budget admission gate
- [x] Portfolio concentration/correlation guardrails
- [x] Operational kill-switch state machine
- [x] Execution rate/repetition throttle primitives
- [x] Adversarial execution stress scenarios
- [x] PSI/Jensen-Shannon drift monitoring
- [x] ECE/Brier/calibration monitoring
- [x] Fail-closed broker metadata validation
- [x] Audit-grade decision record primitive
- [x] CI paused with `[skip ci]` commits and the institutional MR closed during hardening

## Remaining software work before CI re-enable

1. Execute the complete Python/Telegram/tools test suites and correct every failure.
2. Complete integration tests connecting portfolio controls, throttle, control state,
   OMS, pre-trade risk, recovery, reconciliation, surveillance, TCA and lifecycle.
3. Add end-to-end provenance assertions for decision → child order → fill →
   reconciliation → TCA → outcome, including EA-side sequence parity fixtures.
4. Add strategy/regime/venue attribution reports over resolved historical data.
5. Add realistic cost/slippage stress fixtures and walk-forward/OOS evidence fixtures.
6. Expand negative/fault-injection tests for restart, timeout, duplicate, stale-data,
   unknown-position, governance mismatch and reconciliation failure paths.
7. Run static Python validation and repository-wide invariant checks before CI restore.
8. Re-enable CI only after the local/available validation suite is clean.

## External gates deliberately not claimed as complete

- MetaEditor/MQL5 compilation on the authoritative terminal.
- Live/demo broker validation.
- Long-horizon forward performance evidence.
- Production-grade always-on infrastructure.

## Render Free boundary

The current Render Free deployment is treated as a validation/control-plane
runtime, not as a production trading runtime. Render documents that Free web
services can sleep after 15 minutes, use ephemeral filesystems, cannot attach
persistent disks or scale beyond one instance, and Free Postgres expires after
30 days. The code therefore must never treat local service state as durable
trading truth.

The eventual upgrade path is infrastructure, not architecture replacement:

```text
Render Free
   ↓
validated control plane
   ↓
paid always-on service + durable datastore/queue
   ↓
production monitoring / resilience
   ↓
broker-validated live operation
```
