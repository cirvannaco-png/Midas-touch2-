# GitHub Canonical Source and Production Release Surface

## Purpose

GitHub `main` is the canonical source-control branch for Midas Touch. GitHub Actions owns repository CI and the version-controlled production-maintenance schedules. Repository authority, deployment configuration, and proven live-trading readiness are separate claims and must be verified separately.

## Current topology

- Canonical repository: GitHub `cirvannaco-png/Midas-touch2-`, branch `main`.
- CI and production-maintenance workflow definitions: `.github/workflows/`.
- Optional mirror: GitLab `midas-touch-group1/midas-touch2`; it does not govern canonical source or production maintenance.
- GitLab `production` branch and the prior GitLab release-surface procedure are legacy migration artifacts, not an active release authority.
- Runtime: the deployed bridge and MT5/VPS must be verified independently in their respective service/terminal control planes. This source-control migration does not repoint or redeploy those services by itself.

## Promotion controls

1. Develop on a branch and merge to GitHub `main` only through a reviewed pull request with required checks passing.
2. Treat GitHub `main` as the only canonical source tree. Do not make GitLab-only source changes; reconcile the source from GitHub.
3. The GitHub-to-GitLab sync workflow is optional mirror automation. Count a sync as successful only when it reports `SYNC_VERIFIED` for the current GitHub SHA and the resulting GitLab tree is verified.
4. Never use provider-specific commit IDs as cross-provider content identity; verify file/tree parity.
5. Production maintenance runs only through `.github/workflows/production-maintenance.yml`. Do not schedule the same bridge endpoints in GitLab.
6. Production deployment still requires separate review and runtime verification; merging source code is not proof of a healthy deployment.
7. Repository governance does not replace authoritative MetaEditor compilation, MT5 Strategy Tester validation, demo-broker testing, forward testing, or capital-readiness evidence.

## Current release baseline and operational caveats

- Resolve the exact GitHub `main` commit SHA at release time; do not rely on a remembered SHA.
- GitHub branch-protection/ruleset settings have not been independently verified by this document.
- The `production` GitHub Actions environment, its main-branch deployment restriction, and the `BRIDGE_BASE_URL` / `BRIDGE_API_KEY` environment secrets require configuration in GitHub settings. Their presence and values are not verified by repository YAML.
- The last documented GitHub-to-GitLab sync failure was an authentication rejection (`HTTP Basic: Access denied`). Do not claim mirror parity until a later run reports `SYNC_VERIFIED`; repair the GitLab token/username in GitHub Actions settings without exposing credentials.
- The previous GitLab production baseline `b5d715bd` and test ID `SYNC-2026-09-18-001` are historical references only, not the current canonical release baseline.

## Final validation boundary

A green CI run validates only the jobs it actually executed. A successful maintenance cycle requires an `ok` response with a persisted cycle ID and database evidence. EA activation additionally requires valid evidence, lifecycle gates, explicit approval where required, and acknowledgement of the exact approved configuration hash. Live trading readiness requires independent MT5/VPS/broker and forward-performance validation.
