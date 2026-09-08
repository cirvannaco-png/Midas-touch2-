# Medis Touch — Phase A-D Architecture Gates

This document is the release gate for the staged Medis Touch hardening/refactor. It is intentionally conservative: infrastructure and architecture changes must not silently change trading decisions.

## Non-negotiable execution chain

`SIGNAL → Freshness/Stale Protection → Eligibility → Paid Subscription → Entitlement → Explicit Copy Authorization → Broker Capability/Symbol Mapping → User Risk Validation → Risk Gate → Portfolio Gate → Persistent Portfolio Admission → Execution Ledger → OrderCheck → OrderSendAsync → Broker Acknowledgement → OnTradeTransaction → Position Observation → Reconciliation → Outcome/Accuracy Telemetry`

Any failed gate is fail-closed. No best-effort order placement.

## Phase A — Security, copy boundary, broker capability, freshness, risk

### Gate A1 — Subscriber/payment authorization
- Payment verification must be provider-authenticated and reconciled.
- Payment notification alone never grants copy access.
- Entitlement must be active at the time of copy authorization.
- Explicit copy authorization is mandatory.
- Copy keys are subscriber-specific and revocable.

### Gate A2 — Signal freshness
- Five-minute hard stale rejection is the XAUUSD baseline.
- Freshness is evaluated from signal age against an instrument policy.
- A stale signal is rejected, never silently refreshed or executed.

### Gate A3 — Risk
- User selects requested risk within the published interface.
- System validates the requested risk against the authoritative maximum.
- An invalid request is rejected; it is never silently clamped.

### Gate A4 — Portfolio
- Portfolio admission is authoritative and persistent.
- A caller-provided `portfolio_admitted=true` is not trusted as proof.
- The execution boundary re-verifies admission immediately before broker submission.

### Gate A5 — Broker capability
The implementation target is exactly ten broker capabilities:
1. Exness
2. Pepperstone
3. HFM
4. IC Markets
5. XM
6. IG
7. OANDA
8. AvaTrade
9. FXTM
10. FP Markets

`Pepperdine` is a compatibility alias for `Pepperstone`, not an additional broker.

**Status:** core Phase-A infrastructure is present in the current repository. Production activation remains configuration/test dependent.

## Phase B — API route decomposition

Target route boundaries:
- `api/signals.py`
- `api/trades.py`
- `api/outcomes.py`
- `api/webhook.py`
- `api/admin.py`

The existing `telegram-bridge/app/routes.py` remains the compatibility surface until the decomposed routes have equivalent tests and are wired into the application. No route is deleted merely for architectural cleanliness.

**Gate:** old and new route behavior must be equivalent for authentication, idempotency, validation, status codes, persistence, and Telegram side effects.

**Status:** decomposition is not yet certified complete; keep the compatibility route intact during migration.

## Phase C — Application-service decomposition

Business workflows must move behind explicit services without changing external contracts. Minimum service boundaries:
- signal ingestion / lifecycle
- trade-event ingestion
- outcome recording
- subscription/entitlement
- copy authorization
- payment reconciliation
- calibration/config promotion
- execution admission

Routes become adapters. Services own orchestration. Domain rules remain testable without HTTP.

**Status:** service-level modules already exist in several areas (`copy_trading`, `subscriptions`, `payment_webhook`, `calibration`, `execution_validation`). Consolidation and dependency-direction checks are still required before declaring Phase C complete.

## Phase D — Domain-model decomposition

The monolithic bridge model surface must be decomposed into cohesive model modules while preserving database table names and migration compatibility. Candidate boundaries are:
- signals
- trades
- outcomes
- subscribers/entitlements
- payments
- calibration/configuration
- operational settings/audit

Rules:
- no destructive migration during decomposition;
- preserve existing table names and enum values;
- add compatibility imports where necessary;
- migrations must remain linear and reversible in intent;
- tests must cover serialization, persistence, and route/service integration.

**Status:** the current repository still has a consolidated `telegram-bridge/app/models.py`; Phase D is therefore **not complete**.

## Promotion rule

A phase is complete only when:

1. implementation exists;
2. tests cover the changed behavior;
3. CI is green;
4. no trading-decision behavior was changed unintentionally;
5. backward compatibility is demonstrated;
6. the corresponding diff is reviewable.

Green CI alone does not certify a phase.

## Current baseline

- Main branch: clean migrated repository.
- Latest verified pipeline: GitLab pipeline 24 — passed.
- MQL5 structural validation, Python tests, Telegram bridge tests, and tools tests are covered by CI.
- GitHub reference URL was requested for comparison, but the web fetch of the supplied repository URL is currently unavailable. Therefore GitHub-to-GitLab equivalence is **not** certified by this document.

## Safety boundary

Do not modify strategy scoring, signal generation, confidence calculation, risk sizing, or execution behavior merely to perform the Phase B-D structural refactor. Architectural changes must preserve behavior first; behavioral improvements require a separate validated change.
