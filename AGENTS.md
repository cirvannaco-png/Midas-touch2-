# Medis Touch AI Engineering Governance

## Mission
Preserve the Medis Touch architecture, trading behavior, security boundaries, and source integrity while enabling AI-assisted maintenance.

## Non-negotiable rules
- Treat the repository as a production trading system.
- Never alter MQL5 trading logic, strategy selection, indicator parameters, confidence thresholds, risk calculations, news filters, broker execution behavior, or signal semantics as part of refactoring unless a separate change request explicitly authorizes it.
- Preserve the canonical fail-closed execution order:
  SIGNAL -> Freshness/Stale Protection -> Eligibility -> Paid Subscription -> Entitlement -> Explicit Copy Authorization -> Broker Capability/Symbol Mapping -> User Risk Validation -> Risk Gate -> Portfolio Gate -> Persistent Portfolio Admission -> Execution Ledger -> OrderCheck -> OrderSendAsync -> Broker Acknowledgement -> OnTradeTransaction -> Position Observation -> Reconciliation -> Outcome/Accuracy Telemetry.
- A caller-provided `portfolio_admitted=true` is never authoritative proof of persistent portfolio admission.
- A payment notification never grants entitlement unless provider verification and transaction reconciliation succeed.
- Never invent undocumented payment-provider, broker, or external API contracts.
- Never place broker credentials in the Telegram bridge.
- Never log secrets, API keys, copy keys, payment credentials, or broker credentials.
- Preserve backward compatibility for existing `app.models` imports and database metadata during model decomposition.
- Do not rewrite large files merely to perform a narrow extraction. Prefer small, reviewable commits.
- Every implementation change requires targeted tests and a green GitLab pipeline before merge.
- If evidence is insufficient, stop and report the uncertainty rather than guessing.

## Change protocol
1. Inspect and map dependencies.
2. State the invariant being preserved.
3. Make the smallest safe change.
4. Add or update regression tests.
5. Run relevant validation.
6. Review the diff for source/spec drift.
7. Run GitLab CI.
8. Only then propose merge/deployment.

## Branch policy
Work on `feature/phase-a-d-hardening` for the current hardening program. Do not push directly to `main` unless the repository policy explicitly permits it and the change has passed review.

## MQL5 policy
`EA/` is protected architecture. Structural validation is required, but Python-side refactors must not modify EA trading behavior. MetaEditor remains the authoritative compiler for final MQL5 compilation.

## Phase policy
- Phase A: security, copy boundary, broker capabilities, freshness, risk.
- Phase B: API route decomposition.
- Phase C: application-service extraction.
- Phase D: seven-domain model decomposition with compatibility exports.

A phase is not complete because files exist. It is complete only when its architectural gates, regression tests, and CI evidence pass.
