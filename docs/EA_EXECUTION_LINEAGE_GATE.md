# EA strategy-to-execution lineage gate

## Current verified state

The live `EA/MedisTouch_v2.8.mq5` execution path currently generates `TradeSetup` objects through `CTradeDecision`, validates the chosen BUY/SELL setup through `CRiskEngine`, passes that setup by value into `CDecisionEngine::Decide`, persists the resulting `TradeDecisionRecord`, and routes the decision through the broker/order manager. `COutcomeTrackerLive` is linked back to the decision through `decision_id` and receives execution/close events from `OnTradeTransaction`.

The market-state layer is real and already present: `CRegimeDetector` combines trend structure, ATR-percentile volatility and market phase into `TRENDING`, `RANGING`, `TRANSITION`, or `UNDEFINED`. The strategy selector now treats that regime as the authoritative eligibility context.

## Remaining blocking gap

The selected non-SMC strategy still cannot manufacture the executable `TradeSetup` that reaches risk and execution. Momentum Breakout, Mean Reversion and Key-Level Reaction therefore remain diagnostic/readout engines even though their eligibility is now hardened.

The authoritative invariant remains:

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

The feature must not be promoted to production until the live EA path has an authoritative strategy setup builder for every strategy it can select, and the lineage is exercised end-to-end, followed by MQL5 compilation, historical execution-cost testing, walk-forward/parity validation, and controlled demo forward testing.
