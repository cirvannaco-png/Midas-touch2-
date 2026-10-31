---
name: execution-auditor
description: Audit Medis Touch broker capability, risk, portfolio admission, execution ledger and latency/accuracy telemetry.
metadata:
  slash-command: enabled
---

# Broker and Execution Auditor

Audit the canonical execution chain and its fail-closed semantics.

Broker coverage is provider-agnostic. Do not maintain a fixed vendor allowlist or vendor-specific execution branch. The supported venue is the broker/account connected through MetaTrader 5. Validate the live terminal connection and each selected symbol's visibility, trade mode, tick/point/contract values, minimum/maximum/step volume, execution and filling modes, stop/freeze levels, trading sessions, free margin, account currency, leverage, and margin mode. Unknown, unavailable, or inconsistent capabilities fail closed. Never infer support from a broker brand, and never claim a selected broker is demo-validated until its own account-level evidence exists.

Verify the latency points T0-T11 and persisted latency dimensions, plus multidimensional accuracy telemetry: signal, execution, price, risk, reconciliation and outcome accuracy.

XAUUSD uses the five-minute hard stale rejection baseline. Do not weaken freshness requirements.

Do not claim broker execution is live without actual broker/account configuration and end-to-end evidence.
