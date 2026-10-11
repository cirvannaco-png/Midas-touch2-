# Midas Touch Canonical Source and Deployment Standard

## Objective

GitHub `main` is the single canonical source tree. GitLab is an optional mirror, not a second development or production authority. Repository synchronization must not be confused with deployment: this policy change does not repoint, create, or redeploy Render services.

## Current topology

```text
GitHub main (canonical source)
  ├── GitHub Actions CI and production-maintenance workflow
  ├── optional authenticated source-tree mirror ──► GitLab main
  └── existing runtime (verify actual provider/commit in Render settings)
          └── authenticated bridge/API ──► PostgreSQL
                       ▲
                       │ authenticated signal/outcome path
                  VPS / Windows
                       └── MT5 Terminal ── EA ── Broker
```

The diagram describes intended control boundaries, not proof that any hosted service is currently connected, healthy, or executing live trades.

## Rules

1. GitHub `main` is canonical for source, review, CI and production-maintenance workflow definitions.
2. GitLab is an optional mirror only. Its contents are not considered current unless a sync run reports `SYNC_VERIFIED` for the current GitHub source and parity is independently checked.
3. Existing Render services must not be deleted, repointed, duplicated, or migrated on the basis of documentation changes alone. Verify the connected provider, deployed commit, health checks, environment and database directly.
4. Do not create a second production database merely because another service or environment is being tested.
5. Production data, subscriptions, entitlements, payments, signal state, and execution state must have one explicitly authoritative persistence boundary.
6. No production-maintenance endpoints should be scheduled simultaneously from GitHub and GitLab. GitHub Actions is canonical; GitLab maintenance jobs are disabled in `.gitlab-ci.yml`. Remove any pre-existing GitLab project schedules separately in its UI.
7. Docker configuration must remain aligned with `telegram-bridge/Dockerfile` unless a separately reviewed deployment change is approved.
8. Runtime secrets must remain in the appropriate service/CI secret store, never in source control or logs.
9. The VPS is the MT5 execution runtime and must authenticate to the backend through the approved secure signal path.
10. The deployment must never create two active bridge runtimes that independently process the same production execution event or produce duplicate broker orders.

## Deployment change procedure

For any deliberate runtime-provider change, open a separate reviewed change and verify the actual Render/VPS configuration. The release sequence is:

`GitHub PR reviewed -> relevant GitHub CI green -> deployment source/commit confirmed -> database and migrations verified -> API health and authentication verified -> Telegram/payment/entitlement smoke tests -> signal/outcome ingestion verified -> VPS/EA connectivity -> demo-broker execution test -> reconciliation -> separately approved production cutover`

Do not infer a deployment provider from repository configuration alone. Do not use GitLab as an alternate active production path without a separate explicit migration decision and duplicate-processing safeguards.
