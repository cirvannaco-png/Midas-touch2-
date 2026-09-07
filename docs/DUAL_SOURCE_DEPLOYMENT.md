# Medis Touch Dual-Source Deployment Standard

## Objective

Medis Touch supports both the existing GitHub-backed Render deployment and a new GitLab-backed Render deployment. The GitLab path is additive; it does not replace or repoint the existing GitHub services during validation.

## Source paths

```text
                    +--> GitHub -> existing Render services
                    |
Medis Touch source -+
                    |
                    +--> GitLab -> new Render service
                    |
                    +--> VPS -> MT5 / Medis Touch EA
```

## Rules

1. GitLab is the canonical repository for the migrated source and CI validation.
2. Existing GitHub-backed Render services remain untouched until the GitLab deployment is independently healthy.
3. Do not create a second production database merely because a second Render service is created.
4. Production data, subscriptions, entitlements, payments, signal state, and execution state must have one explicitly authoritative persistence boundary.
5. The GitLab Render service must be connected to the private GitLab repository through Render's GitLab integration or an approved container-registry path.
6. Docker configuration must remain aligned with the repository's existing `telegram-bridge/Dockerfile` unless a separately reviewed deployment change is approved.
7. Render deployment must not contain broker credentials or payment secrets in source control.
8. GitLab CI must pass before enabling an automated production deployment path.
9. The VPS is the MT5 execution runtime and must authenticate to the backend through the approved secure signal path.
10. GitHub fallback and GitLab deployment must never independently process the same production execution event in a way that can create duplicate broker orders.

## GitLab -> Render onboarding

Render supports GitLab as a connected Git provider. For a private GitLab project, the Render account must be authorized against the project with the required GitLab permissions. The Render service should then be configured against the intended branch and Dockerfile path.

The first GitLab-backed deployment is a validation environment until health checks, database connectivity, Telegram integration, entitlement checks, copy authorization, signal ingestion, and EA/VPS connectivity are proven.

## Promotion sequence

`GitLab CI green -> Render GitLab service healthy -> database/migrations verified -> API health verified -> Telegram/payment verification -> signal ingestion -> copy authorization -> VPS/EA connectivity -> broker execution test -> reconciliation -> production promotion`

No step should be skipped merely because an earlier GitHub-backed service is already running.
