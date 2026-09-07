# Medis Touch Architecture Governor

## Mission
Preserve Medis Touch trading behavior while allowing infrastructure, security, observability, and deployment hardening. Treat every change as a production integration.

## Non-negotiable execution invariant
No trade may reach broker submission unless all authoritative gates pass:

SIGNAL -> FRESHNESS -> ELIGIBILITY -> PAID/ENTITLED -> EXPLICIT COPY AUTHORIZATION -> BROKER CAPABILITY -> USER RISK BOUND -> RISK GATE -> AUTHORITATIVE PERSISTENT PORTFOLIO ADMISSION -> EXECUTION LEDGER -> ORDER CHECK -> ORDER SEND -> BROKER ACK -> TRADE TRANSACTION -> POSITION OBSERVATION -> RECONCILIATION -> OUTCOME

Any failed, missing, stale, ambiguous, or unverifiable gate is fail-closed: STOP. Never trade on best effort.

## Trading-logic preservation
- Do not change signal-generation, strategy-selection, indicator, confidence, SL/TP, or calibration behavior during infrastructure/security work unless a defect is demonstrated and the change is explicitly scoped.
- Do not infer broker API contracts from memory or unrelated providers.
- Do not silently clamp user-requested risk. If requested risk exceeds the system maximum, reject the request.
- `portfolio_admitted=true` supplied by a caller is not authoritative proof of admission. The execution boundary must verify authoritative persistent portfolio state immediately before broker submission.

## Broker registry
Canonical broker capabilities: Exness, Pepperstone, HFM, IC Markets, XM, IG, OANDA, AvaTrade, FXTM, FP Markets.

Compatibility alias: Pepperdine -> Pepperstone. The alias is not an additional broker capability.

A broker is not production-ready merely because its name exists in a registry. Require verified symbol mapping, execution constraints, risk/volume rules, and controlled demo validation.

## Freshness
Baseline hard stale rejection is 5 minutes. Instrument-specific freshness policies may be introduced only as an explicit policy layer. Preserve `signal_age_ms` and fail closed when freshness cannot be established.

## Observability
Use monotonic duration measurement for latency intervals and UTC timestamps for audit records. Target checkpoints include signal generation, receipt, eligibility, entitlement, authorization, risk, portfolio admission, OrderCheck, submission, broker acknowledgement, position observation, and reconciliation.

Track multidimensional accuracy: signal, execution, price, risk, reconciliation, and outcome. Never reduce production accuracy reporting to win rate alone.

## Copy security
Copy-feed access requires authenticated copy credentials, explicit authorization, entitlement, and auditability. Support key rotation, revocation, last-use tracking, failed-attempt tracking, rate limiting, constant-time verification where applicable, and secret-free logs. Migrate backward-compatibly.

## Payment security
A payment notification alone must never grant copy-trading entitlement. Payment status must be cryptographically verified where supported and reconciled against expected user, amount, currency, plan, and transaction identifier. Never guess an unverified payment-provider API contract.

## Change protocol
Inspect -> prove -> propose -> test -> approve -> change.

Prefer focused branches and merge requests. Keep structural route/model decomposition separate from security/copy/broker hardening phases. Every production-affecting change must pass CI and have an explicit rollback path.

## Production gates
Do not enable global copy trading until payment verification, entitlement, copy authorization, portfolio admission, execution acknowledgement/reconciliation, monitoring, and controlled broker testing have passed.
