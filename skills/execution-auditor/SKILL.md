---
name: execution-auditor
description: Audit Medis Touch broker capability, risk, portfolio admission, execution ledger and latency/accuracy telemetry.
metadata:
  slash-command: enabled
---

# Broker and Execution Auditor

Audit the canonical execution chain and its fail-closed semantics.

Do not maintain a fixed broker-provider allowlist or assume capabilities from a broker name. The account owner selects the provider in MetaTrader 5. Inspect the actual connected account, margin mode, symbol properties, server sessions, execution responses and deal history. Reject unsupported account modes and fail closed when required properties are missing, stale, contradictory or non-finite.

Verify the latency points T0-T11 and persisted latency dimensions, plus multidimensional accuracy telemetry: signal, execution, price, risk, reconciliation and outcome accuracy.

XAUUSD uses the five-minute hard stale rejection baseline. Do not weaken freshness requirements.

Do not claim broker execution is live without actual broker/account configuration and end-to-end evidence.
