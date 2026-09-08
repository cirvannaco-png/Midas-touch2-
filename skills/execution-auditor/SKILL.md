---
name: execution-auditor
description: Audit Medis Touch broker capability, risk, portfolio admission, execution ledger and latency/accuracy telemetry.
metadata:
  slash-command: enabled
---

# Broker and Execution Auditor

Audit the canonical execution chain and its fail-closed semantics.

Broker capability set is exactly ten: Exness, Pepperstone, HFM, IC Markets, XM, IG, OANDA, AvaTrade, FXTM and FP Markets. `Pepperdine` is only an explicit alias for Pepperstone.

Verify the latency points T0-T11 and persisted latency dimensions, plus multidimensional accuracy telemetry: signal, execution, price, risk, reconciliation and outcome accuracy.

XAUUSD uses the five-minute hard stale rejection baseline. Do not weaken freshness requirements.

Do not claim broker execution is live without actual broker/account configuration and end-to-end evidence.
