# Midas Touch 2 — Branch Accounting Audit

**Snapshot date:** 2026-10-22 (UTC)  
**Repository:** [`cirvannaco-png/Midas-touch2-`](https://github.com/cirvannaco-png/Midas-touch2-)  
**Main SHA at snapshot:** `726be44a5c6706b72102f6d2e788b33930900b3d`

## Executive reconciliation

- **158 branch refs** enumerated across all pages; **151 distinct head SHAs**.
- **158 protected branches** and **0 unprotected branches** in the snapshot.
- **14 open PRs** at snapshot; open PRs were drafts, and all are explicitly listed below in the branch table.
- **2 duplicate-head groups** mean some branch names refer to identical commits rather than distinct candidate changes.
- The purpose of the inventory is to account for all refs, **not** to assert all refs are safe to integrate. Protected benchmark and sync-test refs, stale branches, and unfinished trading/research changes are preserved rather than force-merged.
- Two migration refs have no common ancestor with `main` and cannot be treated as ordinary feature branches: `migration/medis-touch-complete` and `migration/medis-touch-source`.

## Duplicate branch heads

- `940e01b12f06854c462a9b34cc7f96f8520f76b8`: `audit/pre-protection-hardening`, `ci/github-actions-validation`, `ci/production-lifecycle-e2e`, `fix/outcometracker-addsetup-signature`, `fix/production-readiness-health-gate`, `integration/production-hardening`, `integration/production-hardening-v2`
- `3dff554a8fd80a97a8b4d90f8b7b8d6679fb9f2e`: `benchmark/baseline-3dff554`, `benchmark/baseline-principal-20260920`

## Known conflict/supersession paths

- PR #108 (MTF gate) was closed unmerged after conflict; the current-main port was integrated as PR #121.
- PR #29 (SMC structural validator) was closed unmerged after conflict; the current-main port was integrated as PR #124.
- PR #113 (production health workflow) was closed unmerged after conflict; the clean current-main replacement was integrated as PR #131.
- PR #31 (symmetric FVG invalidation) was closed unmerged after its focused current-main port, PR #132, passed all seven reported checks and merged.
- PR #117 (separate staging blueprint and read-only staging preflight) merged as `54554a4baf752220646971be931b84df2df0c00d`. It does not switch production to staging or constitute live Render validation.
- PR #132 (symmetric FVG invalidation) merged as `726be44a5c6706b72102f6d2e788b33930900b3d`.

## Merge/validation blockers still open

- **Production health:** the health workflow failed before probing the endpoint because the GitHub Actions production-environment secret `BRIDGE_API_KEY` was empty. Live production database readiness is therefore **unverified**, not failed due to application code.
- **GitLab mirror:** GitLab rejected the sync credential with HTTP Basic access denied. The token must be valid, have `write_repository` and project access; set `GITLAB_SYNC_USER` to the matching GitLab token username if the token type is not a personal access token.
- **Paid production PostgreSQL PR #118:** intentionally left draft. Its requested Render plan is paid and provisioning reported HTTP 402 billing required.
- Remaining research and trading-policy PRs stay drafts pending current-main integration validation and domain-specific evidence. A green source-level test run is not proof of profitable live behavior.

## Complete branch register

| Branch | Head SHA (12) | Protected | Associated pull request(s) | Disposition |
|---|---|---|---|---|
| `audit/complete-architecture-20260925` | `1e669b86c1b5` | Yes | [#24 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/24) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `audit/fix-outcometracker-compiler-parity` | `351922bc3761` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |
| `audit/midas-touch-deep-hardening-20260925` | `ca8569e14c33` | Yes | [#23 closed](https://github.com/cirvannaco-png/Midas-touch2-/pull/23) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `audit/midas-touch-final-hardening-20260925` | `88d0920cbc19` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |
| `audit/performance-targets-and-promotion-gates-20261013` | `9959fcc6b25e` | Yes | [#85 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/85) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `audit/pre-protection-hardening` | `940e01b12f06` | Yes | [#5 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/5) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `bench/render-before-after` | `1613f040e868` | Yes | [#15 closed](https://github.com/cirvannaco-png/Midas-touch2-/pull/15) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `benchmark/baseline-3dff554` | `3dff554a8fd8` | Yes | — | HOLD — benchmark baseline/reference ref; not a production integration candidate. |
| `benchmark/baseline-principal-20260920` | `3dff554a8fd8` | Yes | — | HOLD — benchmark baseline/reference ref; not a production integration candidate. |
| `chore/execute-mql5-policy-tests-20261014` | `36d5d8602447` | Yes | [#96 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/96) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `chore/production-health-mt5-evidence-20261014` | `6d7fc2b44583` | Yes | [#103 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/103) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `chore/retain-native-policy-test-evidence-20261014` | `4689ed15c3ac` | Yes | [#102 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/102) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `chore/verify-runtime-ledger-auth-20261014` | `6eae5194b2de` | Yes | [#104 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/104) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `ci/compileall-post-merge-20260926` | `1214da15d414` | Yes | [#28 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/28) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `ci/fix-green-sync-contract` | `ce2116153910` | Yes | [#7 closed](https://github.com/cirvannaco-png/Midas-touch2-/pull/7) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `ci/github-actions-validation` | `940e01b12f06` | Yes | [#4 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/4) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `ci/gitlab-api-pipeline-source-20261014` | `bfe40e67a08d` | Yes | [#107 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/107) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `ci/latency-percentiles` | `960deece5c70` | Yes | [#12 closed](https://github.com/cirvannaco-png/Midas-touch2-/pull/12) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `ci/latency-percentiles-main` | `ac89545db3cd` | Yes | [#14 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/14) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `ci/metatrader5-compile-20261011` | `f42c0c4ecda4` | Yes | [#44 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/44) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `ci/production-lifecycle-e2e` | `940e01b12f06` | Yes | — | SHARED HEAD — same commit as audit/pre-protection-hardening, ci/github-actions-validation, fix/outcometracker-addsetup-signature, fix/production-readiness-health-gate, integration/production-hardening, integration/production-hardening-v2; no independent change to merge. |
| `ci/verify-full-midas-ci` | `d56799c3df47` | Yes | [#13 closed](https://github.com/cirvannaco-png/Midas-touch2-/pull/13) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `docs/github-source-of-truth-20261011` | `3a010561f67b` | Yes | [#48 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/48) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `docs/post-audit-remediation-status-20261013` | `56bdc636f5df` | Yes | [#92 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/92) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `feat/actual-mt5-tester-validation-20261014` | `ffd152173817` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |
| `feat/chart-control-panel-trailing-audit-20261011` | `f0c736926d2b` | Yes | [#43 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/43) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `feat/durable-execution-ledger-integration` | `1cbe40c6189d` | Yes | [#81 open draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/81) | OPEN DRAFT — assessed but not merged; see PR description/release gates. Protected source branch retained. |
| `feat/ea-config-structural-trailing` | `aa4f55ca4b65` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |
| `feat/mtf-structure-alignment-rebased-20261014` | `f9d2b4fdfaf4` | Yes | [#108 closed](https://github.com/cirvannaco-png/Midas-touch2-/pull/108) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `feat/reconciliation-and-matched-validation-20261014` | `53a8ecad1336` | Yes | [#94 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/94) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `feat/separate-prop-firm-and-micro-account-profiles` | `652008c2add5` | Yes | [#82 open draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/82) | OPEN DRAFT — assessed but not merged; see PR description/release gates. Protected source branch retained. |
| `feature/architecture-governor` | `87ca6d384004` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |
| `feature/dynamic-stop-engine` | `f0c826636042` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |
| `feature/fvg-invalidation-fix-research` | `9fa04e3cb867` | Yes | [#31 closed draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/31) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `feature/high-probability-multi-trade` | `cc461cab0fa3` | Yes | [#16 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/16) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `feature/midas-decision-architecture` | `f8c8b99b67a9` | Yes | [#34 open draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/34) | OPEN DRAFT — assessed but not merged; see PR description/release gates. Protected source branch retained. |
| `feature/mss-fvg-auction-confluence` | `ec3b8f80349f` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |
| `feature/mtf-structure-alignment` | `33d4cb8b89dc` | Yes | [#95 closed draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/95) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `feature/order-flow-confirmation-engine` | `306f5c2eed72` | Yes | [#112 open draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/112) | OPEN DRAFT — assessed but not merged; see PR description/release gates. Protected source branch retained. |
| `feature/peer-strategy-routing` | `177a27253715` | Yes | — | UNREVIEWED DIVERGED REF — no associated PR in the snapshot; do not merge blind. Needs a fresh PR and current-main validation. |
| `feature/phase-a-d-hardening` | `c0ec10040db5` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |
| `feature/production-hardening` | `fe58eb2bd01c` | Yes | — | UNREVIEWED DIVERGED REF — no associated PR in the snapshot; do not merge blind. Needs a fresh PR and current-main validation. |
| `feature/smc-causal-fvg-loss-reduction` | `a63acfa4a29d` | Yes | [#30 open draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/30) | OPEN DRAFT — assessed but not merged; see PR description/release gates. Protected source branch retained. |
| `feature/smc-structural-validator` | `bddf29798acc` | Yes | [#29 closed](https://github.com/cirvannaco-png/Midas-touch2-/pull/29) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `feature/top-down-mtf-dd-risk` | `7a7eda9a96e2` | Yes | [#109 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/109) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `feature/volume-profile-intelligence` | `f438fa729f70` | Yes | [#27 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/27) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/account-risk-profile-ledger-normalization-20261014` | `26c4d70c5b00` | Yes | [#98 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/98) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/accounting-fill-ledger-reconciliation` | `5c94275052b9` | Yes | [#53 closed draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/53) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `fix/authoritative-fill-ledger-main` | `d05bcb5bccbd` | Yes | [#58 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/58) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/authoritative-position-identity-20261012` | `dcb23d1dd86d` | Yes | [#70 open draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/70) | OPEN DRAFT — assessed but not merged; see PR description/release gates. Protected source branch retained. |
| `fix/authoritative-strategy-setup-lineage-20261009` | `a5bea662ceb4` | Yes | [#37 closed draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/37) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `fix/backtest-evidence-variable-spread-20261012` | `2c6ba67b4696` | Yes | [#72 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/72) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/ci-nonblocking-gitlab-sync-20260919` | `73fc2581f05b` | Yes | [#9 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/9) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/ci-production-audit-20260919` | `bca662b0b6ef` | Yes | [#8 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/8) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/codex-audit-main-20260925` | `14cc41d5855a` | Yes | [#25 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/25) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/configure-risk-profile-guard-20261014` | `31368a1dc287` | Yes | [#99 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/99) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/dao-research-cost-model-callsite` | `3215bef1d652` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |
| `fix/dynamic-stop-no-market-sl-20261014` | `ef188c189faf` | Yes | [#106 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/106) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/dynamic-stop-reject-market-price-20261014` | `ac803ce48d61` | Yes | [#105 closed](https://github.com/cirvannaco-png/Midas-touch2-/pull/105) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `fix/dynamic-stop-test-api-20261014` | `684794c1fa46` | Yes | [#100 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/100) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/ea-deal-event-idempotency` | `fc28fe5b626b` | Yes | [#55 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/55) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/emergency-stop-durable-latch-20261018` | `4addd6c00f5e` | Yes | [#114 closed draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/114) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `fix/enable-recalibration-schedule-20261010` | `9bbf40da0821` | Yes | [#40 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/40) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/evidence-deduplication` | `86a5fa53767a` | Yes | [#21 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/21) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/gitlab-ci-secret-and-import-path-20261011` | `f3da4bb52c86` | Yes | [#42 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/42) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/gitlab-ruff-recovery-test-parity` | `07dec3f5e2a8` | Yes | [#56 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/56) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/gitlab-sync-token-auth-20261009` | `8f313396f4fb` | Yes | [#39 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/39) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/history-identity-parser-20261012` | `868423c8bbdb` | Yes | [#75 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/75) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/main-ci-remove-external-sync-gate-20260919` | `1e6bfdcd59d3` | Yes | [#10 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/10) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/midas-architecture-hardening-20260923` | `da739e488cd1` | Yes | [#19 closed](https://github.com/cirvannaco-png/Midas-touch2-/pull/19) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `fix/midas-touch-main-ci-readme-20260925` | `c31084ad15bd` | Yes | [#26 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/26) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/min-volume-risk-guard` | `3f5658be6e6b` | Yes | [#54 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/54) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/mirror-prune-stale-github-workflows` | `9cdd34286dac` | Yes | [#110 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/110) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/mt5-package-layout` | `708282e3c9e2` | Yes | [#18 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/18) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/multi-fill-vwap-outcome-accounting-20261012` | `f49b93364faf` | Yes | [#73 open draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/73) | OPEN DRAFT — assessed but not merged; see PR description/release gates. Protected source branch retained. |
| `fix/multi-trade-architecture-audit` | `cd7da0a1c34f` | Yes | [#20 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/20) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/multifill-outcome-accounting-20261012` | `35e1e006a226` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |
| `fix/multifill-outcome-accounting-v2-20261012` | `f3a297a4bb46` | Yes | [#77 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/77) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/normalize-protective-prices-to-tick-20261014` | `2c40d6fcc643` | Yes | [#101 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/101) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/order-manager-volume-boundary-20261012` | `61258ae2ff58` | Yes | [#66 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/66) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/outcome-completeness-ci-20261012` | `ba215fb4717a` | Yes | [#74 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/74) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/outcome-provenance-accounting` | `871a7d574de2` | Yes | [#49 closed draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/49) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `fix/outcome-provenance-main` | `2d34bf366e33` | Yes | [#60 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/60) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/outcometracker-addsetup-signature` | `940e01b12f06` | Yes | — | SHARED HEAD — same commit as audit/pre-protection-hardening, ci/github-actions-validation, ci/production-lifecycle-e2e, fix/production-readiness-health-gate, integration/production-hardening, integration/production-hardening-v2; no independent change to merge. |
| `fix/partial-close-volume-guard-20261013` | `18577683b730` | Yes | [#88 closed draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/88) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `fix/partial-exit-independent-of-trailing-20261013` | `190b85440afe` | Yes | [#93 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/93) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/payoff-asymmetry-precision-gates-2026-10-12` | `afdc6c60995a` | Yes | [#76 open draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/76) | OPEN DRAFT — assessed but not merged; see PR description/release gates. Protected source branch retained. |
| `fix/portfolio-pending-order-risk-20261013` | `f688ef84d7cf` | Yes | [#91 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/91) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/position-ticket-identifier-parity-20261012` | `ab3e786d9a60` | Yes | [#67 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/67) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/production-correctness` | `2b195e782ac5` | Yes | — | UNREVIEWED DIVERGED REF — no associated PR in the snapshot; do not merge blind. Needs a fresh PR and current-main validation. |
| `fix/production-health-authenticated-preflight-20261018` | `9ab381736bf8` | Yes | [#113 closed draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/113) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `fix/production-readiness-health-gate` | `940e01b12f06` | Yes | [#6 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/6) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/qualified-closed-trade-target-20261013` | `966b3a25ceb3` | Yes | [#89 closed draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/89) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `fix/qualified-trade-and-partial-close-guards-20261013` | `75c8496e24ff` | Yes | [#90 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/90) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/recovery-identity-parser-20261012` | `7e8da8e704af` | Yes | [#65 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/65) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/remove-hardcoded-return-target-20261013` | `23edbf765d43` | Yes | [#87 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/87) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/remove-unused-recovery-placeholders` | `a24d8ce87408` | Yes | [#63 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/63) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/restore-production-postgres-infrastructure` | `1f5ea83c76d7` | Yes | [#118 open draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/118) | OPEN DRAFT — assessed but not merged; see PR description/release gates. Protected source branch retained. |
| `fix/risk-atr-cap-fail-closed-20261012` | `e6b2ccbb087d` | Yes | [#68 closed draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/68) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `fix/risk-atr-cap-fail-closed-mainline-20261012` | `6c0fb4808ed3` | Yes | [#69 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/69) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/robust-gitlab-tree-sync` | `e9d94c5f2763` | Yes | [#17 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/17) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/sqlite-outbox-test-isolation-20261013` | `3c8f8e92ce17` | Yes | [#78 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/78) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/static-recovery-candidate-query` | `f97c2bdc4686` | Yes | [#61 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/61) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `fix/static-sql-recovery-query` | `6a68a156a298` | Yes | [#57 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/57) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `governance/sync-automation` | `49fc352cf7a9` | Yes | — | UNREVIEWED DIVERGED REF — no associated PR in the snapshot; do not merge blind. Needs a fresh PR and current-main validation. |
| `hardening/production-recovery-reconciliation` | `8a95a550015c` | Yes | [#50 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/50) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `hardening/small-account-risk-and-production-preflight` | `30787acceac9` | Yes | [#120 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/120) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `integration/authoritative-setup-boundary-20261022` | `583cce11863a` | Yes | [#129 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/129) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `integration/fvg-invalidation-fix-20261022` | `e6b587bea5fc` | Yes | [#132 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/132) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `integration/mt5-diagnostic-evidence-20261022` | `3c0890ca8d20` | Yes | [#130 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/130) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `integration/production-hardening` | `940e01b12f06` | Yes | — | SHARED HEAD — same commit as audit/pre-protection-hardening, ci/github-actions-validation, ci/production-lifecycle-e2e, fix/outcometracker-addsetup-signature, fix/production-readiness-health-gate, integration/production-hardening-v2; no independent change to merge. |
| `integration/production-hardening-v2` | `940e01b12f06` | Yes | — | SHARED HEAD — same commit as audit/pre-protection-hardening, ci/github-actions-validation, ci/production-lifecycle-e2e, fix/outcometracker-addsetup-signature, fix/production-readiness-health-gate, integration/production-hardening; no independent change to merge. |
| `integration/production-health-authenticated-preflight-20261022` | `56d05d1915b6` | Yes | [#131 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/131) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `main` | `726be44a5c67` | Yes | — | AUTHORITATIVE — current default branch. |
| `merge/dao-wider-stops-research-20261022` | `fe6576f860cc` | Yes | [#123 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/123) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `merge/emergency-stop-latch-20261022` | `a2d3acf00131` | Yes | [#122 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/122) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `merge/lona-report-consistency-audit-20261022` | `f490611ab74b` | Yes | [#125 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/125) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `merge/mt5-tester-deal-evidence-20261022` | `557c1d5b0b63` | Yes | [#126 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/126) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `merge/research-evidence-toolkit-20261022` | `baf746fbfa80` | Yes | [#127 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/127) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `merge/resolve-mtf-structure-alignment-20261022` | `f1df39941bf8` | Yes | [#121 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/121) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `merge/smc-structural-diagnostics-20261022` | `99744af738cf` | Yes | [#124 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/124) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `migration/compatibility-on-recovery-candidate` | `286e838bf019` | Yes | [#52 closed draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/52) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `migration/compatibility-schema-main` | `0ef6062aeda1` | Yes | [#59 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/59) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `migration/medis-research-validation-guidelines` | `c30e4f24c488` | Yes | [#47 closed draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/47) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `migration/medis-touch-complete` | `1debaa445c00` | Yes | — | HOLD — no common ancestor with main; preserve original history and selectively migrate only after a dedicated audit. |
| `migration/medis-touch-source` | `a8982611fc58` | Yes | — | HOLD — no common ancestor with main; preserve original history and selectively migrate only after a dedicated audit. |
| `migration/restore-durable-execution-research-schema` | `8b8d2264e347` | Yes | [#51 closed draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/51) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `ops/github-actions-maintenance-20261011` | `52c1a48cdf7d` | Yes | [#46 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/46) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `ops/institutional-development-workflow` | `f0b7f54ade27` | Yes | [#2 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/2) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `ops/reconcile-gitlab-namespace-sync-controller` | `8dc9ba544f3d` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |
| `ops/render-github-shadow` | `d7e2bfb1d31d` | Yes | — | UNREVIEWED DIVERGED REF — no associated PR in the snapshot; do not merge blind. Needs a fresh PR and current-main validation. |
| `ops/scheduled-recalibration-enable` | `5f59a299da8d` | Yes | [#41 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/41) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `ops/staging-private-db-20261018` | `33c332b45888` | Yes | [#117 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/117) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `perf/signal-ingest-latency-20260920` | `65de7135aa5e` | Yes | [#11 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/11) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `production` | `74cabb8d6156` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |
| `refactor/separate-execution-audit-20261011` | `a0395fd3ed2d` | Yes | [#45 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/45) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `research/dao-wider-stops-30pct` | `018ade2f5ee0` | Yes | [#119 closed draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/119) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `research/dual-lane-risk-guard` | `51af03775956` | Yes | [#38 open draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/38) | OPEN DRAFT — assessed but not merged; see PR description/release gates. Protected source branch retained. |
| `research/feature-mda-counterfactual-scaleout-oos` | `0ca06cf87ca2` | Yes | [#22 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/22) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `research/hard-loss-firewall` | `3fac15c0cf8c` | Yes | [#33 open draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/33) | OPEN DRAFT — assessed but not merged; see PR description/release gates. Protected source branch retained. |
| `research/inducement-structural-provenance` | `f783537a0739` | Yes | [#32 open draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/32) | OPEN DRAFT — assessed but not merged; see PR description/release gates. Protected source branch retained. |
| `research/matched-mt5-variant-audit-20261012` | `239642588396` | Yes | [#71 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/71) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `research/mt2-win-loss-asymmetry-guard-20261009` | `d4594fc3d281` | Yes | [#36 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/36) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `research/mt5-diagnostic-parity-audit-20261018` | `79d5d6f5b07f` | Yes | [#115 open draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/115) | OPEN DRAFT — assessed but not merged; see PR description/release gates. Protected source branch retained. |
| `research/risk-trailing-optimization-20261013` | `59f556e9df37` | Yes | [#86 closed](https://github.com/cirvannaco-png/Midas-touch2-/pull/86) | CLOSED UNMERGED — not merged as this PR; retained as a protected ref. Where applicable its validated successor/port is recorded in this audit. |
| `research/risk-trailing-optimization-rebased-20261013` | `ea5c9cd32e66` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |
| `risk-trailing-hardening-2026-10-08` | `8285872396a6` | Yes | [#35 open draft](https://github.com/cirvannaco-png/Midas-touch2-/pull/35) | OPEN DRAFT — assessed but not merged; see PR description/release gates. Protected source branch retained. |
| `sync/bootstrap` | `eca74e21d561` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |
| `sync-test/conflict-github` | `b5d976f032d1` | Yes | [#1 closed](https://github.com/cirvannaco-png/Midas-touch2-/pull/1) | HOLD — synchronization/conflict test fixture; not production feature code. |
| `sync-test/conflict-gitlab` | `9406572a907f` | Yes | — | HOLD — synchronization/conflict test fixture; not production feature code. |
| `sync-test/github-to-gitlab` | `6473ce9a5871` | Yes | — | HOLD — synchronization/conflict test fixture; not production feature code. |
| `sync-test/github-to-gitlab-20260918` | `9b5d77051843` | Yes | — | HOLD — synchronization/conflict test fixture; not production feature code. |
| `sync-test/gitlab-to-github` | `acd74a9f86fe` | Yes | — | HOLD — synchronization/conflict test fixture; not production feature code. |
| `test/native-dynamic-stop-policy-20261014` | `0657180a785c` | Yes | [#97 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/97) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `test/partial-close-recovery-contract-20261013` | `39a921f05c94` | Yes | [#79 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/79) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `test/recovery-fault-reconciliation-20261013` | `61cf918de486` | Yes | [#128 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/128); [#80 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/80) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `test/scoring-evidence-authority` | `9ccc515147ad` | Yes | [#62 closed merged](https://github.com/cirvannaco-png/Midas-touch2-/pull/62) | INTEGRATED — associated PR merged; branch retained as protected history. |
| `tmp-check` | `0809c59cfbfd` | Yes | — | NO ASSOCIATED PR — protected ref retained; no separate merge performed without a reviewable current-main diff. |

## How to read this register

- “Integrated” indicates at least one associated PR is recorded as merged. A source ref may still exist after its change lands in `main`; branch deletion was not requested and none was attempted.
- “Closed unmerged” means that pull request was not merged, not necessarily that no later port or successor integrated a subset of the same behavior.
- “No associated PR” or “unreviewed diverged ref” means the branch is recorded and retained; it must not be promoted merely because it exists.
- This is a point-in-time accounting register, not a permanent statement that refs cannot move. Re-run the inventory before the next integration wave.
