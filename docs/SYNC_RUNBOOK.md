# MIDAS TOUCH — GitHub-to-GitLab Mirror Runbook

## Authority and operating mode

GitHub `cirvannaco-png/Midas-touch2-`, branch `main`, is the canonical source tree. GitHub Actions owns CI and the production-maintenance workflow. GitLab `midas-touch-group1/midas-touch2` (project ID `86337573`) is an optional one-way source-tree mirror only.

The current automation is `.github/workflows/github-to-gitlab-sync.yml`. It can run after the `Midas Touch CI` workflow succeeds on `main`, or by intentional manual dispatch from `main`. It mirrors files from the selected GitHub `main` source to GitLab `main`, excluding provider-specific `.github/` and GitLab's own `.git/` directory. It does not promote the GitLab `production` branch or deploy Render.

Rules:

- Do not make GitLab-only source edits and do not treat GitLab `main` or `production` as release authority.
- Never dispatch the sync workflow from a non-`main` branch; the workflow guard must reject that request.
- GitHub SHA-1 and GitLab SHA-256 commit IDs are not directly comparable. Verify source-tree parity and use the sync workflow's verified result for the exact GitHub source SHA.
- Do not configure production-maintenance schedules or production bridge secrets in GitLab. `.gitlab-ci.yml` admits push/MR validation only and disables the duplicate maintenance jobs.
- No force-push, automatic merge, or conflict resolution is permitted as part of source mirroring.
- A successful sync verifies the mirror tree only. It is not a deployment, release, MT5 compile/backtest, or live-trading readiness signal.

## Required GitHub Actions secrets

In GitHub repository settings, configure:

- `GITLAB_SYNC_TOKEN`: an unexpired GitLab token with `write_repository` scope and access to project `86337573`.
- `GITLAB_SYNC_USER`: optional for personal access tokens (the workflow defaults to `oauth2`); required with the exact username when using token types that do not accept `oauth2`.

The token must not be committed, printed, or pasted into chat. The workflow reports authentication/clone failure without exposing the token. If GitLab returns `HTTP Basic: Access denied`, verify expiry, scope, project membership and token-type/username pairing, then update the GitHub Actions secret through GitHub settings.

## Normal operation

1. Merge reviewed changes to GitHub `main` only after the applicable GitHub Actions checks pass.
2. Let the source-sync workflow run after successful `Midas Touch CI`, or manually dispatch it from the GitHub `main` ref when a deliberate retry is needed.
3. Inspect the run's result. A write operation must report `SYNC_VERIFIED` with the expected source SHA and the verified GitLab commit. If no change is needed, the workflow must report `SYNC_VERIFIED` with the same tree-parity meaning.
4. If the workflow fails, do not claim the mirror is current. Inspect sanitized job diagnostics, repair credentials in GitHub settings if required, and retry only after the cause is understood.
5. Do not modify the GitLab `production` ref as part of this mirror workflow.

## Legacy sync artifacts

The earlier manual transport workflow and dedicated `midas-touch2-sync` SHA-1 staging repository belonged to a previous cross-provider operating model. They are not the target of the current canonical source-sync workflow and must not be used as the active release source without a separate, reviewed architecture change.

## Production-maintenance separation

Production maintenance is owned by `.github/workflows/production-maintenance.yml` and requires the GitHub `production` environment plus environment secrets `BRIDGE_BASE_URL` and `BRIDGE_API_KEY`. Disable any old GitLab project schedules separately in GitLab settings. Never treat sync success as evidence that a calibration cycle ran or that an EA configuration was approved or activated.
