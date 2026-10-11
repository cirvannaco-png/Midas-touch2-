# Production Maintenance, Recovery, and Reconciliation

## Ownership and operator configuration

GitHub Actions on canonical GitHub `main` owns scheduled production maintenance. The `production` GitHub Environment must be restricted to `main` and configured with environment secrets `BRIDGE_BASE_URL` and `BRIDGE_API_KEY`. The URL must be HTTPS without embedded credentials, whitespace, query, or fragment. Never paste the API key into issues, logs, commits, or this document.

Do not run production maintenance as a casual diagnostic. Recalibration, subscription enforcement, and recovery POSTs can change production data or send notifications. This code change adds guards; it does not itself dispatch those operations, configure secrets, or verify an actual production run.

## Scheduled operations

- Saturday at 06:00 UTC: alternate-week recalibration guard. It checks bridge and database health first, does not retry the state-changing POST, and requires a response with `status=ok` and a non-empty cycle ID. A no-data response is not a successful calibration.
- Daily at 07:00 UTC: subscription enforcement after bridge/database health preflight and strict response-counter validation.
- Daily at 08:00 UTC: bounded recovery sweep for stale/failed signal and trade-event delivery notifications. Each route is called once with retries disabled. A non-empty remaining backlog fails the workflow, making it visible rather than silently green.

If a state-changing POST times out, the result is ambiguous. Inspect the bridge/database state and logs before manually running the operation again. Automatic retries are deliberately disabled to prevent duplicate cycles or messages.

## Durable execution recovery invariants

Before a broker submission, persist the order identity, immutable client-order identity, parent identity (for children), and requested quantity. Persist broker fill IDs to make delivery of the same fill event idempotent. Replaying a fill with the same ID and values is a no-op; reusing that ID with different quantity or price is an integrity fault. Cumulative fills must not exceed the requested quantity. A late fill after cancellation is not considered a full fill unless cumulative quantity reaches the requested quantity.

After restart or an ambiguous acknowledgement, query the broker using the original venue/client identity and reconcile the response. Never submit a replacement order merely because the original acknowledgement was lost. Persisted state transitions are validated; venue order identity cannot be silently rebound. EA/backend parity remains false until both sides have non-empty, matching ordered event histories.

## Reconciliation invariants

Broker status and cumulative filled quantity must both be available and consistent with OMS state before the order can resume. Missing, non-finite, negative, over-request, contradictory, or ambiguous broker values fail closed. Divergence requires query/reconciliation; it must not be silently overwritten or treated as successful recovery.

The SQLite journal is a local/reference implementation and test fixture—not an appropriate shared journal for a multi-instance live deployment. Production deployments require shared transactional persistence with equivalent uniqueness, row-locking, and recovery semantics. The notification-delivery sweep only recovers Telegram signal/trade-event notifications; it does **not** reconcile MT5 broker positions or orders. Broker reconciliation remains a separate execution control.

## Release evidence required

1. Exact candidate SHA passes GitHub CI and relevant structural checks.
2. MetaEditor compiles the latest EA source with zero errors and warnings.
3. Regression tests cover replayed fill events, late fills, identity reuse, illegal transitions, missing broker evidence, overfills, and EA/backend parity.
4. The production environment secrets are configured by an authorized operator and health preflight passes.
5. Maintenance results include a persisted calibration cycle ID and accurate recovery backlog counters. Do not retry an ambiguous state-changing POST until the first attempt has been investigated.
6. Broker reconciliation is demonstrated against the real adapter with restart, partial-fill/cancel race, lost acknowledgement, duplicate event, and deferred/out-of-order event cases.
7. Matched out-of-sample backtests and demo forward testing are complete before live-trading certification.

Green CI proves the tested code passes those checks; it does not prove strategy profitability or live-trading readiness.
