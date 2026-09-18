# MIDAS TOUCH — Cross-Provider Sync Runbook

## Operating mode

GitHub is the **manual transport origin** for ordinary development branches when one controlled GitHub change must appear on GitLab. This does not make GitHub the authority for policy or releases.

Current rules:

- `main` and `production` are never mutated by the mirror controller.
- Approved development namespaces are `feature/*`, `fix/*`, `audit/*`, `chore/*`, `ops/*`, `integration/*`, and `sync-test/*`.
- Ordinary branches may be mirrored GitHub → GitLab only when GitLab is equal to or strictly behind GitHub.
- Divergence is a hard STOP.
- A GitLab-ahead branch is a hard STOP; this workflow does not perform reverse sync.
- No force-push, automatic merge, "ours/theirs", or conflict resolution is permitted.
- GitLab CI remains paused.
- The mirror workflow is manual (`workflow_dispatch`) rather than push-triggered, so routine development does not consume CI minutes automatically.

## Required GitHub secret

Create one GitHub Actions repository secret:

`MIDAS_GITLAB_TOKEN`

The token must be allowed to push to:

`midas-touch-group1/midas-touchsync`

Do not commit tokens, credential files, or URLs containing credentials.

## Manual mirror procedure

1. Push or merge development work onto the desired GitHub branch.
2. Open **Actions → Midas — Manual GitHub to GitLab Mirror**.
3. Enter the exact branch name.
4. Run once with **dry_run = true**.
5. Confirm the controller reports either:
   - refs are identical,
   - GitLab is strictly behind and a fast-forward is available, or
   - a new GitLab ref would be created from the GitHub commit.
6. Run again with **dry_run = false** to perform the allowed fast-forward/create operation.
7. Verify the branch tips on both providers.
8. For any STOP condition, resolve through the normal PR/MR workflow and rerun verification.

The underlying `scripts/midas-sync-controller.sh` is fail-closed: missing provider state, unsupported refs, GitLab-ahead state, and divergence do not return success.

## Release refs

Do not use the mirror workflow for:

- `main`
- `production`

Those refs move only through the promotion workflow and exact-commit release procedure.

## Future automation

Once branch protection, ownership, credentials, and release controls are fully confirmed, this workflow may be promoted to a narrowly scoped event-driven mirror. Do not add blanket `push` triggers while CI minutes are constrained.

