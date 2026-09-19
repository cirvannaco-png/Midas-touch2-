# MIDAS TOUCH — Cross-Provider Sync Runbook

## Operating mode

GitHub `main` is the automatic transport origin for source changes. A successful push to GitHub `main` triggers the **Midas Touch - GitHub to GitLab Sync** workflow, which applies the source-tree delta to GitLab project `86337573` on GitLab `main`.

This does not make GitHub the authority for application policy or production promotion; it defines the transport path only.

Current rules:

- GitHub `main` → GitLab `main) is automatic through GitHub Actions.
- GitHub Actions never force-pushes or rewrites GitLab history.
- Provider-specific control files are intentionally excluded from source synchronization: `.github/**` and GitLab's root `.gitlab-ci.yml`.
- The sync workflow verifies that GitLab `main` exists after the write and then verifies source-tree content parity.
- GitHub and the active GitLab repository may use different Git object formats. Cross-provider SHA equality is therefore not the parity criterion; file/tree content parity is.
- Any sync failure is a failed workflow and must be investigated before a release is considered synchronized.

## Required GitHub secret

Create one GitHub Actions repository secret:

`GITLAB_SYNC_TOKEN`

The token must have permission to write repository content in GitLab project `86337573` (`midas-touch2`). Do not commit tokens, credential files, or URLs containing credentials.

## Automatic synchronization procedure

1. A change is merged or pushed to GitHub `main`.
2. GitHub Actions starts **Midas Touch - GitHub to GitLab Sync**.
3. The workflow computes the GitHub source delta and applies it to GitLab `main`.
4. The workflow verifies the GitLab branch.
5. The workflow downloads the GitLab `main` archive and compares SHA-256 file hashes against the GitHub source tree, excluding only `.github/**` and `.gitlab-ci.yml`.
6. The workflow is green only when the write succeeds and the content-parity check passes.

## Development-branch controller

`scripts/midas-sync-controller.sh` remains a separate fail-closed utility for controlled development branches. It deliberately refuses to mutate `main` or `production` and stops on GitLab-ahead or divergent refs.

Approved development namespaces are:

`feature/*`, `fix/*`, `audit/*`, `chore/*`, `ops/*`, `integration/*`, and `sync-test/*`.

## Release refs

Synchronization is not production promotion. Production still moves through the explicit release process and remains subject to branch protection, validation, MetaEditor/MQL5 compilation, broker/demo testing, and forward-test evidence.

## Credential and failure policy

Never bypass a failed sync by force-pushing or manually overwriting GitLab history. A failed parity check means the providers are not synchronized and must be reconciled through the normal controlled repository process.
