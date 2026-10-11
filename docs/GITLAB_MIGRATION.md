# GitLab Migration and Recovery Audit

## Purpose

This repository was reconstructed from the supplied Medis Touch recovery ZIP after GitHub access became unavailable. The migration is intentionally limited to repository/CI/deployment hygiene.

**Trading logic was not changed.**

## Recovery source

Authoritative source used:

- `medis_touch_repo/` from `medis_touch_repo_with_copytrading_payments.zip`

The two nested ZIP archives under `attached_assets/` were not selected as the source of truth. They contain older/smaller snapshots, including an older `MedisTouch_v2.8.mq5`. They are excluded from the clean repository so the repository does not contain ambiguous duplicate implementations.

## Removed from the clean repository

- `.github/` — all GitHub Actions and Dependabot configuration.
- `.replit` — unrelated hosted-development artifact.
- `attached_assets/` — nested recovery ZIPs; retained only in the original recovery archive.
- `LICENSE.md` — stale/contradictory license text referring to Nakima and a hosted GitHub App; the root `LICENSE` is retained as the repository license.
- `docs/medis-touch-ci-fix.md` — historical GitHub Actions-specific CI note that is no longer applicable.

## Added

- `.gitlab-ci.yml` — migration-era GitLab pipeline definition for repository checks. Production maintenance jobs are now disabled there; GitHub Actions is canonical for validation and production schedules.

## Production maintenance scheduler

GitHub Actions on GitHub main is the only production maintenance scheduler. The workflow is .github/workflows/production-maintenance.yml.

1. **Biweekly recalibration check**
   - Cron: 0 6 * * 6 (weekly workflow tick, Saturday 06:00 UTC)
   - Runs the actual cycle only on alternate Saturdays using the UTC parity anchor 2026-01-03.
2. **Daily subscription sweep**
   - Cron: 0 7 * * * (daily at 07:00 UTC)

GitLab is an optional source-tree mirror, not the production control plane. The mirrored .gitlab-ci.yml rejects scheduled pipelines and disables the maintenance jobs to prevent duplicate requests. Delete/disable any old GitLab schedules; do not add new schedules there.

## Required GitHub Actions repository secrets

In GitHub, create an environment named production under Settings → Environments and restrict deployments to the main branch. Add these environment secrets:

- BRIDGE_BASE_URL: the actual HTTPS base URL for the deployed bridge service (no trailing slash required).
- BRIDGE_API_KEY: the same secret value as the deployed bridge's SECRET_KEY setting.

These secrets must not be committed or exposed in logs/chat. The scheduled workflow uses the production environment, restricts manual dispatch jobs to main, validates HTTPS, applies bounded network timeouts, avoids automatic POST retries, and validates response JSON. To manually execute a production job, use Actions → Midas Touch Production Maintenance → Run workflow on main and choose the intended task. Manual recalibration immediately calls the production bridge; do not use it as a casual dry run.

GITLAB_SYNC_TOKEN and optional GITLAB_SYNC_USER are separate credentials used only by the optional GitHub-to-GitLab mirror workflow. They are not used for production maintenance.

## Validation performed on the supplied recovery copy

- Python bytecode compilation: passed for all Python sources.
- MQL5 include-tree validator: passed:
  - 61 MQL5 source files
  - 2 entry points
  - 188 includes resolved
  - no missing/case-mismatched includes
  - no empty/broken headers
  - no compiled binaries
- `medis_touch` test suite: **25 passed**.
- Telegram bridge test collection could not be fully executed in this environment because `aiosqlite` is not installed and outbound package installation is unavailable here. The repository's pinned requirements include `aiosqlite`; GitLab CI will install the declared dependency before running the suite.
- Tools test collection is coupled to the Telegram bridge's runtime dependencies and therefore was not treated as passing locally without those dependencies.

## Important recovery limitation

The supplied ZIP contains source files but no `.git` directory. Therefore this clean repository preserves the recovered source tree, not the original Git commit history, branches, tags, signed commits, issues, or pull requests.

If GitHub access is restored later, history can be evaluated separately. Do not attempt to bypass GitHub account controls.

## Security finding

No live credential was identified in the scanned source tree. Placeholder/test credentials exist in examples and CI test environments, which is expected.

Before the first GitLab push, independently rotate any credential that may ever have been exposed outside the repository:

- Telegram bot token
- Render API key
- Render service/API secrets
- broker/API credentials
- payment-provider credentials
- bridge API key

## Trading-logic boundary

No `.mq5` or `.mqh` trading implementation was edited as part of this migration. Changes are confined to:

- repository hygiene
- CI/CD configuration
- documentation/comments that described GitHub-specific automation
- removal of obsolete platform artifacts

The EA source remains the recovered source of truth.

## Scheduling status and activation gate

The scheduler is implemented in GitHub Actions on the canonical GitHub main branch; schedule definitions are version-controlled in .github/workflows/production-maintenance.yml. Secret values are not defined by YAML and must be set as GitHub Actions environment secrets in the production environment, restricted to the main branch.

Before calling the production engine autonomously active, confirm:

1. BRIDGE_BASE_URL points to the actual deployed bridge and uses HTTPS.
2. BRIDGE_API_KEY matches the deployed bridge's SECRET_KEY; the workflow never logs this value.
3. GitHub Actions shows the maintenance workflow enabled on the default branch, with both cron schedules present.
4. The latest due recalibration run returned status "ok" and a non-empty cycle_id; a no_data response is not a completed persisted cycle.
5. A CalibrationCycle record and registered-challenger evaluation can be verified in the production database/logs. Promotions remain gated and may require explicit Telegram approval.
6. Backtest-based candidates were built from genuine MT5 Tester reports/data, passed the chronological walk-forward and locked-OOS gates, and were submitted through tools/submit_tester_evidence.py. Scheduled recalibration does not run MT5 Strategy Tester and does not fabricate backtest evidence.
7. The EA has separately acknowledged the exact approved configuration hash. A cycle or a VALIDATED evidence record is not proof of live EA activation or profitable forward performance.

The GitLab mirror's maintenance jobs are disabled in repository CI configuration. Any legacy GitLab project schedules should also be deleted/disabled. Do not interpret a GitLab pipeline's status as evidence that the GitHub production scheduler ran.

If GitHub Actions secrets are not yet configured, the workflow can exist and pass repository CI while production maintenance remains unactivated. Treat activation as unverified until a due run and its persisted evidence are observed.

## GitHub-to-GitLab source-of-truth synchronization

GitHub `main` is the canonical source tree. The GitHub Actions workflow `.github/workflows/github-to-gitlab-sync.yml` reconciles the GitLab `main` source tree only after the GitHub CI workflow succeeds. Do not treat GitLab as synchronized unless the job reports `SYNC_VERIFIED` for the current GitHub commit and the GitLab main tree is verified.

Required GitHub Actions repository secrets/configuration:

- `GITLAB_SYNC_TOKEN`: an unexpired GitLab token with `write_repository` scope and access to project `86337573`.
- `GITLAB_SYNC_USER`: for a personal access token, the workflow may use `oauth2`; for a project/group access token or deploy token, set the exact GitLab token username required by that token type.

**Current operational blocker (2026-10-11):** the GitHub-to-GitLab sync workflow failed during GitLab clone with `HTTP Basic: Access denied`. The secret is present but GitLab rejected the credentials. This usually means an expired/incorrect token, insufficient scope/project access, or a token-type/username mismatch. The workflow cannot repair or inspect secret values itself. Rotate/recreate the token in GitLab, update the GitHub Actions secret(s), then rerun the sync workflow and verify the resulting GitLab commit and file parity. Never paste the token into code, logs, or this conversation.

A successful GitHub CI run alone is not proof that the GitLab mirror was updated. The latest GitHub main includes EA version 2.81 and the operator panel; the observed GitLab main EA source was still version 2.80 when checked, so source-tree parity remains unconfirmed until the authenticated sync succeeds.
