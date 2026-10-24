# Midas Touch 2 — source of truth, release identity, and operational risks

**Audit snapshot:** 24 October 2026  
**Decision:** GitHub `main` is the sole production source branch. Live-trading readiness remains blocked.

## Canonical ownership

- **Product name:** Midas Touch 2. Use “Midas Touch 2” in current UI, deployment, and operational documentation. “Medis Touch” remains only in legacy filenames, historic material, and compatibility identifiers; do not create new projects under that name.
- **Canonical repository:** [`cirvannaco-png/Midas-touch2-`](https://github.com/cirvannaco-png/Midas-touch2-), branch `main`.
- **Canonical EA source:** `EA/`. **Canonical service source:** `telegram-bridge/`. **Canonical Render blueprint:** root `render.yaml`.
- **`mql5/`** is a legacy terminal-layout placeholder; do not develop a second EA there.
- **`medis_touch/`** is a non-production handbook/reference implementation. It is not the deployed EA or bridge.
- **GitLab:** secondary mirror/research workspace, not an independent production source. The GitLab project `midas-touch-group1/midas-touch2` has its own history; the separate `midas-touch-group1/midas-touch2-sync` project contains a single synchronization-test commit and is not the product's source history. Do not use that test project's commit count as evidence that the canonical repository lacks history.

## Version contract

- The packaged source version is **2.81**, held in root `VERSION` and repeated in both MQL5 `#property version` declarations.
- `EA/MedisTouch_v2.8.mq5` and `EA/MedisTouch_Indicator_v2.8.mq5` keep their legacy filenames because the MT5 staging tool and installation paths reference them. The suffix `v2.8` is not the package version.
- Changelog headings such as `v2.21`/ `v2.20` are historical feature-milestone labels; they are not proof of an independently compiled package release.
- A compiled artifact is identified by **package version + canonical Git commit SHA + compiler result + artifact checksum**. A source edit or a green static include check alone is not a compiled release.
- The version-contract test under `tools/tests/` must remain in CI so these declarations cannot silently drift.

## Deployment truth

The root `render.yaml` describes the canonical GitHub-backed `midas-touch2` service in Frankfurt. The connected Render accounts also show a separate GitLab-backed `medis-touch-telegram` service in Oregon. They are two live services, not one service with a harmless metadata discrepancy.

Treat the Frankfurt GitHub-backed service as canonical based on the repository's stated deployment contract. Treat the Oregon GitLab-backed service as a **legacy duplicate pending explicit retirement**. Do not edit, delete, suspend, or redirect it implicitly as part of a code-only change: first verify its traffic, secrets, database URL, webhook consumers, and latest deploy. Avoid running both as independent production schedulers or pointing both at the same writable state until duplicate execution has been ruled out.

## Database deadline and network policy

Render currently reports `midas-touch2-production-db` as an available **Free** PostgreSQL instance in Frankfurt, with expiry **21 November 2026** and an empty IP allowlist. Empty allowlist means the external SQL probe may be blocked; it does not prove that the database is empty or broken.

Required actions before the deadline:
1. Take and verify a restorable backup/export immediately.
2. Choose a persistent paid plan or a replacement PostgreSQL provider, confirm its cost, and provision/migrate before expiry.
3. Verify the target bridge's effective `DATABASE_URL`, region, migrations, row counts/checksums, write/read round trips, and execution-ledger health without printing secrets.
4. Test restore into a separate database and reconcile signal/outcome/ledger totals before changing production traffic.

**Do not open PostgreSQL to `0.0.0.0/0` as a shortcut.** Prefer the intended service's internal database URL and least-privilege network access. The Render connector used here exposes no safe one-call operation to create/verify a complete backup-and-restore workflow, and provisioning a paid replacement creates a billable commitment; neither should be claimed done without the corresponding evidence.

## Account sizing and trading evidence

At KSh 1,500:
- 0.5% planned stop risk = **KSh 7.50**.
- 1% = KSh 15.00; 2% = KSh 30.00; 20% = KSh 300.00.

The sizer must use the broker's symbol contract/tick values, tick size, volume step/minimum, account currency, and stop distance. It must reject any trade where the broker minimum volume exceeds the configured stop-risk budget. Never force a minimum lot or widen risk merely to produce a trade count. A KSh 1,500 account may be too small to validate XAUUSD live at the current minimum volume and reasonable stop distance; use Strategy Tester and demo for validation instead.

There is currently **no established positive net expectancy after realistic costs**. A win-rate target of 87% and a 600% return target remain aspirational and unvalidated. Promotion requires same-data baseline/candidate comparison with spread, commission, slippage and applicable swaps; chronological walk-forward folds; a locked untouched out-of-sample period; drawdown and trade-count reporting; exact EA build parity; and Exness demo ledger reconciliation. Do not promote the diagnostic confidence model based only on an in-sample score.

## Change-control rule

Every production-affecting change must:
1. be made on a review branch and pull request;
2. pass unit/regression tests and the required native MetaEditor compile;
3. include deployment/configuration impact analysis;
4. have observable evidence and a rollback path; and
5. remain blocked from live trading until all external runtime and performance gates pass.
