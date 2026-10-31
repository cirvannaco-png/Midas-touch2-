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

After this change is merged to `main`, an authorized operator should
dispatch **Synchronize production bridge authentication** from the `main`
branch. The workflow requires only the protected `BRIDGE_API_KEY` and
`RENDER_API_KEY`; it writes the canonical bridge key to Render as both
`BRIDGE_API_KEY` and the `SECRET_KEY` compatibility alias. It also removes
the retired MT5-specific environment variable from Render. Configure the EA's
`InpBridgeApiKey` with the same canonical bridge key. The workflow cannot
configure the local MT5 terminal input. After synchronization, verify the
deployment is healthy and rerun the production health-check and maintenance
workflows. The authenticated ledger-health endpoint must return HTTP 200.

## AI authority boundary

The MT5 EA finds and evaluates setups and decides when to trade. The bridge
does not perform a second MT5-specific identity check: all execution-ledger
routes require the single `X-API-Key` bridge credential, and the EA sends that
header. There is no separate MT5 key or second MT5 header.

AI agents may analyze, explain, and propose, but they must not be given the
bridge credential. The execution-origin policy rejects requests explicitly
declared as `AI_AGENT` for the protected reserve and position-modification
operations. The `requested_by=MT5_EA` field is an assertion, not a separate
authentication factor. With a single-key design, any caller that obtains the
bridge key can reach the protected API; therefore keep it restricted to the
MT5 runtime and authorized operator infrastructure. A human-approved proposal
must still pass the EA's normal order-check, risk, persistent-admission,
execution-ledger, broker-acknowledgment, and reconciliation flow.

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
