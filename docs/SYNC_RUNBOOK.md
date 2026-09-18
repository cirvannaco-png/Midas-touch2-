# MIDAS TOUCH — Cross-Provider Sync Runbook

## Operating mode

GitHub is the **manual transport origin** for ordinary development branches when we need one controlled change to appear on GitLab. This does not make GitHub the authority for policy or releases.

Current rules:

- `main` and `production` are release-boundary refs and are never modified by the mirror workflow.
- Ordinary branches may be mirrored GitHub → GitLab only when GitLab is equal to or strictly behind GitHub.
- Divergence is a hard STOP.
- A GitLab-ahead branch is a hard STOP; this workflow does not perform reverse sync.
- No force-push, automatic merge, "ours/theirs", or conflict resolution is permitted.
- GitLab CI remains paused. The mirror workflow is manual (`workflow_dispatch`) rather than push-triggered.

## GitHub secret required

Create one GitHub Actions repository secret:

`MIDAS_GITLAB_TOKEN`

The token must be allowed to push to the active GitLab repository:

`midas-touch-group1/midas-touchsync`

Do not commit tokens, URLs containing tokens, or credential files to the repository.

## Manual mirror procedure

1. Push or merge your development work onto the desired GitHub branch.
2. Open **Actions → Midas — Manual GitHub to GitLab Mirror**.
3. Enter the exact branch name.
4. Run once with **dry_run = true**.
5. Confirm the output says either:
   - refs are identical, or
   - GitLab is strictly behind and a fast-forward is proposed.
6. Run again with **dry_run = false** to perform the fast-forward.
7. Verify the same branch tip on GitHub and GitLab.
8. For any STOP condition, resolve through a PR/MR and rerun the verification.

## Release refs

Do not use this workflow for:

- `main`
- `production`

Those refs must move through the promotion workflow and exact-commit release procedure.

## Future automation

Once branch protection and credential ownership are fully confirmed, this workflow can be promoted from manual execution to a narrowly scoped event-driven mirror. Do not add a blanket `push` trigger while CI minutes are constrained.
