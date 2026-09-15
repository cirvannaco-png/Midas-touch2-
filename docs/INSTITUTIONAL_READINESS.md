# Midas Institutional Readiness Checklist

This checklist separates **software maturity** from external infrastructure and broker validation.

## Completed in repository

- [x] Canonical TradeSetup contract and strategy pipeline
- [x] Fail-closed pre-trade risk and persistent portfolio admission
- [x] Governed OMS/execution policy and venue abstraction
- [x] Durable child-order/client-order recovery journal
- [x] EA/backend execution parity records
- [x] Reconciliation and late/partial-fill recovery coverage
- [x] Execution TCA primitives for arrival price, slippage, spread and impact
- [x] Prediction separation: model score / calibrated probability / expected return
- [x] Regime-aware allocation with sample sufficiency
- [x] Model/strategy/configuration lineage primitives
- [x] Institutional promotion evidence gate
- [x] Portfolio budget admission gate
- [x] Operational kill-switch state machine
- [x] Adversarial execution stress scenarios
- [x] PSI/Jensen-Shannon drift monitoring primitives
- [x] Calibration error monitoring primitive
- [x] Audit-grade decision record primitive
- [x] CI intentionally paused during hardening

## Remaining software work before CI re-enable

1. Run the full Python/Telegram/tools test suites and correct every failure.
2. Add integration tests connecting the new control plane to the existing OMS,
   pre-trade risk, recovery, reconciliation, surveillance and lifecycle adapters.
3. Add end-to-end provenance assertions so every executable decision carries a
   lineage fingerprint through order creation, child order, fill, reconciliation,
   TCA and outcome.
4. Add strategy/regime/venue attribution reports over resolved historical data.
5. Add realistic cost/slippage stress fixtures and walk-forward/OOS fixtures.
6. Add negative tests proving unknown state, stale data, governance mismatch,
   duplicate orders and unresolved reconciliation can never execute.
7. Re-enable CI only after the local/available validation suite is clean.

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
trading truth. citehttps://render.com/docs/free

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
