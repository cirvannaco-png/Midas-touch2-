---
name: execution-auditor
description: Audit Medis Touch broker capability, risk, portfolio admission, execution ledger and latency/accuracy telemetry.
metadata:
  slash-command: enabled
---

# Broker and Execution Auditor

Audit the canonical execution chain and its fail-closed semantics.

Broker support is provider-neutral within the MetaTrader 5 execution boundary: do not maintain a fixed brand whitelist or assume any specific broker. Accept any broker/server reachable through the user's MT5 terminal when it supports the required trade operations. Discover account margin mode, symbol contract/tick values, volume min/max/step, trade/fill modes, stop/freeze levels, market sessions, account currency and server-time offset from the terminal at runtime. Fail closed when required capabilities are missing, inconsistent or cannot be validated. Keep broker-specific costs and restrictions in the selected account's test manifest, not in shared strategy logic.

Verify the latency points T0-T11 and persisted latency dimensions, plus multidimensional accuracy telemetry: signal, execution, price, risk, reconciliation and outcome accuracy.

XAUUSD uses the five-minute hard stale rejection baseline. Do not weaken freshness requirements.

Do not claim broker execution is live without actual broker/account configuration and end-to-end evidence.
