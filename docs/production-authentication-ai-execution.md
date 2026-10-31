# Production bridge authentication and AI execution boundary

## Canonical bridge credential

The production workflows send the protected GitHub Actions environment secret
`BRIDGE_API_KEY` in the `X-API-Key` header. The bridge now uses
`BRIDGE_API_KEY` as its explicit authentication setting, with
`SECRET_KEY` retained as a compatibility alias. When both are configured,
startup validation requires an exact match. A mismatch fails closed rather than
letting the health-check and maintenance workflows silently disagree with the
running bridge.

The production Render service is `midas-touch2` in Frankfurt
(`srv-daobbbrtqb8s73elh44g`). The manual workflow
`.github/workflows/production-auth-sync.yml` synchronizes the protected
GitHub `BRIDGE_API_KEY` value into both Render environment keys
`BRIDGE_API_KEY` and `SECRET_KEY`, preserves other service variables, and
triggers a deployment. It requires the protected production environment to
contain both `BRIDGE_API_KEY` and `RENDER_API_KEY`. Never put either value
in source code, issues, logs, or chat.

After the change is merged to `main`, an authorized operator must dispatch
**Synchronize production bridge authentication** from the `main` branch.
Provision a separate, random `MT5_EXECUTION_API_KEY` of at least 32 characters
in the same protected GitHub production environment and in the MT5 EA input
`InpMT5ExecutionApiKey`. It must not equal `BRIDGE_API_KEY`. The workflow
synchronizes it to the Render service but cannot configure the local MT5
terminal's input value. Keep it available only to the EA operator and the
production bridge. The EA refuses ledger initialization until this value is
present. Then verify that the deployment is healthy and rerun the production
health-check and maintenance workflows. The rotation is not complete until
the authenticated ledger-health endpoint returns HTTP 200 and the subscription
sweep completes with a valid response.

## AI authority boundary

AI agents may analyze, explain, and propose. They cannot reserve execution
risk, submit orders, change stops, close positions, cancel orders, or alter
risk limits. Every broker-mutating bridge route requires both the general `X-API-Key` and
the distinct `X-MT5-Execution-Key` capability. The general key alone cannot
reserve risk or alter broker state. The request's `requested_by=MT5_EA` value is
an additional assertion, not an authentication factor; only the MT5 EA is
provisioned with the dedicated execution key. An AI-provided approval flag is
not execution authorization. A human-approved proposal must return to the normal MT5 EA
order-check, risk, persistent-admission, execution-ledger, broker-acknowledgment,
and reconciliation path.

## Position-modification reconciliation

The EA writes a unique durable modification intent before calling the broker.
It then reads the actual stop and target from MT5 and submits those observed
values for confirmation. The bridge checks the registered position, direction,
monotonic stop protection, and non-increasing reserved risk before marking the
event applied. A pending intent blocks new portfolio reservations.

If the result is ambiguous, startup/periodic broker snapshots reconcile the
actual broker state, and a broker-confirmed position close resolves any
remaining pending intent. The EA's local admission latch remains closed after
a transport or ledger failure until a complete broker snapshot reconciles the
account. Protective stop changes are still attempted when the ledger is
unavailable; failing to protect an existing open trade would be the wrong
safety response.

## Research isolation

Candidate selection receives only explicitly tagged training and validation
partitions. The helper rejects role contamination and validates strict
chronological boundaries against the locked OOS interval. Locked OOS records
are not returned to candidate selection and remain available only to the
separate one-shot locked-OOS evaluation process.
