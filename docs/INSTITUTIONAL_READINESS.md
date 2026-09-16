# Midas Institutional Readiness Checklist

This checklist separates software maturity from external infrastructure and broker validation.

## Completed in repository

- [x] Canonical TradeSetup contract and fail-closed backend strategy pipeline
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
- [x] Strategy/regime/venue execution-cost attribution helpers
- [x] Leakage-resistant walk-forward/OOS window construction
- [x] OMS-boundary failure cleanup and reservation-release fault fixture
- [x] Final Ruff lint remediation pass
- [x] Regime-aware EA strategy authority and explicit abstention
- [x] Strategy-specific EA setup builders for momentum breakout, mean reversion and key-level reaction
- [x] Durable thesis invalidation and selected-strategy persistence across EA restart
- [x] Canonical EA signal publication of invalidation, final TP, strategy and regime provenance
- [x] Telegram bridge validation and persistence of the canonical setup contract
- [x] Signal database migration for invalidation, final TP and strategy provenance
- [x] Copy-feed preservation of invalidation, final TP and strategy provenance
- [x] Static lineage gate spanning EA → DecisionStore → bridge → database → copy feed

## Active hardening / final validation gates

- [ ] Restore CI only when computation budget permits, then obtain a green hardened-branch pipeline.
- [ ] Complete end-to-end runtime provenance assertions through decision → child order → fill → reconciliation → TCA → outcome.
- [ ] Keep negative/fault-injection paths green for restart, timeout, duplicate, stale-data, unknown-position and reconciliation failure cases.
- [ ] Final branch/static invariant audit is clean in an executable environment.
- [ ] Run authoritative MetaEditor/MQL5 compilation after the strategy-builder integration.

## External gates deliberately not claimed as complete

- MetaEditor/MQL5 compilation on the authoritative terminal.
- Live/demo broker validation.
- Long-horizon forward performance evidence.
- Production-grade always-on infrastructure.

## Render Free boundary

Render Free remains a validation/control-plane runtime, not a production trading runtime. Local service state is not treated as durable trading truth. Production deployment requires durable storage, always-on compute, monitoring and broker-validated operation.
