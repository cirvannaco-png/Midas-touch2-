# MIDAS TOUCH — Repository Operating Model

## Repositories

- Active GitHub: `cirvannaco-png/Midas-touch2-`
- Canonical GitLab: `midas-touch-group1/midas-touch2`
- Historical archive: original SHA-256 `midas-touch2` — immutable reference only.

The GitHub/GitLab active pair uses provider-specific object IDs but is intended to carry the same source tree and branch topology on synchronized development refs.

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

The controller may:
- fetch both providers
- compare branch tips
- report equality
- fast-forward an unprotected branch when one side is strictly ahead
- create a missing unprotected development ref from the GitHub source when explicitly approved

The controller must not:
- force-push protected branches
- merge conflicts automatically
- overwrite a divergent branch
- reverse-sync GitLab back to GitHub
- create webhook loops

The canonical GitLab transport target is `midas-touch-group1/midas-touch2`.

## CI policy

Broad push-triggered CI remains disabled/paused while compute minutes are constrained.

Future validation should be scoped to:
- release validation
- merge/promotion gates
- explicit manual runs
- synchronization integrity checks

Do not reintroduce blanket CI for every branch push.

## Emergency rule

Any uncertainty in ancestry, commit identity, validation evidence, or provider parity is a STOP condition. Preserve the branches and investigate before mutating either provider.
