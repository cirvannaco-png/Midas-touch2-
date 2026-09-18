# MIDAS TOUCH — Repository Operating Model

## Repositories

- Active GitHub: `cirvannaco-png/Midas-touch2-`
- Active GitLab engineering/release repository: `midas-touch-group1/midas-touch2` (SHA-256)
- GitLab transport sync repository: `midas-touch-group1/midas-touch2-sync` (SHA-1; transport only, not a release authority)
- Historical archive: original SHA-256 `midas-touch2` — immutable reference only.

GitHub currently uses SHA-1 repository objects. The active GitLab repository currently uses SHA-256 repository objects. Cross-provider parity therefore must never depend on literal SHA equality; it is established by provider-specific commit IDs plus verified source-tree/ref identity and release evidence.

## Authority and safety

Neither provider is an automatic winner when branches diverge.

For ordinary branches:
- Equal tips: no action.
- One side is a strict ancestor of the other: fast-forward the lagging side only when the ref is unprotected.
- Both sides diverged: stop and resolve through a normal PR/MR.
- Never automatically force-push, choose "ours/theirs", or overwrite a divergent branch.

For protected refs (`main`, `production`):
- No automatic force-push.
- No automatic deletion.
- No automatic divergence resolution.
- Changes enter through the promotion workflow.

## Development branches

Use:
- `feature/*` for new capabilities.
- `fix/*` for defects.
- `audit/*` for correctness/security/reliability audits.
- `chore/*` for tooling and maintenance.
- `ops/*` for repository/infrastructure operations.

Every meaningful branch should identify its purpose and be disposable after integration.

## Main

`main` is the integration branch, not the live-trading authorization boundary.

Required path:
`feature/fix/audit → PR/MR → main → validation`

Validation must cover, as applicable:
- MQL5 compilation
- static/audit checks
- backend/EA contract parity
- unit/integration tests
- deterministic backtest
- risk-control invariants
- news lock, spread and volatility constraints
- broker minimum/freeze constraints
- DynamicStopEngine invariants
- recalibration/config version integrity
- audit logging and rollback safety

## Production

`production` is the release boundary.

A production commit must already exist on `main` and have passed the release gates. Promotion must move the exact validated `main` commit; it must not create an unrelated production-only fix.

Production promotion:
`validated main → production → controlled forward test → demo/live rollout`

A production branch is a software-release boundary, not permission to trade real money.

## Synchronization

Cross-provider synchronization must be transport-only, not policy-changing.

The current manual GitHub → GitLab transport workflow targets the dedicated SHA-1 `midas-touch2-sync` repository because the active GitLab engineering repository uses SHA-256. The sync repository is a transport staging surface only; it must never be treated as the production/release source or as a substitute for the active GitLab engineering repository.

The controller may:
- fetch both providers
- compare branch tips
- report equality
- fast-forward an unprotected branch when one side is strictly ahead

The controller must not:
- force-push protected branches
- merge conflicts automatically
- overwrite a branch because one provider is considered authoritative
- auto-resolve divergence
- create webhook loops

## CI policy

Broad push-triggered CI remains disabled/paused while compute minutes are constrained.

Future validation should be scoped to:
- release validation
- merge/promotion gates
- explicit manual runs
- synchronization integrity checks

Do not reintroduce blanket CI for every branch push.

## Current provider-state audit — 2026-09-18

The final pre-protection sweep found these provider-state facts:

- GitHub `main` is currently unprotected.
- GitHub `production` exists but is currently unprotected and is 18 commits behind GitHub `main`.
- GitLab `main` is protected, but the current project settings still allow developers to push and merge directly.
- GitLab `production` does not currently exist in the active SHA-256 engineering repository.
- The dedicated GitLab SHA-1 sync repository exists but is empty at the audit timestamp; it is transport-only.
- GitLab CI is intentionally paused at the repository configuration level to conserve runner minutes.

These are provider configuration facts, not application behavior. Do not treat the production branch as an active cross-provider release boundary until the missing GitLab `production` ref and both providers' protection/release controls are explicitly established and verified.

## Emergency rule

Any uncertainty in ancestry, commit identity, validation evidence, or provider parity is a STOP condition. Preserve the branches and investigate before mutating either provider.
