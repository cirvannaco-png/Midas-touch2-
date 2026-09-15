# Midas Institutional Control Plane

## Objective

Midas should be institution-grade in **control quality** before it is institution-grade in infrastructure. The control plane therefore stays deterministic, auditable, fail-closed, and lightweight enough to validate on the current Render Free footprint.

Render Free is a temporary development/validation constraint. Render documents that Free web services can spin down after 15 minutes, have an ephemeral filesystem, cannot attach persistent disks or scale beyond one instance, and Free Postgres expires after 30 days. Those limits mean durable trading state must remain in the database/recovery design and the broker/EA must remain the execution source of truth until paid infrastructure is introduced. citehttps://render.com/docs/free

## Control chain

```text
Market/Data Freshness
        ↓
Model + Strategy Lineage
        ↓
Calibration / Expected Return
        ↓
Portfolio Budget
        ↓
Pre-trade Risk
        ↓
Governance Hash
        ↓
OMS / Execution Policy
        ↓
Broker / EA
        ↓
Reconciliation
        ↓
TCA / Outcome
        ↓
Surveillance / Drift
        ↓
Promotion / Rollback
```

## Hard gates

1. **Model lineage** — every decision identifies model, strategy, regime, calibration, risk, execution and configuration versions.
2. **Prediction separation** — `model_score`, `calibrated_probability`, and `expected_return` remain distinct.
3. **Portfolio budget** — persistent admission is bounded by an explicit budget; caller-provided admission is never authoritative.
4. **Operational control** — venue, reconciliation, freshness, risk, governance, drawdown and duplicate-order failures halt execution.
5. **Drift/degradation** — model drift or execution degradation restricts operation instead of silently continuing at full size.
6. **Promotion evidence** — code/data/OOS/walk-forward/stress/cost/calibration/risk/paper-trading gates and minimum sample size are mandatory.
7. **Stress integrity** — a scenario fails if reconciliation, duplicate-order, or unknown-position integrity fails, even when P&L looks acceptable.
8. **Auditability** — decision records retain the immutable lineage fingerprint and independent prediction quantities.

## Kill-switch hierarchy

```text
NORMAL
  ↓ degradation/drift
RESTRICTED
  ↓ critical integrity/risk failure
HALTED
```

Recovery is not an automatic `restart → trade` operation. It must reconcile broker truth, restore governance/version integrity, and re-establish valid market-data/risk state before execution resumes.

## Validation target

The following must be demonstrated before calling the software **institution-ready**:

- deterministic unit/regression coverage for every control;
- realistic execution-cost and slippage analysis;
- walk-forward and out-of-sample evidence;
- calibration evidence with sufficient samples;
- adversarial stress scenarios for execution and recovery;
- reconciliation with no unresolved unknown positions/orders;
- TCA attribution of execution cost;
- surveillance thresholds and controlled restriction/halt behaviour;
- promotion and rollback artifacts with immutable version lineage.

MetaEditor compilation and live/demo broker validation remain external gates and are intentionally not represented as passed by software tests.
