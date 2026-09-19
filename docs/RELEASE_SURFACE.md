# Midas Touch Production Release Surface

## Provider topology

- GitHub development repository: `cirvannaco-png/Midas-touch2-`
- Canonical GitLab repository: `midas-touch-group1/midas-touch2`
- GitLab development branch: `main`
- GitLab release branch: `production`
- Render runtime source currently documented as GitLab `main`; deployment changes must remain separately verified.

## Release rules

1. Development and validation occur on non-release branches.
2. Cross-provider synchronization is validated on dedicated non-release branches first.
3. GitHub SHA-1 and GitLab SHA-256 object IDs are not used as cross-provider identity.
4. File/tree/content parity is the synchronization invariant.
5. `main` and `production` are never updated by the synchronization controller.
6. `production` moves only through an explicit GitLab release workflow.
7. Repository release governance does not certify MQL5 compilation, broker execution, forward performance, or live-capital readiness.
8. Render runtime state must be verified independently before a release cutover.

## Current state

- GitLab `main`: use the live branch ref; verify the exact commit SHA at release time.
- GitLab `production`: `b5d715bd`
- Main protection: verified
- Production protection: not yet verified as enabled
- Sync controller: present and fail-closed
- Automatic GitLab CI: intentionally paused to conserve minutes
- Production promotion: intentionally gated pending validation
- Controlled synchronization test: `SYNC-2026-09-18-001`
