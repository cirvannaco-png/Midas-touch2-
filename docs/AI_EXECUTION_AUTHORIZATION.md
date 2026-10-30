# Midas execution authorization and position reconciliation

## Broker execution authority

The Midas EA is the only authorized broker-execution principal. External AI assistants may retrieve evidence, explain risk, generate candidate parameters, and propose actions. They may not call a broker adapter, submit an order, close exposure, or modify a live position.

The execution authorization contract is fail-closed. An execution request must identify the Midas EA as principal, use a recognized environment, hold authoritative persistent portfolio admission, have an available execution ledger and Midas risk/protective-stop controls, and complete the mandatory gates in their canonical order. Production execution additionally requires validated demo evidence and explicit human approval.

No AI-driven change may bypass the EA's existing InpRequireExecutionLedger, risk checks, stop protections, exposure checks, or emergency stop. A missing or stale ledger acknowledgement blocks new exposure; it must not be converted into an advisory warning.

## Position modification evidence

A successful trade-server result for a trailing-stop update is not, by itself, an acknowledged reconciliation. The EA reads the broker-applied SL/TP and current position size, recalculates stop risk using the account's configured per-trade risk unit, and records the event through the authenticated /execution-ledger/position-modification endpoint.

Each event has a unique evidence reference and a canonical payload fingerprint. Identical retries are idempotent; reusing a reference for different broker state is rejected. The service updates the durable risk reservation and stores immutable modification evidence in the same transaction. It rejects stop changes that worsen the existing protective stop.

The EA writes unacknowledged events to a per-account/per-magic/symbol/timeframe common-files queue. It retries the same evidence after transport failure or restart. While an event is pending, the EA blocks another modification for that position and blocks new entries until the queue is acknowledged and the full broker snapshot reconciles.

## Production authentication configuration

BRIDGE_API_KEY is the canonical credential used by GitHub Actions and authenticated bridge requests. SECRET_KEY remains a backward-compatible fallback for existing deployments. The Render synchronization script writes the same secure source value to both variable names to prevent another key-name mismatch. Never commit, log, or paste either value into a ticket or chat.

After the branch is reviewed and merged, a maintainer must synchronize the existing GitHub BRIDGE_API_KEY with the Render production service using the secret-sync script from a trusted runner. If the credential itself needs to rotate, coordinate the same new value with the MT5 EA's bridge API key input and test the full authenticated health preflight before enabling production maintenance. A code merge alone does not change existing Render environment values.