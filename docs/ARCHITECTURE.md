# Medis Touch Architecture

## Canonical copy-trading control plane

Signal -> Eligibility -> Subscription Entitlement -> Explicit Copy Authorization -> Risk Validation -> Portfolio Admission -> Execution Ledger -> OrderCheck -> Broker Submission -> Broker ACK -> Position Observation -> Reconciliation -> Outcome.

Every stage is a hard gate. Failure stops execution. Subscription/payment never implies trading authorization.

## User risk policy

Users choose their requested risk. The platform enforces an independent system maximum and rejects invalid or excessive risk rather than silently increasing or rewriting the request.

```text
User chooses risk
  -> paid
  -> entitled
  -> copy explicitly enabled
  -> broker supported
  -> signal valid/not stale
  -> risk within limits
  -> portfolio exposure acceptable
  -> execution allowed
```

## Broker boundary

The bridge accepts broker identity/capability, not broker passwords. Credentials remain in the user's MT5/connector boundary. Broker-specific adapters must implement a common execution contract.

Target broker registry: Exness, Pepperstone, HFM, IC Markets, XM, IG, OANDA, AvaTrade, FXTM, FP Markets. `Pepperdine` is a compatibility alias for Pepperstone.

## Freshness

The copy path rejects signals older than five minutes as a hard baseline. Instrument-specific policies may impose tighter operational limits, especially for XAUUSD. Signal creation time, receipt time and age are recorded.

## Latency

Critical-path timestamps are T0 signal generated, T1 received, T2 eligibility, T3 entitlement, T4 authorization, T5 risk, T6 portfolio admission, T7 OrderCheck, T8 OrderSendAsync, T9 broker acknowledgement, T10 position observed and T11 reconciliation. Internal durations use monotonic clocks; UTC timestamps are used for audit correlation.

## Accuracy

Accuracy is multidimensional: signal accuracy, execution accuracy, price accuracy, risk accuracy, reconciliation accuracy and outcome accuracy. Record requested versus executed entry, volume, direction, risk and position, plus slippage and deviation.

## Refactoring sequence

Phase A: security and application/domain boundaries.
Phase B: route decomposition into `api/` modules.
Phase C: application service extraction.
Phase D: split the legacy model registry into signal, trade, calibration, promotion, research, execution and portfolio modules. Remove the legacy registry only after CI proves all consumers migrated.
