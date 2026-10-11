# Medis Touch Phase A-D Implementation Status

This document is a release gate, not a claim that a phase is complete merely because files exist.

## Phase A — Security, copy boundary, broker capabilities, freshness, risk

**Status: implemented / under continued audit**

Required invariants:

- fail-closed execution ordering
- explicit copy authorization
- paid subscription and entitlement checks
- persistent portfolio admission verification
- supported broker capability boundary
- stale-signal protection
- user-risk validation against the system maximum
- no broker credentials in the Telegram bridge
- execution/latency and outcome telemetry boundaries

The canonical execution order remains documented in `AGENTS.md` and `app/services/architecture.py`.

## Phase B — API route decomposition

**Status: staged, not complete**

Target route boundaries:

- `api/signals.py`
- `api/trades.py`
- `api/outcomes.py`
- `api/webhook.py`
- `api/admin.py`

`app/routes.py` remains the compatibility surface until each endpoint is extracted with regression coverage. No broad rewrite is permitted.

## Phase C — Application-service extraction

**Status: in progress**

Established seams include:

- `app/services/architecture.py`
- `app/services/copy_authorization.py`
- `app/services/payment_integrity.py`
- `app/services/execution_guard.py`

The copy authorization service is fail-closed and preserves the existing 401/403 semantics. Further extraction must preserve route behavior and must be incremental.

## Phase D — Persistence model decomposition

**Status: compatibility foundation established; decomposition not yet complete**

`app.models` remains the canonical compatibility import surface. The current SQLAlchemy metadata and model names are protected by regression tests in `tests/test_phase_cd_boundaries.py`.

The eventual decomposition must preserve:

- `Base.metadata`
- table names
- column names
- PostgreSQL enum names
- `PG_ENUM(create_type=False)` behavior
- all existing `from app.models import ...` imports
- Alembic/database compatibility

No model definitions should be moved until their import and migration dependencies are mapped.

## Deployment and source-control track — GitHub + Render/VPS

GitHub `cirvannaco-png/Midas-touch2-` on `main` is the canonical source tree and GitHub Actions is the canonical CI and production-maintenance system. GitLab is an optional one-way source-tree mirror. The migration does not itself repoint or redeploy any Render service; verify the provider, deployed commit, database and health in the service control plane.

The VPS is the persistent MT5/EA execution layer. A VPS deployment is not considered live until MT5, EA health, backend authentication, broker connectivity, recovery, and reconciliation are externally verified.

## Merge gate

A phase may be promoted only after:

1. dependency inspection
2. invariant statement
3. minimal change
4. targeted regression tests
5. Applicable GitHub Actions checks passing on the exact candidate commit (GitLab mirror CI is secondary).
6. diff/source-drift review
7. deployment verification where applicable

MQL5 trading behavior is protected from refactoring unless explicitly authorized by a separate change request.
