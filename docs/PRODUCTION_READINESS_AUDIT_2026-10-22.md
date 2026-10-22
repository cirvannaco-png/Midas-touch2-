# Production Readiness Audit — 2026-10-22

## Decision

**Do not enable live trading yet.** This audit found source-level risks that can be improved in code, but it also found external configuration and runtime evidence blockers that cannot be honestly marked complete from repository inspection alone.

## Source-level changes proposed on this branch

- Default EA account profile changed to the small-account profile.
- Default small-account limits are 0.5% risk per trade, one open position, 1.5% daily-loss limit, 5% hard drawdown limit, and 0.5% portfolio open-risk cap.
- A shared hard ceiling rejects per-trade risk above 2% in both profile validation and the lot-sizing engine. A 30% setting must fail closed, not silently become a tradable configuration.
- Minimum-lot override remains disabled; the sizing engine already rejects a broker minimum lot when it exceeds the configured risk budget. At KSh 1,500, 0.5% is KSh 7.50 of planned stop risk. Gold may therefore legitimately produce a sizing rejection depending on Exness symbol contract size, minimum volume, stop distance, and account currency.
- Production health-check workflow now reads its bridge hostname from the same `BRIDGE_BASE_URL` secret used by production maintenance rather than pinning a hard-coded Render hostname.
- These code changes are on a review branch and must pass MetaEditor compile and CI before merging. They have not been deployed to MT5 or Render.

## Verified blockers

### 1. Production maintenance credentials are absent

GitHub Actions run [39609252572](https://github.com/cirvannaco-png/Midas-touch2-/actions/runs/39609252572) failed in “Validate production bridge secrets” because both `BRIDGE_BASE_URL` and `BRIDGE_API_KEY` were empty. Preflight and maintenance work were skipped. Add these as GitHub Actions secrets in the repository's production environment; do not commit them to source control or echo their values in logs.

### 2. Current health check does not reach the expected endpoint

GitHub Actions run [39722904583](https://github.com/cirvannaco-png/Midas-touch2-/actions/runs/39722904583) timed out after 10 seconds with curl error 28, zero response bytes, and HTTP 000 against the hard-coded `midas-touch2.onrender.com` hostname. The revised workflow will require `BRIDGE_BASE_URL`; the secret must point to the actual intended service and the service must answer.

### 3. Render service and production database configuration are not aligned

Render account inspection reported:
- Existing web service: `medis-touch-telegram`, service ID `srv-dalcvcrm8hqs73953gi0`, URL `https://medis-touch-telegram-zqsk.onrender.com`, Oregon region, GitLab source mirror.
- Root `render.yaml` describes a `midas-touch2` service in Frankfurt, with the GitHub repository as source and `/health/db` as health check.
- Production database: `midas-touch2-production-db`, ID `dpg-dbbrkm0u01pc738q6qm0-a`, Frankfurt region, Free plan, status reported available, expiry date November 19, 2026.
- Database IP allowlist is empty. The external read-only SQL probe was blocked by that allowlist. Do **not** solve this by opening the database to `0.0.0.0/0`. Verify the service's actual `DATABASE_URL`, region, migrations, and internal network access from the intended Render service. Services using Render's internal database address should be co-located in the same region.
- The Free database's expiration must be resolved or the service risks data loss.

The active service's hidden environment values were not readable here, so this audit does not claim that its runtime database URL or secrets are correct.

### 4. The exact main-branch EA build was not proven compiled during this audit

The latest successful MetaEditor compile located in the available run history was for a research branch and a different source SHA, not the current main source. The PR for these changes must show the native Windows MetaEditor compile job passing (0 compile errors and the expected EX5 artifact). Static include-tree validation alone is not an MQL5 compile.

### 5. Strategy profitability is not established

Earlier StrategyTune runs used independent $10,000 periods, IC Markets data, and omitted a fully matched Exness commission/slippage/swap model. The candidate lowered losses versus its baseline in the combined samples but was still net negative across the independent periods. The 87% win-rate target did not hold consistently, and 600% return has not been demonstrated. Risk controls and trailing stops can manage exposure; they cannot create predictive edge by themselves.

## Required release gates

1. Merge only after MetaEditor compile, MQL5 policy tests, bridge tests, PostgreSQL migration smoke tests, research tests, and security/dependency checks pass.
2. Add the correct `BRIDGE_BASE_URL` and `BRIDGE_API_KEY` secrets in GitHub's production environment.
3. Align the intended Render service and production DB in one region, apply migrations, and prove `/health/db` returns `status=online` and `database=connected`.
4. Prove authenticated `/execution-ledger/health` returns `status=online`, `database=connected`, and `execution_ledger=ready`.
5. Compile the exact EA source in MetaEditor; attach it to Exness demo first; verify accepted orders, fills, partial exits, trailing-stop modifications, commission/swaps, realized P&L, ledger parity, emergency-stop persistence, and restart recovery.
6. Run chronological, cost-inclusive backtests and untouched out-of-sample validation. Promote an entry/exit profile only when net expectancy is positive after realistic costs and drawdown criteria pass.

A failed gate should block live entries rather than be bypassed. “No blockers” can only be declared after the external configuration and runtime checks above actually pass.
