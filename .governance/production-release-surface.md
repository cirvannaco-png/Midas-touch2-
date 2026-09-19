# GitLab Production Release Surface

## Purpose
The `production` branch is the controlled Midas Touch release surface.

## Current topology
- Development/validation: GitHub `cirvannaco-png/Midas-touch2-`
- Canonical GitLab repository: `midas-touch-group1/midas-touch2`
- Current GitLab development branch: `main`
- Release surface: GitLab `production`
- Runtime service documented by the production surface: `medis-touch-telegram`

## Promotion controls

1. No direct trading-logic development occurs on `production`.
2. Release candidates originate from validated development states.
3. Cross-provider synchronization uses a dedicated non-release branch before any release promotion.
4. Synchronization identity is based on tree/content parity rather than provider-specific commit object format.
5. Production promotion is represented by an explicit GitLab merge request.
6. The synchronization controller never mutates `main` or `production`.
7. Repository governance does not replace MetaEditor/MQL5 compilation, demo-broker validation, forward testing, or capital-readiness evidence.

## Current release baseline

- GitLab `main`: use the live branch ref; verify the exact commit SHA at release time.
- GitLab `production`: `b5d715bd`
- Production protection: currently not enabled; this remains an external GitLab governance action.
- Automatic GitLab CI: intentionally paused.

## Synchronization evidence

- Test ID: `SYNC-2026-09-18-001`
- GitHub test branch: `sync-test/github-to-gitlab-20260918`
- GitLab test branch: `sync-test/github-to-gitlab-20260918`

## Final validation boundary

Software release status and trading readiness are separate. The remaining empirical gates are authoritative MQL5 compilation, runtime integration/recovery tests, demo-broker validation, long-horizon forward evidence, and production-grade infrastructure validation.
