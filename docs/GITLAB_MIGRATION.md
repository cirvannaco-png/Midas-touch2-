# Medis Touch GitLab Migration

Source package: `medis_touch_repo_with_copytrading_payments.zip` supplied for this migration.

The migration target is the private GitLab project `midas-touch-group/Medis-touch`.

## Required production gates

- paid -> entitled -> copy explicitly enabled -> broker supported -> signal valid/not stale -> risk within limits -> portfolio exposure acceptable -> execution allowed
- user-selected risk is bounded by platform limits
- unsupported brokers fail closed
- broker passwords never enter the public bridge
- signals older than five minutes are rejected as the baseline stale-signal control
- execution uses an execution ledger, idempotency/request IDs, OrderCheck, asynchronous submission where validated, broker acknowledgement and reconciliation
- reconciliation mismatch blocks further execution and raises an alert

## Broker target

Exness, Pepperstone, HFM, IC Markets, XM, IG, OANDA, AvaTrade, FXTM and FP Markets. `Pepperdine` is an alias for Pepperstone.

## Latency telemetry

T0 signal generated; T1 received; T2 eligibility; T3 entitlement; T4 authorization; T5 risk; T6 portfolio; T7 OrderCheck; T8 OrderSendAsync; T9 broker acknowledgement; T10 position observed; T11 reconciliation.

Record stage latency, signal age and end-to-end latency using monotonic durations plus UTC audit timestamps.

## Accuracy telemetry

Track signal, execution, price, risk, reconciliation and outcome accuracy, including requested/actual entry, slippage, requested/executed volume and direction, expected/actual risk and expected/broker position.

## Refactoring order

Phase A security and boundaries; Phase B API route decomposition; Phase C application services; Phase D model decomposition. Large structural migrations must not be mixed with trading-behaviour changes without CI and regression evidence.

## Migration note

The supplied archive predates some later GitHub-side hardening work. The hardened domain boundary and broker registry committed during this migration are therefore treated as the canonical forward architecture. No profitability claim is implied by this migration; MT5 compilation, Strategy Tester validation and forward/demo validation remain mandatory before live-money activation.
