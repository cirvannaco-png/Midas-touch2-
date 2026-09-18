# Midas Touch — Development / Production Promotion

## Branches

### main
Integration branch. Protected. No direct pushes or force-pushes.

### production
Release branch. Protected. It may only advance to a commit already validated on `main`.

### Working branches
Use:
- `feature/*`
- `fix/*`
- `audit/*`
- `chore/*`
- `governance/*`

## Promotion

1. Create or update a working branch.
2. Synchronize it to both providers.
3. Review on the originating provider.
4. Open the corresponding PR/MR on the other provider.
5. Merge the same reviewed commit lineage into `main`.
6. Wait for the validation gate.
7. Promote the exact validated `main` commit to `production` on both providers.
8. Deploy only from the `production` commit.

## Production rollback

Rollback means returning `production` to the last validated commit.

Never rewrite `main` to perform a rollback.

## Live-trading boundary

`production` is a code-release boundary. Live trading remains separately gated by compile, backtest, demo/forward test, VPS/broker verification and controlled rollout.
