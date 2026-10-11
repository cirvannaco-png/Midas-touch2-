# Midas Touch VPS Deployment Standard

## Purpose

The VPS is the persistent execution runtime for the Midas Touch MT5 Expert Advisor. It is not a replacement for the backend, payment system, authorization layer, or Render services.

## Production topology

```text
GitHub main (canonical source; deployment connection must be verified)
        |
        v
Render bridge/API -> PostgreSQL
        |
        v
authenticated signal/outcome path
        |
        v
VPS / Windows -> MT5 Terminal -> Midas Touch EA -> Broker
```

The diagram shows the intended architecture, not verified live deployment state. Confirm the actual Render-connected repository/provider, deployed commit, environment and database in the service control plane. Do not assume a service was repointed merely because GitHub is the canonical repository. GitLab is an optional source-tree mirror only.

## Execution boundary

The EA/VPS must not bypass these gates:

`SIGNAL -> Freshness/Stale Protection -> Eligibility -> Paid Subscription -> Entitlement -> Explicit Copy Authorization -> Broker Capability/Symbol Mapping -> User Risk Validation -> Risk Gate -> Portfolio Gate -> Persistent Portfolio Admission -> Execution Ledger -> OrderCheck -> OrderSendAsync -> Broker Acknowledgement -> OnTradeTransaction -> Position Observation -> Reconciliation -> Outcome/Accuracy Telemetry`

Any failed mandatory gate is a hard STOP. Best-effort execution is prohibited.

A caller-provided `portfolio_admitted=true` value is never authoritative proof of persistent admission. The execution boundary must verify authoritative portfolio state immediately before broker submission.

## VPS runtime requirements

- Windows VPS capable of running the required MT5 terminal continuously.
- Stable network connectivity and synchronized system clock.
- MT5 terminal configured for the intended broker account.
- Midas Touch EA attached only to approved symbols/timeframes/configurations.
- Automatic terminal/EA recovery after restart or network interruption.
- Health/watchdog monitoring for terminal, EA, broker connection, and backend connectivity.
- Secure machine-level storage for runtime secrets; never commit secrets to GitHub or GitLab.
- No broker credentials in the Telegram bridge.
- Structured execution/audit telemetry without credentials, copy keys, or payment secrets.
- Restart reconciliation before accepting new execution after an outage.
- Duplicate-order protection and persistent execution ledger.

## Recovery sequence

After VPS, MT5, EA, or network recovery:

1. Confirm backend authentication and connectivity.
2. Reconcile broker positions/orders against authoritative execution state.
3. Restore only approved configuration.
4. Confirm symbol/broker capability mapping.
5. Confirm portfolio admission state.
6. Resume signal consumption only after reconciliation succeeds.

If reconciliation cannot establish a trustworthy state, execution remains blocked.

## Latency telemetry

Persist UTC audit timestamps and use a monotonic clock for internal duration measurement at:

`T0 Signal generated -> T1 Signal received -> T2 Eligibility -> T3 Entitlement -> T4 Copy authorization -> T5 Risk validation -> T6 Portfolio admission -> T7 OrderCheck -> T8 OrderSendAsync -> T9 Broker acknowledgement -> T10 Position observed -> T11 Reconciliation`

Required latency fields include transport, eligibility, authorization, risk, portfolio, order-check, broker submission, broker acknowledgement, reconciliation, and end-to-end latency.

## VPS deployment policy

GitHub Actions is the canonical source/CI system; its repository checks and maintenance workflow do not configure the VPS or prove that the Render bridge is currently connected to GitHub. MQL5 structural validation does not replace authoritative MetaEditor compilation or Strategy Tester evaluation.

No VPS deployment is considered production-ready merely because a GitHub or GitLab pipeline passes. The VPS must additionally pass terminal startup, broker connectivity, EA initialization, signal receipt, authorization gates, order-check, execution acknowledgement, and reconciliation tests, followed by controlled demo/forward validation.
