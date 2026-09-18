# Midas Touch — Dual-Repository Synchronization Protocol

## Active repositories

- GitHub: `cirvannaco-png/Midas-touch2-`
- GitLab: `midas-touch-group1/Midas-touchsync`
- Historical archive: original `midas-touch2` (SHA-256; never rewritten)

The active GitHub/GitLab pair uses the same SHA-1 history. A fast-forward synchronization therefore preserves identical commit IDs.

## Branch authority

Both providers are development surfaces. No provider is the permanent owner of a feature branch.

### Protected boundaries

`main` and `production` are protected.

Automation must never:
- force-push them;
- merge divergent histories;
- overwrite one provider's protected ref with another provider's ref;
- silently choose "ours" or "theirs".

### Synchronizable branches

Feature, fix, audit and governance branches may synchronize in either direction.

## Synchronization algorithm

For every branch:

1. Fetch both providers.
2. Equal tips: do nothing.
3. Branch exists on one provider only:
   - Create it on the other provider if it is not protected.
4. One tip is an ancestor of the other:
   - Fast-forward the lagging provider if the branch is not protected.
5. Protected branch is ahead on one side:
   - Stop and raise a promotion alert. Use a PR/MR.
6. Histories diverge:
   - Stop. Create a conflict-resolution branch and reconcile through normal Git review.

## Why this prevents loops

A synchronized fast-forward creates the same commit SHA on both providers. The next run sees equal tips and performs no operation.

No polling loop can manufacture a new commit merely because it synchronized an existing commit.

## Production workflow

`feature/*` / `fix/*` / `audit/*`
→ review
→ `main`
→ validation
→ `production`
→ controlled deployment

## Trading-system validation gate

Before production promotion:

- MQL5 compilation passes.
- Backend/EA contract parity passes.
- Unit and integration tests pass.
- Static/audit checks pass.
- Backtest is reproducible and recorded.
- RiskGuard, news lock, spread/volatility filters and broker constraints pass.
- DynamicStopEngine invariants pass.
- Recalibration/config changes are versioned and auditable.
- Controlled demo/forward test is completed.
- Live rollout is explicitly authorized.

Repository promotion is not itself permission to place live trades.

## CI policy

The GitLab project currently has a top-level `workflow: rules: - when: never`, so repository pushes do not launch normal pipelines.

GitHub currently has no workflow directory in `main`.

Synchronization automation should use one lightweight GitHub scheduled workflow after the GitLab access token is installed as a repository secret. The workflow only runs the controller above; it does not run the trading test suite.

