# EA strategy-to-execution lineage gate

## Current verified state

The live `EA/MedisTouch_v2.8.mq5` execution path currently generates `TradeSetup` objects through `CTradeDecision`, validates the chosen BUY/SELL setup through `CRiskEngine`, passes that setup by value into `CDecisionEngine::Decide`, persists the resulting `TradeDecisionRecord`, and routes the decision through the broker/order manager. `COutcomeTrackerLive` is linked back to the decision through `decision_id` and receives execution/close events from `OnTradeTransaction`.

This is a real setup-to-outcome lineage, but it is **not yet the required selected-strategy lineage**.

## Blocking gap

`CStrategySelector` and the strategy engines (`CMomentumBreakoutEngine`, `CMeanReversionEngine`, and `CKeyLevelEngine`) are currently diagnostic/readout components. `TradeSetup` generation remains in `CTradeDecision` and is SMC/FVG based. Therefore a non-SMC strategy can be identified diagnostically but does not yet manufacture the executable `TradeSetup` that reaches risk and execution.

The authoritative invariant must be:

```text
regime
  -> authoritative strategy selection
  -> selected strategy builds COMPLETE TradeSetup
  -> structural validation
  -> pre-trade risk
  -> portfolio admission/reservation
  -> governed OMS/execution
  -> broker
  -> execution reconciliation
  -> OutcomeTracker
  -> strategy-confidence calibration
```

No non-SMC strategy may be silently replaced by an SMC setup. A selected strategy that cannot produce a complete setup must fail closed.

## Setup immutability requirement

After the completed setup crosses the strategy boundary, downstream components may attach execution/governance metadata, but must not mutate the strategy thesis fields:

- direction/type
- entry range
- structural invalidation
- protective stop
- TP1/TP2/final TP
- strategy provenance
- creation time
- confidence at decision time

Calibration observations and execution-cost observations remain separate from the strategy thesis. The same setup must remain traceable by `decision_id` and an immutable setup fingerprint/snapshot across risk, portfolio, execution, broker acknowledgement/recovery, and outcome processing.

## Production gate

This document is a gate, not a claim of completion. MR !7 must not be promoted to production until the live EA path has an authoritative strategy setup builder and the above lineage is exercised end-to-end, followed by MQL5 compilation, historical execution-cost testing, walk-forward/parity validation, and controlled demo forward testing.