# Midas Touch — Architecture Phases and Production Gates

## Current certification status

Midas Touch is **not yet certified production-ready**. The architecture is fail-closed, but certification requires current green CI evidence plus external MetaEditor/MT5 validation and controlled forward-test evidence.

Current repository hardening is being performed on `feature/production-hardening` and reviewed through merge request `!1` before main is changed.

### Mandatory evidence gates

1. Repository structural validation.
2. Python, Telegram bridge, dependency, and invariant tests.
3. GitLab CI green on the exact candidate commit.
4. MetaEditor compilation of every production EA entry point with **0 errors**; warnings must be reviewed rather than ignored.
5. MT5 Strategy Tester backtest using the production EA/inputs, with no-lookahead and execution/indicator parity verification.
6. Walk-forward/holdout validation on actual persisted EA outcomes or an actual exported Strategy Tester OutcomeTracker dataset.
7. Controlled demo forward test with broker acknowledgement, restart recovery, duplicate-order, reconciliation, and telemetry verification.
8. Only after all preceding gates pass: production enablement.

## Non-negotiable execution chain

`SIGNAL → Freshness/Stale Protection → Eligibility → Paid Subscription → Entitlement → Explicit Copy Authorization → Broker Capability/Symbol Mapping → User Risk Validation → Risk Gate → Portfolio Gate → Persistent Portfolio Admission → Execution Ledger → OrderCheck → OrderSendAsync → Broker Acknowledgement → OnTradeTransaction → Position Observation → Reconciliation → Outcome/Accuracy Telemetry`

Any failed gate is fail-closed. No best-effort order placement.

## Payment-provider rule

Payment notifications never grant entitlement without provider verification and transaction reconciliation. The Ammer Pay adapter is currently **disabled** because its server-to-server endpoint, webhook schema, and signature contract have not been verified from a primary merchant API specification. It must not be enabled for production until those contracts are supplied and tested. A verified provider must be used instead.

## Statistical calibration rule

Regime allocations may only change when the configured sample-size, Wilson-confidence, expectancy, drawdown, and improvement gates pass. Aggregate regime statistics must not be blindly applied across strategies when strategy attribution is available; calibration must preserve strategy/regime attribution to prevent cross-strategy contamination.

## Validation limitation

Static MQL5 validation proves source/include integrity only. It does **not** prove MetaEditor compilation, broker behavior, Strategy Tester correctness, or live execution safety. Those remain explicit certification gates.
