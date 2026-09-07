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

- `.gitlab-ci.yml` — native GitLab CI/CD replacement for:
  - MQL5 structural validation
  - `medis_touch` lint/security/tests
  - Telegram bridge lint/security/dependency/tests
  - tools tests
  - daily subscription maintenance
  - biweekly recalibration maintenance
  - manual Render secret synchronization

## Scheduled jobs

Create two GitLab pipeline schedules:

1. **Daily subscription sweep**
   - Cron: `0 7 * * *`
   - CI/CD variable: `SCHEDULE_TASK=daily-subscriptions`

2. **Biweekly recalibration**
   - Cron: `0 6 * * 6`
   - CI/CD variable: `SCHEDULE_TASK=biweekly-recalibration`

The recalibration job preserves the existing Saturday-parity behavior anchored to `2026-01-03`.

## Required protected/masked GitLab CI/CD variables

For scheduled maintenance:

- `BRIDGE_BASE_URL`
- `BRIDGE_API_KEY`

For the optional Render secret-sync job:

- `RENDER_API_KEY`
- `RENDER_SERVICE_ID`
- `BOT_TOKEN`
- `CHAT_ID`
- `ADMIN_CHAT_ID`
- `SECRET_KEY`
- optional `WEBHOOK_SECRET_TOKEN`

These values must be stored in GitLab CI/CD variables, never committed.

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
