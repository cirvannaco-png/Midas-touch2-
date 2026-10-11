# Midas Touch Release Surface

## Provider topology

- Canonical repository: GitHub `cirvannaco-png/Midas-touch2-`, branch `main`.
- Canonical CI and production-maintenance definitions: GitHub Actions in `.github/workflows/`.
- Optional mirror: GitLab `midas-touch-group1/midas-touch2`, maintained from GitHub when authenticated synchronization succeeds.
- Runtime: Render bridge service and MT5/VPS are separate operational systems. Their actual connected repository, deployed commit, environment configuration, database and health must be checked in their service control planes; this document does not prove them.

The GitLab `main` and `production` refs documented by the previous migration plan are legacy references. They are not the source-of-truth branches for ongoing development or production-maintenance scheduling.

## Release rules

1. Development and review occur on branches; integrate changes into GitHub `main` through a reviewed pull request.
2. Require the applicable GitHub checks to pass before merging. Recheck the current head SHA and checks immediately before a release.
3. GitHub-to-GitLab synchronization is optional mirror maintenance. Verify file/tree parity and the current GitHub SHA; provider-specific commit IDs are not interchangeable.
4. Do not make independent GitLab edits that diverge from GitHub `main`.
5. Do not configure duplicate production-maintenance schedules in GitLab.
6. Deployment changes require separate review and a verified runtime health check; the source-of-truth change does not automatically repoint an existing Render service.
7. Repository release governance does not certify MQL5 compilation, broker execution, forward performance, or live-capital readiness.

## Current state and limitations

- GitHub `main` is canonical; resolve its exact SHA at release time.
- The GitHub Actions maintenance workflow is present in the source tree. Production activation remains unverified until the GitHub `production` environment, main-branch restriction and environment secrets are confirmed in settings and a due workflow run succeeds with persisted evidence.
- Mirror parity is unverified until the latest sync run reports `SYNC_VERIFIED` for the current GitHub commit.
- Previous GitLab branch protection, GitLab `production` SHA `b5d715bd`, and synchronization test `SYNC-2026-09-18-001` are historical records only.
- A green pipeline is not proof of production runtime health or trading readiness.
