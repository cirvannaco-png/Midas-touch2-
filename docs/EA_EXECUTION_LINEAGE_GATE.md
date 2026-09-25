# EA strategy-to-execution lineage gate

## Current code-level state

The live `EA/MedisTouch_v2.8.mq5` execution path generates `TradeSetup` objects through `CTradeDecision`, validates the selected BUY/SELL setup through `CDecisionEngine::ValidateSetupGeometry`, persists the resulting `TradeDecisionRecord`, and routes the decision through the broker/order manager. `COutcomeTrackerLive` remains linked to the decision through `decision_id` and receives execution/close events from `OnTradeTransaction`.

The market-state layer is authoritative for strategy eligibility: `CRegimeDetector` combines trend structure, ATR-percentile volatility and market phase into `TRENDING`, `RANGING`, `TRANSITION`, or `UNDEFINED`. `CStrategySelector` uses that state to select one eligible strategy without summing heterogeneous strategy scores.

Strategy authority is implemented inside `CTradeDecision::Generate()`. `SelectPeerStrategy()` selects the eligible strategy, `BuildSMC()` constructs the SMC setup, and `BuildNonSMC()` dispatches Momentum Breakout, Mean Reversion, or Key-Level Reaction to its owned builder. Candidate setups are rejected when incomplete or geometrically invalid; the broker spread floor is reapplied and the thesis invalidation relationship is rechecked. A selected challenger is never silently replaced by SMC.

## Authoritative lineage

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

## Setup immutability and persistence

After the completed setup crosses the strategy boundary, downstream components may attach execution/governance metadata, but must not mutate the strategy thesis fields:

- direction/type
- entry range
- structural invalidation
- protective stop
- TP1/TP2/final TP
- strategy provenance
- creation time
- confidence at decision time

`DecisionStore` persists the thesis invalidation and selected strategy across restart. The bridge contract now carries and persists `invalidation`, `final_tp`, and `strategy`; bridge validation enforces their geometric relationship when supplied. Copy-feed responses preserve the same fields so downstream subscribers do not receive a degraded setup contract.

Calibration observations and execution-cost observations remain separate from the strategy thesis. The same setup remains traceable by `decision_id` and its persisted snapshot across risk, portfolio, execution, broker acknowledgement/recovery, and outcome processing.

## Validation status

Static lineage and production-invariant coverage now includes the EA selector/builders, decision geometry, durable decision persistence, signal publishing, bridge schema/validation/database persistence, and copy-feed preservation.

CI remains intentionally paused to preserve computation capacity. Therefore no claim of a green pipeline is made here. MetaEditor compilation, Strategy Tester execution, walk-forward/holdout validation, and controlled demo forward testing remain external certification gates.

## Production gate

The feature must not be promoted to production until the live EA path is compiled with MetaEditor with zero errors and reviewed warnings, followed by historical execution-cost testing, walk-forward/parity validation, and controlled demo forward testing with broker acknowledgement, restart recovery, duplicate-order handling, reconciliation, and telemetry verification.
