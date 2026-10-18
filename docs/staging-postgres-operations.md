# Midas Touch 2 staging Postgres operations

**Status checked:** 2026-10-18 (UTC)  
**Staging database:** `midas-touch2-staging-db`  
**Render resource ID:** `dpg-dbahl7s9v7es738i7m20-a`  
**Region/version:** Frankfurt / PostgreSQL 18  
**Current plan:** Free; expires **2026-11-17 19:14:39 UTC**  
**Network posture:** database IP allowlist is empty (external access blocked).

## Safety boundary

The existing `midas-touch2` Render service follows `main`. Do not change its `DATABASE_URL` to the staging database. The `render.yaml` on branch `ops/staging-private-db-20261018` describes a separate `midas-touch2-staging` service, and has `autoDeployTrigger: off`. Do not merge that branch's staging-only `render.yaml` into `main`: it intentionally does not describe the production service.

The staging blueprint injects `DATABASE_URL` via Render's `fromDatabase` reference. This selects the internal connection string for a same-workspace, same-region Render service. Keep the database IP allowlist empty; do not use `0.0.0.0/0` to make a remote SQL client work.

The service's startup registers a Telegram webhook. Supply a dedicated staging bot token and test chat IDs. **Never copy the production bot token into staging**, because registering the staging webhook would replace the production bot webhook.

## Expiry and data policy

This database was provisioned as a free staging database. Free Postgres expires 30 days after creation and has no Render-managed backup or point-in-time recovery. Treat its contents as disposable test data only. Do not put production records, credentials, or authoritative trading/execution-ledger records in it.

Before using it for any data that must survive a reset or expiry, choose and validate one of these routes:

1. **Preferred for durable ledger storage:** upgrade/provision a paid database and enable managed recovery. Render's current documented paid recovery window for a Hobby workspace is three days; logical exports are separately retained for seven days. A PITR restore creates a separate database that can be inspected before switching services.
2. **If keeping Free:** establish an independent encrypted export destination first. Run `pg_dump` from a same-region Render-side job using the internal connection string, store the encrypted archive outside Render, keep its decryption key separately, and test restoring into an isolated empty database. A checksum or successful `pg_restore --list` is not a substitute for a real restore test.

At the time of this check, no external backup destination or validated restore procedure is configured. Consequently, no persistent data should be written to this Free database until that gate is met.

## Verification gates

- [ ] Apply this staging blueprint as a separate Render Blueprint, not as a sync/update to the production service.
- [ ] Configure the required staging secrets in Render; keep secrets out of Git. Use a staging-only Telegram bot.
- [ ] Confirm the staging service resolves the database's internal URL and that the DB allowlist remains empty.
- [ ] Verify `GET /health/db` returns HTTP 200 with `status=online` and `database=connected`. This route runs a live SQL `SELECT 1`; it does not authenticate callers.
- [ ] Verify `GET /execution-ledger/health` using the staging `X-API-Key` returns HTTP 200 and `status=online`, `database=connected`, `execution_ledger=ready`; verify the same route without a key is rejected.
- [ ] Create an encrypted backup and perform a real restore test before retaining any non-disposable data.
- [ ] Check authenticated bridge and database health again after staging configuration, then review the evidence before considering a production change.

## Current access limitation

The hosted Render SQL-query tool runs outside Render's private network. With this database's external IP allowlist empty, its SQL attempt is correctly rejected. This is not a reason to open public database access: use the Render-internal `fromDatabase` URL from the staging service for the live SQL test. This operator session does not expose a Blueprint-sync action or a database IP-allowlist update action, and the GitHub production-maintenance environment is missing `BRIDGE_BASE_URL` and `BRIDGE_API_KEY`; those limitations prevent claiming live staging SQL, authenticated-ledger, or restore verification at present.
