# Durable Execution Recovery and EA/Backend Parity

## Recovery invariant

A broker submission crosses an external side-effect boundary. Before that call, the execution identity is journaled as `SUBMITTING`. If acknowledgement is ambiguous, the durable state becomes `UNKNOWN` and the reservation remains held. Recovery queries and adopts the existing broker order identity; it never retries the order as a new exposure.

## Partial fill / cancellation invariant

`PARTIALLY_FILLED -> CANCEL_PENDING -> CANCELLED` does not erase fills. A late broker fill is accepted against the same order identity and advances the durable state to `FILLED` only when cumulative filled quantity reaches the authorized quantity at the integration boundary. Parent/child conservation remains an OMS invariant.

## EA/backend parity

Both sides must publish the same ordered execution events using the same `decision_id`, immutable setup fingerprint, status, cumulative filled quantity and average fill price. The durable parity journal compares the complete sequence rather than merely the terminal state. Divergence is therefore detectable even when both sides eventually report `FILLED`.

## Production requirement

SQLite provides transactional persistence and concurrency tests for the local reference implementation. Production multi-instance deployments must use a shared transactional database with equivalent row/transaction semantics. Broker reconciliation remains mandatory after restart or ambiguous acknowledgement.
