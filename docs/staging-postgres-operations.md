# Midas Touch 2 staging Postgres operations

**Status checked:** 2026-10-18 (UTC)  
**Staging database:** `midas-touch2-staging-db`  
**Render resource ID:** `dpg-dbahl7s9v7es738i7m20-a`  
**Region/version:** Frankfurt / PostgreSQL 18  
**Current plan:** Free; expires **2026-11-17 19:14:39 UTC**  
**Network posture:** database IP allowlist is empty (external access blocked).

## Safety boundary

The existing `midas-touch2` Render service follows `main`. Do not change its `DATABASE_URL` to the staging database.

The additive Blueprint file `render.staging.yaml` defines a separate `midas-touch2-staging` service; it sets `autoDeployTrigger: "off"`, points to the existing app code on `main`, and uses the staging DB through a Render `fromDatabase` reference. In Render, create a **new Blueprint** and set its Blueprint file path to `render.staging.yaml`. Do **not** sync this file into the existing production Blueprint. It intentionally omits the production service.

The staged code includes a local preflight script at `scripts/staging_bridge_preflight.sh`; after the staging service is configured, it checks `/health/db`, authenticated `/execution-ledger/health`, and rejection of a request without a key. It is read-only and does not print secrets.

The staging blueprint needs `BOT_TOKEN`, `CHAT_ID`, `ADMIN_CHAT_ID`, `SECRET_KEY`, and `WEBHOOK_SECRET_TOKEN` configured as Render secrets. The bridge registers a Telegram webhook at startup. Supply a dedicated staging bot token and test chat IDs. **Never copy the production bot token into staging**, because registering the staging webhook would replace the production bot webhook.

## Private database networking

Keep the DB `ipAllowList` empty. Render services in the same workspace and region can connect to Postgres using its internal URL; that traffic bypasses the external IP allowlist. The Blueprint's `fromDatabase` binding is the intended way to supply the internal connection string to the staging service. Do not use `0.0.0.0/0` as a workaround.

The hosted Render SQL-query tool runs outside Render's private network. Its failed query is expected with this private-only setting and does not establish whether a same-region Render service can connect. Verify the live connection from the staging service itself through `/health/db`, which uses the app's `DATABASE_URL` to execute `SELECT 1`.

## Expiry and backup policy

This database was provisioned on Free as a **disposable staging database only**. Free Postgres expires 30 days after creation, has a fixed 1 GB allowance, and does not support Render-managed backups or point-in-time recovery. After expiry it becomes inaccessible; there is a 14-day upgrade grace period before deletion. See [Render free-plan limits](https://render.com/docs/free).

**Expiry decision:** use only synthetic/demo test data in this database; no authoritative execution ledger, customer data, production signals, or information that must survive expiry. Review it by **2026-11-10**, and either export/verify and retire it before expiry or arrange a paid retention plan through the Dashboard. The resource's current expiry is **2026-11-17 19:14:39 UTC**.

**Backup decision:** there is no external backup destination or tested restore configured, so do not persist important data here. If staging must retain data, establish a separate encrypted backup target and prove a full restore into a clean database before placing important test evidence there. Keep the encryption key separate from backup artifacts. A checksum, file listing, or `pg_restore --list` is not a restore test.

For durable ledger storage, the safer default is a paid Render Postgres plan with managed recovery enabled. Current Render pricing lists the 256 MB Postgres plan at **$6/month** and 1 GB RAM at **$19/month**; prices can change. On a Hobby workspace, paid database PITR has a three-day window; Pro or higher has seven days. Logical exports are retained for seven days, and Free databases have no Render-created logical exports. See [pricing](https://render.com/pricing) and [backup/recovery docs](https://render.com/docs/postgresql-backups). No paid upgrade has been made.

## Verification gates

- [ ] Create a **new** Render Blueprint with repository `cirvannaco-png/Midas-touch2-`, branch `main`, Blueprint file path `render.staging.yaml`.
- [ ] Configure staging-only bot token, chat IDs, API key, and webhook secret in Render; keep all secrets out of Git.
- [ ] Confirm the staging service's `DATABASE_URL` resolves through the internal `fromDatabase` reference while the database allowlist remains empty.
- [ ] Verify `GET /health/db` returns HTTP 200 with `status=online` and `database=connected`.
- [ ] Run `BRIDGE_BASE_URL=https://<actual-staging-host> BRIDGE_API_KEY=<staging-SECRET_KEY> bash scripts/staging_bridge_preflight.sh` from a trusted environment with network access. It must verify authenticated ledger health (`status=online`, `database=connected`, `execution_ledger=ready`) and verify that the same endpoint rejects a missing key. Do not put the key in shell history or print it; prefer environment-secret injection.
- [ ] Establish an encrypted external backup and perform a real restore test before retaining any non-disposable data.
- [ ] Review staging logs and check health again after staging configuration. Only then consider any separate production change.

## Current blockers (not represented as successful)

The Render tools available in this operator session do not provide the action to create/sync a Blueprint or update/upgrade PostgreSQL and do not provide the host/IP needed to perform a private-only SQL query through the hosted SQL connector. The staging DB therefore remains unconnected and its SQL/health test is still unverified. The GitHub production-maintenance environment also lacks the required `BRIDGE_BASE_URL` and `BRIDGE_API_KEY`; do not run its production preflight until the intended staging values are added in a **staging** GitHub environment. No live staging deployment, secrets change, paid upgrade, backup, or restore test has been performed as part of this preparation.
