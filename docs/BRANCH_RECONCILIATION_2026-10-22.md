# Branch reconciliation — Midas-touch2-

**Snapshot:** 2026-10-22  
**Repository:** [cirvannaco-png/Midas-touch2-](https://github.com/cirvannaco-png/Midas-touch2-)  
**Main HEAD at report creation:** `604d2a268103df92c23eb8d9e073e7d232e4be64`  
**Branch refs inventoried:** 154  
**Open PRs at snapshot:** 18

## Decision rule

This is a reconciliation, not a blanket approval to ship every branch tip. A branch with no commits ahead of `main` needs no merge. A merged PR is accounted for by its merge commit. Stale-base feature branches are not force-pushed onto `main`: their full histories can reintroduce superseded code and conflicts. Changes to live entry/exit logic, risk limits, accounting or production infrastructure are not promoted solely because static CI passes. The repository's own evidence gates require native MT5/MetaEditor, real-history cost-inclusive validation and Exness demo reconciliation where specified.

## Completed integrations in this pass/context

- #120 — conservative small-account defaults and production preflight
- #110 — GitLab mirror cleanup for excluded GitHub workflows
- #109 — top-down MTF candidate and drawdown risk ladder
- #102 — retain native policy-test evidence
- #121 — latest-main opt-in MTF structure-alignment gate
- #122 — durable emergency-stop latch
- #123 — research-only DaoEA wider-stop experiment port
- #124 — latest-main SMC structural diagnostics port
- #125 — LONA report-consistency audit
- #126 — tester-only MT5 deal exporter
- #127 — cost stress, risk-adjusted metrics and locked-OOS tooling
- #36 — research-only win/loss asymmetry experiment record

Important boundary: merging research tooling or experiment documentation does **not** mean its strategy candidate is profitable or approved for live execution. Actual real-tick strategy results and Exness demo-forward reconciliation remain outstanding.

## Current branch register

Each live branch is listed below with its current ref SHA and its reconciliation disposition. The audit intentionally does not delete branches.

| Branch | Head (short SHA) | Disposition |
|---|---|---|
| `audit/complete-architecture-20260925` | `1e669b86c1` | Merged via PR #24 (fix: complete MQL5 architecture audit and compile-safety hardening); merge commit 8b135ce50a. |
| `audit/fix-outcometracker-compiler-parity` | `351922bc37` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `audit/midas-touch-deep-hardening-20260925` | `ca8569e14c` | PR #23 closed without merge; changes not promoted in this audit. (audit: eliminate MQL5 decision duplication and harden compile-safety gates) |
| `audit/midas-touch-final-hardening-20260925` | `88d0920cbc` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `audit/performance-targets-and-promotion-gates-20261013` | `9959fcc6b2` | Merged via PR #85 (docs(audit): establish performance and promotion gates); merge commit bf0b3573c5. |
| `audit/pre-protection-hardening` | `940e01b12f` | Merged via PR #5 (audit: final pre-protection repository hardening); merge commit faa64256ee. |
| `bench/render-before-after` | `1613f040e8` | PR #15 closed without merge; changes not promoted in this audit. (test: run real Render before-after latency benchmark) |
| `benchmark/baseline-3dff554` | `3dff554a8f` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `benchmark/baseline-principal-20260920` | `3dff554a8f` | Compare audit found no commits ahead of main; historical/redundant branch, no merge needed. Retained, not deleted. |
| `chore/execute-mql5-policy-tests-20261014` | `36d5d86024` | Merged via PR #96 (test(mql5): execute policy assertions in native Strategy Tester); merge commit 6b535db56f. |
| `chore/production-health-mt5-evidence-20261014` | `6d7fc2b445` | Merged via PR #103 (ci: retain MT5 policy evidence and probe production DB health); merge commit c8380878b4. |
| `chore/retain-native-policy-test-evidence-20261014` | `4689ed15c3` | Merged via PR #102 (ci(mql5): retain native Strategy Tester policy evidence); merge commit 0064c77f89. |
| `chore/verify-runtime-ledger-auth-20261014` | `6eae5194b2` | Merged via PR #104 (ci(health): verify production execution ledger requires authentication); merge commit 8b121f9f25. |
| `ci/compileall-post-merge-20260926` | `1214da15d4` | Merged via PR #28 (ci: add repository-wide Python compile check); merge commit c83417a1eb. |
| `ci/fix-green-sync-contract` | `ce21161539` | PR #7 closed without merge; changes not promoted in this audit. (ci: restore green validation and harden sync parity) |
| `ci/github-actions-validation` | `940e01b12f` | Merged via PR #4 (CI: enable GitHub Actions validation); merge commit f8fafc7654. |
| `ci/gitlab-api-pipeline-source-20261014` | `bfe40e67a0` | Merged via PR #107 (ci(gitlab): allow API-triggered mirror validation pipelines); merge commit b0dea53ccd. |
| `ci/latency-percentiles` | `960deece5c` | PR #12 closed without merge; changes not promoted in this audit. (test: strengthen latency regression protection) |
| `ci/latency-percentiles-main` | `ac89545db3` | Merged via PR #14 (test: strengthen latency regression protection); merge commit 3ec40b5ff0. |
| `ci/metatrader5-compile-20261011` | `f42c0c4ecd` | Merged via PR #44 (Add MetaEditor compile gate and fix MQL5 compile blockers); merge commit 249ae30428. |
| `ci/production-lifecycle-e2e` | `940e01b12f` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `ci/verify-full-midas-ci` | `d56799c3df` | PR #13 closed without merge; changes not promoted in this audit. (chore: verify full CI on optimized Midas revision) |
| `docs/github-source-of-truth-20261011` | `3a010561f6` | Merged via PR #48 (ops: enforce GitHub main authority and safe GitLab mirroring); merge commit 76a6473c4f. |
| `docs/post-audit-remediation-status-20261013` | `56bdc636f5` | Merged via PR #92 (docs(status): record remediation and live-trading release gates); merge commit 046ffbe864. |
| `feat/actual-mt5-tester-validation-20261014` | `ffd1521738` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `feat/chart-control-panel-trailing-audit-20261011` | `f0c736926d` | Merged via PR #43 (Add on-chart trade controls, configurable sessions, and execution audit); merge commit 088fce827c. |
| `feat/durable-execution-ledger-integration` | `1cbe40c618` | DRAFT PR #81 — Held: execution-ledger and risk-reservation changes require authenticated database/bridge connectivity plus broker-order, partial-close and restart reconciliation evidence. |
| `feat/ea-config-structural-trailing` | `aa4f55ca4b` | Compare audit found no commits ahead of main; historical/redundant branch, no merge needed. Retained, not deleted. |
| `feat/mtf-structure-alignment-rebased-20261014` | `f9d2b4fdfa` | PR #108 closed unmerged due to conflicts; current-main port merged as PR #121. |
| `feat/reconciliation-and-matched-validation-20261014` | `53a8ecad13` | Merged via PR #94 (Wire durable broker ledger and restore matched risk validation harness); merge commit aba61e068a. |
| `feat/separate-prop-firm-and-micro-account-profiles` | `652008c2ad` | DRAFT PR #82 — Held: introduces an 8% MICRO_RESEARCH envelope, conflicting with the stated fixed 30% small-account risk setting; real MT5 and demo validation are absent. |
| `feature/architecture-governor` | `87ca6d3840` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `feature/dynamic-stop-engine` | `f0c8266360` | Compare audit found no commits ahead of main; historical/redundant branch, no merge needed. Retained, not deleted. |
| `feature/fvg-invalidation-fix-research` | `9fa04e3cb8` | DRAFT PR #31 — Held: FVG invalidation is a strategy research change; matched, cost-inclusive and locked-OOS validation is outstanding. |
| `feature/high-probability-multi-trade` | `cc461cab0f` | Merged via PR #16 (Add high-probability multi-trade execution); merge commit 4f837d5ac0. |
| `feature/midas-decision-architecture` | `f8c8b99b67` | DRAFT PR #34 — Held: large decision-architecture refactor on a stale base; needs a conflict-resolved current-main port and behavioral parity evidence. |
| `feature/mss-fvg-auction-confluence` | `ec3b8f8034` | Compare audit found no commits ahead of main; historical/redundant branch, no merge needed. Retained, not deleted. |
| `feature/mtf-structure-alignment` | `33d4cb8b89` | PR #95 closed without merge; changes not promoted in this audit. (Add opt-in multi-timeframe structure alignment gate) |
| `feature/order-flow-confirmation-engine` | `306f5c2eed` | DRAFT PR #112 — Held: research-only diagnostics; exact real-tick ON/OFF parity, cost-inclusive OOS and Exness demo reconciliation are outstanding. |
| `feature/peer-strategy-routing` | `177a272537` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `feature/phase-a-d-hardening` | `c0ec10040d` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `feature/production-hardening` | `fe58eb2bd0` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `feature/smc-causal-fvg-loss-reduction` | `a63acfa4a2` | DRAFT PR #30 — Held: causal SMC/FVG loss-reduction candidate has no validated performance evidence; keep research-only. |
| `feature/smc-structural-validator` | `bddf29798a` | PR #29 closed unmerged due to conflicts; current-main port merged as PR #124. |
| `feature/top-down-mtf-dd-risk` | `7a7eda9a96` | Merged via PR #109 (Add direction-agnostic top-down MTF candidate and drawdown risk ladder); merge commit 2ef80fc381. |
| `feature/volume-profile-intelligence` | `f438fa729f` | Merged via PR #27 (feat: cross-asset volume profile intelligence); merge commit 8e7f1758d1. |
| `fix/account-risk-profile-ledger-normalization-20261014` | `26c4d70c5b` | Merged via PR #98 (fix(risk): honor selected account profile during startup reconciliation); merge commit bc55c13052. |
| `fix/accounting-fill-ledger-reconciliation` | `5c94275052` | PR #53 closed without merge; changes not promoted in this audit. (Fix authoritative fill-ledger recovery and parent reconciliation) |
| `fix/authoritative-fill-ledger-main` | `d05bcb5bcc` | Merged via PR #58 (Reconcile recovered broker fills against authoritative parent ledger); merge commit 2692ba8b22. |
| `fix/authoritative-position-identity-20261012` | `dcb23d1dd8` | DRAFT PR #70 — Held: no check runs were reported for this exact head; position identity and partial-fill/risk-sizing changes need current-main CI and MT5 validation. |
| `fix/authoritative-strategy-setup-lineage-20261009` | `a5bea662ce` | DRAFT PR #37 — Held: static checks passed, but the PR explicitly requires native MetaEditor compilation and relevant MT5 tests; those gates are not evidenced. |
| `fix/backtest-evidence-variable-spread-20261012` | `2c6ba67b46` | Merged via PR #72 (Fix variable-spread MT5 evidence provenance validation); merge commit 97f65319ff. |
| `fix/ci-nonblocking-gitlab-sync-20260919` | `73fc2581f0` | Merged via PR #9 (ci: keep external GitLab sync non-blocking); merge commit 8c1e7ecde9. |
| `fix/ci-production-audit-20260919` | `bca662b0b6` | Merged via PR #8 (fix(ci): harden copy-feed tests and GitLab synchronization); merge commit 87086247e2. |
| `fix/codex-audit-main-20260925` | `14cc41d585` | Merged via PR #25 (fix: close Codex audit findings and restore green main CI); merge commit 51e1868419. |
| `fix/configure-risk-profile-guard-20261014` | `31368a1dc2` | Merged via PR #99 (fix(risk): block unconfigured small-account and prop-firm profiles); merge commit 9f19d98cb5. |
| `fix/dao-research-cost-model-callsite` | `3215bef1d6` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `fix/dynamic-stop-no-market-sl-20261014` | `ef188c189f` | Merged via PR #106 (fix(execution): reject dynamic stops on or beyond market price); merge commit f2b1c2e641. |
| `fix/dynamic-stop-reject-market-price-20261014` | `ac803ce48d` | PR #105 closed without merge; changes not promoted in this audit. (fix(execution): reject dynamic stops on or beyond market price) |
| `fix/dynamic-stop-test-api-20261014` | `684794c1fa` | Merged via PR #100 (fix(mql5): isolate dynamic-stop test geometry from runtime); merge commit c2fe163b91. |
| `fix/ea-deal-event-idempotency` | `fc28fe5b62` | Merged via PR #55 (Make EA deal accounting idempotent and mark incomplete recovery outcomes ambiguous); merge commit d74c03aa61. |
| `fix/emergency-stop-durable-latch-20261018` | `4addd6c00f` | PR #114 closed unmerged; current-main emergency-stop latch port merged as PR #122. |
| `fix/enable-recalibration-schedule-20261010` | `9bbf40da08` | Merged via PR #40 (fix(recalibration): activate scheduled learning cycle safely); merge commit 337feb3a1c. |
| `fix/evidence-deduplication` | `86a5fa5376` | Merged via PR #21 (Fix duplicate BOS/liquidity evidence); merge commit ef205b7c10. |
| `fix/gitlab-ci-secret-and-import-path-20261011` | `f3da4bb52c` | Merged via PR #42 (ci: keep GitLab pipeline environment compatible with tests); merge commit 27ab69f68b. |
| `fix/gitlab-ruff-recovery-test-parity` | `07dec3f5e2` | Merged via PR #56 (Fix recovery test lint parity across CI providers); merge commit 74a2012f17. |
| `fix/gitlab-sync-token-auth-20261009` | `8f313396f4` | Merged via PR #39 (fix(ci): harden GitLab sync authentication); merge commit 35a9c45db1. |
| `fix/history-identity-parser-20261012` | `868423c8bb` | Merged via PR #75 (fix(recovery): validate history deal identity suffix before attribution); merge commit 11faab5804. |
| `fix/main-ci-remove-external-sync-gate-20260919` | `1e6bfdcd59` | Merged via PR #10 (ci: remove external GitLab sync from main push gate); merge commit 3dff554a8f. |
| `fix/midas-architecture-hardening-20260923` | `da739e488c` | PR #19 closed without merge; changes not promoted in this audit. (fix: harden MQL5 architecture and high-probability execution boundaries) |
| `fix/midas-touch-main-ci-readme-20260925` | `c31084ad15` | Merged via PR #26 (ci/docs: keep main CI green and standardize Midas Touch naming); merge commit 41483a8e40. |
| `fix/min-volume-risk-guard` | `3f5658be6e` | Merged via PR #54 (Enforce strict minimum-volume risk and add position-level MT5 metrics); merge commit a8e3e2643f. |
| `fix/mirror-prune-stale-github-workflows` | `9cdd34286d` | Merged via PR #110 (Fix GitLab mirror cleanup for excluded GitHub workflows); merge commit d5a497635f. |
| `fix/mt5-package-layout` | `708282e3c9` | Merged via PR #18 (Add deterministic MT5 compile-layout staging and include checks); merge commit 2a5a8e808c. |
| `fix/multi-fill-vwap-outcome-accounting-20261012` | `f49b93364f` | DRAFT PR #73 — Held: no check runs were reported for this exact head; fill-VWAP/accounting/over-risk changes need current-main CI and MT5 partial-fill validation. |
| `fix/multi-trade-architecture-audit` | `cd7da0a1c3` | Merged via PR #20 (refactor: move high-probability multi-trade policy into portfolio layer); merge commit 404d1c2f7f. |
| `fix/multifill-outcome-accounting-20261012` | `35e1e006a2` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `fix/multifill-outcome-accounting-v2-20261012` | `f3a297a4bb` | Merged via PR #77 (fix(accounting): reconcile parent VWAP and reject invalid deal metrics); merge commit eb66967192. |
| `fix/normalize-protective-prices-to-tick-20261014` | `2c40d6fcc6` | Merged via PR #101 (fix(execution): normalize protective prices to broker tick grid); merge commit ca8be993fb. |
| `fix/order-manager-volume-boundary-20261012` | `61258ae2ff` | Merged via PR #66 (fix(execution): enforce broker lot constraints at order boundary); merge commit 8b7409ed0b. |
| `fix/outcome-completeness-ci-20261012` | `ba215fb471` | Merged via PR #74 (fix(ci): reconcile outcome completeness and MetaEditor overload contracts); merge commit 513c76760a. |
| `fix/outcome-provenance-accounting` | `871a7d574d` | PR #49 closed without merge; changes not promoted in this audit. (Fix Midas outcome provenance and execution-cost accounting) |
| `fix/outcome-provenance-main` | `2d34bf366e` | Merged via PR #60 (Persist complete EA outcome provenance and signed broker cashflows); merge commit e164963d77. |
| `fix/outcometracker-addsetup-signature` | `940e01b12f` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `fix/partial-close-volume-guard-20261013` | `18577683b7` | PR #88 closed without merge; changes not promoted in this audit. (fix(execution): validate partial-close volume against broker steps) |
| `fix/partial-exit-independent-of-trailing-20261013` | `190b85440a` | Merged via PR #93 (fix(execution): decouple partial exits from trailing stop success); merge commit 1db265b549. |
| `fix/payoff-asymmetry-precision-gates-2026-10-12` | `afdc6c6099` | DRAFT PR #76 — Held: trading-entry/exit candidate remains unscored; #127 ported research tooling only, not a validated strategy change. |
| `fix/portfolio-pending-order-risk-20261013` | `f688ef84d7` | Merged via PR #91 (fix(risk): reserve portfolio exposure for pending orders); merge commit 69e6328542. |
| `fix/position-ticket-identifier-parity-20261012` | `ab3e786d9a` | Merged via PR #67 (fix(execution): reconcile position ticket versus history identifier); merge commit 417a1c7d3d. |
| `fix/production-correctness` | `2b195e782a` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `fix/production-health-authenticated-preflight-20261018` | `9ab381736b` | DRAFT PR #113 — Held: authenticated production ledger/database is not verified; one workflow check was skipped because production credentials/evidence are absent. |
| `fix/production-readiness-health-gate` | `940e01b12f` | Merged via PR #6 (fix: make production readiness health gate database-aware); merge commit 940e01b12f. |
| `fix/qualified-closed-trade-target-20261013` | `966b3a25ce` | PR #89 closed without merge; changes not promoted in this audit. (fix(trading): count qualified closed trades, not entry fills) |
| `fix/qualified-trade-and-partial-close-guards-20261013` | `75c8496e24` | Merged via PR #90 (fix(ea): harden partial closes and qualified trade tracking); merge commit f7d7638db2. |
| `fix/recovery-identity-parser-20261012` | `7e8da8e704` | Merged via PR #65 (fix(recovery): reject malformed trade identities during restart recovery); merge commit 605b1f764a. |
| `fix/remove-hardcoded-return-target-20261013` | `23edbf765d` | Merged via PR #87 (fix(metrics): remove hard-coded 87% return target); merge commit de2e14810e. |
| `fix/remove-unused-recovery-placeholders` | `a24d8ce874` | Merged via PR #63 (Remove obsolete recovery SQL placeholder builder); merge commit aa22e8894a. |
| `fix/restore-production-postgres-infrastructure` | `1f5ea83c76` | DRAFT PR #118 — Held: the user is testing on the free plan; paid production database provisioning is not authorized or verified. |
| `fix/risk-atr-cap-fail-closed-20261012` | `e6b2ccbb08` | PR #68 closed without merge; changes not promoted in this audit. (Fix ATR stop-distance validation fail-closed behavior) |
| `fix/risk-atr-cap-fail-closed-mainline-20261012` | `6c0fb4808e` | Merged via PR #69 (fix(risk): fail closed on invalid ATR stop-distance cap); merge commit e3316778c3. |
| `fix/robust-gitlab-tree-sync` | `e9d94c5f27` | Merged via PR #17 (Harden autonomous GitHub to private GitLab synchronization); merge commit bb403209e5. |
| `fix/sqlite-outbox-test-isolation-20261013` | `3c8f8e92ce` | Merged via PR #78 (test: isolate API tests from SQLite outbox worker races); merge commit 31dfc80141. |
| `fix/static-recovery-candidate-query` | `f97c2bdc46` | Merged via PR #61 (Remove dynamic SQL interpolation from recovery candidate query); merge commit 1dae8c58fc. |
| `fix/static-sql-recovery-query` | `6a68a156a2` | Merged via PR #57 (Avoid dynamic SQL construction in recovery journal query); merge commit c62bc7a231. |
| `governance/sync-automation` | `49fc352cf7` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `hardening/production-recovery-reconciliation` | `8a95a55001` | Merged via PR #50 (Hardening: production maintenance, recovery, and reconciliation); merge commit 0ba73ab2a5. |
| `hardening/small-account-risk-and-production-preflight` | `30787accea` | Merged via PR #120 (Hardening: conservative small-account defaults and production preflight); merge commit 7feb91bd48. |
| `integration/production-hardening` | `940e01b12f` | Compare audit found no commits ahead of main; historical/redundant branch, no merge needed. Retained, not deleted. |
| `integration/production-hardening-v2` | `940e01b12f` | Compare audit found no commits ahead of main; historical/redundant branch, no merge needed. Retained, not deleted. |
| `main` | `604d2a2681` | Default branch; current protected main. |
| `merge/dao-wider-stops-research-20261022` | `fe6576f860` | Merged via PR #123 (research: port DaoEA wider-stop experiment to current main); merge commit 0c2225fe1b. |
| `merge/emergency-stop-latch-20261022` | `a2d3acf001` | Merged via PR #122 (fix(safety): port durable emergency-stop latch to latest main); merge commit 9735314de3. |
| `merge/lona-report-consistency-audit-20261022` | `f490611ab7` | Merged via PR #125 (research: add LONA report consistency audit); merge commit 71dd4e6992. |
| `merge/mt5-tester-deal-evidence-20261022` | `557c1d5b0b` | Merged via PR #126 (test(mt5): export native tester deal evidence for costs-inclusive validation); merge commit 445c7daca5. |
| `merge/research-evidence-toolkit-20261022` | `baf746fbfa` | Merged via PR #127 (research: add cost stress, risk-adjusted metrics, and locked-OOS firewall); merge commit d7f897e60a. |
| `merge/resolve-mtf-structure-alignment-20261022` | `f1df39941b` | Merged via PR #121 (feat(mtf): resolve opt-in structure alignment gate on latest main); merge commit 5cee7292df. |
| `merge/smc-structural-diagnostics-20261022` | `99744af738` | Merged via PR #124 (feat(smc): port diagnostic structural validator to latest main); merge commit 76e90029b0. |
| `migration/compatibility-on-recovery-candidate` | `286e838bf0` | PR #52 closed without merge; changes not promoted in this audit. (Compatibility migration on recovery-hardening candidate) |
| `migration/compatibility-schema-main` | `0ef6062aed` | Merged via PR #59 (Restore additive execution and research schema compatibility); merge commit baeb8aae79. |
| `migration/medis-research-validation-guidelines` | `c30e4f24c4` | PR #47 closed without merge; changes not promoted in this audit. (Audit Medis Touch compatibility before selective migration) |
| `migration/medis-touch-complete` | `1debaa445c` | Independent migration/source history with no common ancestor to main; do not merge as a normal feature branch. |
| `migration/medis-touch-source` | `a8982611fc` | Independent migration/source history with no common ancestor to main; do not merge as a normal feature branch. |
| `migration/restore-durable-execution-research-schema` | `8b8d2264e3` | PR #51 closed without merge; changes not promoted in this audit. (Restore missing durable execution and research schema) |
| `ops/github-actions-maintenance-20261011` | `52c1a48cdf` | Merged via PR #46 (ops: make GitHub Actions the production maintenance scheduler); merge commit cac007c3d7. |
| `ops/institutional-development-workflow` | `f0b7f54ade` | Merged via PR #2 (ops: establish institutional development and production workflow); merge commit 14e4a11ddb. |
| `ops/reconcile-gitlab-namespace-sync-controller` | `8dc9ba544f` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `ops/render-github-shadow` | `d7e2bfb1d3` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `ops/scheduled-recalibration-enable` | `5f59a299da` | Merged via PR #41 (Add daily subscription maintenance job on current main); merge commit affec5565f. |
| `ops/staging-private-db-20261018` | `33c332b458` | DRAFT PR #117 — Held: staging database/service blueprint is not verified against the user's free-plan testing setup. |
| `perf/signal-ingest-latency-20260920` | `65de7135aa` | Merged via PR #11 (perf: reduce signal ingestion latency); merge commit 02f756fcca. |
| `production` | `74cabb8d61` | Compare audit found no commits ahead of main; historical/redundant branch, no merge needed. Retained, not deleted. |
| `refactor/separate-execution-audit-20261011` | `a0395fd3ed` | Merged via PR #45 (Separate execution audit from chart presentation); merge commit 474a4fc57c. |
| `research/dao-wider-stops-30pct` | `018ade2f5e` | PR #119 closed unmerged; research-only wider-stop port merged as PR #123. The trading strategy itself is not validated. |
| `research/dual-lane-risk-guard` | `51af037759` | DRAFT PR #38 — Held: no check runs were reported for this exact head; risk-governor changes remain a research candidate without current-main test evidence. |
| `research/feature-mda-counterfactual-scaleout-oos` | `0ca06cf87c` | Merged via PR #22 (Add research analytics and locked-OOS validation layer); merge commit b894506a2b. |
| `research/hard-loss-firewall` | `3fac15c0cf` | DRAFT PR #33 — Held: hard-loss firewall is OFF by default, but the PR explicitly requires native compile and MT5 Strategy Tester validation before promotion. |
| `research/inducement-structural-provenance` | `f783537a07` | DRAFT PR #32 — Held: signal provenance changes touch the decision path; full native compile and behavioral parity are not evidenced. |
| `research/matched-mt5-variant-audit-20261012` | `2396425883` | Merged via PR #71 (Research: add matched MT5 variant comparison harness); merge commit 28165d6727. |
| `research/mt2-win-loss-asymmetry-guard-20261009` | `d4594fc3d2` | Merged via PR #36 (docs(research): record MT2 win-loss asymmetry guard experiment); merge commit 604d2a2681. |
| `research/mt5-diagnostic-parity-audit-20261018` | `79d5d6f5b0` | DRAFT PR #115 — Held: real MT5 matched-run exports, native tester compilation for the current mainline integration, cost-complete walk-forward/OOS and Exness demo evidence are outstanding. |
| `research/risk-trailing-optimization-20261013` | `59f556e9df` | PR #86 closed without merge; changes not promoted in this audit. (Decouple partial exits and add matched stop/risk experiment harness) |
| `research/risk-trailing-optimization-rebased-20261013` | `ea5c9cd32e` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `risk-trailing-hardening-2026-10-08` | `8285872396` | DRAFT PR #35 — Held: capacity and weekday trade qualification can alter trade frequency/behavior; no matched cost-inclusive EA evidence is attached. |
| `sync-test/conflict-github` | `b5d976f032` | PR #1 closed without merge; changes not promoted in this audit. (test(sync): conflict detection) |
| `sync-test/conflict-gitlab` | `9406572a90` | Synchronization/conflict-test branch; not product code. Retained as test fixture; not merged into production main. |
| `sync-test/github-to-gitlab` | `6473ce9a58` | Synchronization/conflict-test branch; not product code. Retained as test fixture; not merged into production main. |
| `sync-test/github-to-gitlab-20260918` | `9b5d770518` | Synchronization/conflict-test branch; not product code. Retained as test fixture; not merged into production main. |
| `sync-test/gitlab-to-github` | `acd74a9f86` | Synchronization/conflict-test branch; not product code. Retained as test fixture; not merged into production main. |
| `sync/bootstrap` | `eca74e21d5` | No current open PR matched this branch. Branch tip is preserved; divergent/unreviewed changes were not fast-forwarded blindly. Requires targeted review/PR or explicit retirement. |
| `test/native-dynamic-stop-policy-20261014` | `0657180a78` | Merged via PR #97 (test(mql5): execute dynamic-stop policy assertions in native tester); merge commit 11ebcaeabb. |
| `test/partial-close-recovery-contract-20261013` | `39a921f05c` | Merged via PR #79 (test: cover partial-close recovery accounting invariants); merge commit 34dede1bcc. |
| `test/recovery-fault-reconciliation-20261013` | `61cf918de4` | Merged via PR #80 (test(recovery): add restart and reconciliation fault injection); merge commit 8d81d83916. |
| `test/scoring-evidence-authority` | `9ccc515147` | Merged via PR #62 (Guard scoring evidence authority against double-counting); merge commit e7a14e6de9. |
| `tmp-check` | `0809c59cfb` | Compare audit found no commits ahead of main; historical/redundant branch, no merge needed. Retained, not deleted. |

## Held merge gates

- Production/staging PostgreSQL blueprints (#117/#118): not merged; the user is testing on the free plan, and database/service provisioning is not being changed by a code merge.
- Authenticated production health (#113): not merged until a real authenticated database/ledger check succeeds; its production-evidence check was skipped.
- Diagnostic parity and order-flow research (#115/#112): do not promote as production behavior until real native MT5 OFF/ON runs, cost-complete walk-forward and locked-OOS evidence, and Exness demo reconciliation are attached.
- Account profiles (#82): proposes an 8% `MICRO_RESEARCH` envelope and conflicts with the stated fixed 30% small-account risk setting; not merged.
- Execution-ledger integration (#81): needs authenticated database/bridge connectivity and broker-side recovery/partial-close/restart proof.
- Fill accounting / authoritative position identity (#73/#70): no checks were reported for the exact heads in the audit; current-main CI and native partial-fill/position-identity evidence are needed.
- Strategy and architecture candidates (#76/#38/#35/#34/#33/#32/#31/#30): unique strategy/risk/decision-path changes remain on draft branches until their stated native compile, behavior-parity, matched-cost and/or OOS gates pass.

## What “accounted for” means here

Branches in the register are classified as merged, already ancestral/redundant, superseded by a current-main port, draft/held for named evidence, closed-unmerged, isolated migration/test history, or divergent without an active PR. No unreviewed head was forced into main, and no branch was deleted. Remaining divergent branches still need an individual targeted integration or an explicit decision to retire them; this report does not falsely describe them as merged.
