# MIDAS TOUCH — Repository Operating Model

## Repositories and authority

- **Canonical source:** GitHub `cirvannaco-png/Midas-touch2-`, branch `main`.
- **Canonical automation:** GitHub Actions in `.github/workflows/` for CI, guarded production maintenance, and optional mirror sync.
- **Optional mirror:** GitLab `midas-touch-group1/midas-touch2`, project ID `86337573`. Its source tree is subordinate to GitHub `main`.
- **Legacy sync artifact:** `midas-touch-group1/midas-touch2-sync` and its prior manual transport runbook belonged to an earlier operating model; they are not the destination of the current direct source-tree mirror.
- **Runtime:** Render bridge/backend, PostgreSQL, VPS, MT5 and broker environments are separate operational surfaces. Their actual connected repository, deployed commit, secrets, database and health must be checked in the respective control planes.

GitHub and the active GitLab project may use different Git object formats. Never compare cross-provider commit hashes as though they were interchangeable; mirror parity is a source-tree/content question.

## Source, CI and mirror policy

GitHub `main` is the source of truth for development and reviewed integration.

For code changes:
- Use a scoped branch and pull request.
- Run targeted tests and applicable GitHub Actions checks against the exact candidate commit.
- Do not merge merely because a file exists or an earlier commit was green.
- If checks are not run or are skipped, report that explicitly and treat validation as a pre-merge requirement.
- Do not change MQL5 trading behavior under a documentation, repository or CI migration.

The GitHub-to-GitLab workflow is a one-way mirror operation, not a second release process. It may synchronize GitHub `main` to GitLab `main` after successful CI or via intentional dispatch from GitHub `main`. It must not be run from a feature branch against GitLab `main`. Do not make GitLab-only changes, reverse-sync GitLab to GitHub, force-push, or automatically resolve divergent histories.

The source mirror excludes provider-specific `.github/` configuration. A mirror is current only when its workflow reports `SYNC_VERIFIED` for the exact GitHub source SHA and the resulting GitLab tree is verified. A clone/authentication failure or any unverified state means mirror parity is unknown.

## Main and release boundary

GitHub `main` is the integration branch, not the live-trading authorization boundary. The prior GitLab `production` branch procedure is legacy and is not an active source-of-truth release mechanism.

A source merge does not automatically authorize production deployment. Verify the actual hosting provider/repository/commit, required environment settings and secrets, database/migrations, application health, signal/outcome ingestion, and rollback path before any deployment change. Do not repoint or duplicate Render services as a side effect of source-control work.

## Production-maintenance workflow

GitHub Actions workflow `.github/workflows/production-maintenance.yml` owns:
- alternate-Saturday recalibration checks at 06:00 UTC, with its documented parity guard;
- daily subscription enforcement at 07:00 UTC;
- explicit manual dispatch from GitHub `main` only.

It uses the GitHub Actions `production` environment and requires only the `BRIDGE_API_KEY` environment secret; the non-secret canonical service URL is configured in workflow YAML. The environment's main-branch deployment restriction and secret configuration must be verified in GitHub settings. Remove old GitLab schedules separately; repository YAML alone cannot delete settings already stored in GitLab.

A successful scheduler run must prove a persisted cycle ID, not just an HTTP 2xx. A cycle does not itself demonstrate candidate approval, EA hash acknowledgement, profitable backtesting or live-trading readiness.

## Trading-system safeguards

Preserve the canonical fail-closed order:

`SIGNAL -> Freshness/Stale Protection -> Eligibility -> Paid Subscription -> Entitlement -> Explicit Copy Authorization -> Broker Capability/Symbol Mapping -> User Risk Validation -> Risk Gate -> Portfolio Gate -> Persistent Portfolio Admission -> Execution Ledger -> OrderCheck -> OrderSendAsync -> Broker Acknowledgement -> OnTradeTransaction -> Position Observation -> Reconciliation -> Outcome/Accuracy Telemetry`

Never use repository/CI success as a substitute for authoritative MetaEditor compilation, genuine MT5 Strategy Tester results with realistic costs and locked-OOS validation, controlled demo forward testing, restart recovery, broker reconciliation, and explicit configuration-hash acknowledgement.

## Historical provider-state audit — 2026-09-18

The following facts are a historical snapshot from 2026-09-18, not verified current settings:

- GitHub `main` was reported as unprotected at that audit.
- GitHub `production` was reported as unprotected and behind `main`.
- GitLab `main` was reported as protected, with direct push/merge permissions still possible for developers.
- GitLab `production` was reported as absent in the active SHA-256 engineering repository.
- The dedicated GitLab SHA-1 sync repository was reported empty.
- GitLab CI was described as paused at that time.

Verify live branch-protection/ruleset, environment, and token settings directly before relying on them; this historical record is not evidence of their current state.

## Emergency rule

Any uncertainty in commit identity, source-tree parity, validation evidence, deployment state or provider configuration is a STOP condition. Preserve current branches and runtime state, investigate, and make a reviewed change rather than guessing.
