# Medis Touch → Midas Touch 2 Compatibility Matrix

**Scope:** source `cirvannaco-png/Medis-Touch` versus target `cirvannaco-png/Midas-touch2-`, default branches inspected on 2026-10-12. This is a migration decision record, not a claim that every source file has been behaviorally ported.

## Findings and disposition

| Source path / capability | Midas target finding | Disposition |
| --- | --- | --- |
| `telegram-bridge/migrations/versions/0007_parameter_config_registry.py` | Revision `0007` is already used by Midas for subscribers/payments. The source revision cannot be copied under the same ID. | Do not copy revision numbers or replace Midas migration history. |
| `telegram-bridge/migrations/versions/0008_subscribers_and_payments.py` | Midas uses `0008` for its immutable configuration registry and has subscriber/payment tables in its own `0007`. | Preserve target chain. |
| `telegram-bridge/migrations/versions/0009_research_execution_portfolio.py` | Source creates `research_experiments`, `experiment_observations`, `experiment_book_results`, `validation_runs`, `promotion_decision_audit`, `execution_ledger`, and `portfolio_reservations`. Target's `0009` is configuration-evaluation schema; those seven source models/tables were absent from target `app/models.py`/migration chain. | **Confirmed schema gap.** This PR restores the ORM models and adds additive revision `0017` after target `0016`; it does not renumber or replace existing Midas migrations. |
| `EA/includes/Portfolio/PortfolioRiskEngine.mqh` | File is absent at the same path in Midas, but the source EA facade does not include it. Midas has `PortfolioManager.mqh`, `MultiTradeEngine.mqh`, `RiskGuard.mqh`, and Python portfolio-risk/pre-trade modules. | Do not copy an unreferenced alternate engine. Further work should compare live call paths and tests before deciding whether any rolling-correlation behavior is missing from the EA itself. |
| `EA/includes/Execution/AsyncExecutionEngine.mqh`, `EA/includes/Execution/PortfolioCoordinator.mqh` | Not present at the same paths in target. They are not direct includes of the inspected source EA facade; Midas has distinct order manager, broker adapter, multi-trade and recovery components. | No blind copy. Confirm whether any needed behavior is actually reachable/required before migration. |
| `EA/includes/Core/RuntimeConfigBus.mqh`, `EA/includes/Core/RuntimeParameters.mqh` | Not present at the same paths. The inspected source EA facade does not include them. Midas has its own immutable config-sync contract and acknowledgement flow. | No blind copy; preserve Midas config lifecycle and acknowledgement behavior. |
| `EA/includes/Execution/TradeStateMachine.mqh` | Source and target blob SHA matched in the reviewed comparison. | No transfer needed. |
| `EA/includes/Recovery/RecoveryEngine.mqh` | Same path differs. Target version has Midas-specific `OutcomeTrackerLive` integration and additional decision/leg identity handling. | Preserve target implementation; do not replace with source version. Perform semantic review and recovery fault tests separately. |
| `EA/includes/Signals/ConfigSync.mqh` | Same path differs; target has a configuration contract and acknowledgement semantics tied to Midas's immutable registry. | Preserve target implementation; validate endpoint/ACK failure cases rather than overwrite it. |
| `EA/includes/Portfolio/PortfolioManager.mqh` | Same path differs. Midas has batch admission, symbol/group position caps, risk calculation and fail-closed rejection when open risk cannot be calculated. | Preserve target implementation. The missing source risk-engine file alone does not prove missing functionality. |
| `tools/gating.py` and `tools/metrics_engine.py` | Same paths differ. **Midas gating is stricter by design:** it refuses promotion while any required metric lacks persistent, non-overlapping evidence and validates `min_persistence >= 1`. The source gate can promote when one metric moves up and no resolved metric moves down even if other gated metrics remain incomplete. Midas metrics also preserve strategy/asset-class breakdowns and report commission, spread, and slippage separately from expectancy. | Preserve Midas versions. The source gate behavior is not a safe compatibility improvement; copying it would weaken the promotion guard. Any future change requires matched tests and provenance evidence. |
| `telegram-bridge/app/research/*` and `telegram-bridge/app/research_routes.py` | Source contains a broker-neutral research package and authenticated research/execution routes; these source paths are absent in target. Midas already has separate adaptive research, pre-trade risk, execution-recovery and research tooling, so a direct copy risks duplicate control paths. | This PR restores the missing durable schema only. The API/service layer remains an explicit follow-up, requiring an integration design and tests before enabling broker-facing calls. |


| `telegram-bridge/app/config_routes.py` | Midas has a split configuration lifecycle: immutable registry/evaluation/sync-state models and `app/api/config_sync.py`; same-path route copy would collide with target API boundaries. | Do not copy wholesale. Audit endpoint-by-endpoint against the target config contract before proposing any missing endpoint. |
| `telegram-bridge/app/control_plane.py` | No same-path target file. Midas has separate fail-closed service boundaries and research/strategy controls; the source control plane is a different module boundary. | No direct file copy; map each externally reachable endpoint and gate to current Midas services first. |
| `telegram-bridge/app/copy_routes.py`, `copy_settings.py` | Midas's copy-feed and subscriber behavior is split across current routes, copy-trading/admin modules, subscriptions, and settings store. | Preserve target route contracts; compare behavior and authorization tests rather than restoring duplicate routers. |
| `telegram-bridge/app/payment_models.py` | Subscriber/payment ORM models and the matching migration already exist in Midas under `app/models.py` and migration `0007_subscribers_and_payments.py`. | Functionally represented; no transfer needed. |
| `telegram-bridge/app/deployment.py` | No same-path target module. Midas has config lifecycle/sync and deployment/maintenance workflows with distinct operational contracts. | Do not copy without a requirement-by-requirement endpoint and workflow comparison. |
| `telegram-bridge/tests/test_imports.py` | Source-only import smoke test; target's CI already compiles Python sources and runs bridge tests, and the target module graph is intentionally different. | Do not port as a substitute for behavior tests. Add a focused regression test only if it detects a target-specific import-cycle risk. |


| `EA/includes/Execution/OrderManager.mqh` | Same path differs. Midas identifies trades by decision **and leg**, adds ticket/decision lookup, prevents duplicate live trades for a decision, and supports per-leg restore/cancel behavior for its multi-trade engine. | Preserve Midas implementation; do not overwrite with the source's single-decision-indexed version. |
| `EA/includes/Execution/BrokerAdapter.mqh` | Same path differs. Midas has explicit execution-completion checks that distinguish partial fills and permitted no-change responses, plus direction-aware market-open checks. | Preserve Midas behavior and validate partial execution outcomes in the recovery test suite. |
| `EA/includes/Execution/PositionManager.mqh` | Midas integrates `DynamicStopEngine`, dynamic-stop input policy, structural swing anchors, spread/ATR guardrails, stop-modification throttling, and SL-modification audit. | Preserve Midas stop-management enhancements; do not replace with the simpler source manager. |
| `EA/includes/Trading/OutcomeTracker.mqh` / `OutcomeTrackerLive.mqh` | The Midas EA facade uses `OutcomeTrackerLive`, which records actual executed/closed outcomes and integrates environment-strategy memory and decision fingerprints. The target also has a separate simulation tracker with resolution-time provenance. | Preserve the live/simulation split and Midas lineage. Do not substitute the source's simulation tracker for live accounting. |


| `EA/includes/Trading/TradeZone.mqh` | Source file defines a runtime-parameter overlay on `CTradeDecision`. Midas intentionally turns this same path into a compatibility shim and makes `StrategyTradeZone.mqh` authoritative; the EA facade includes the strategy router, which builds SMC and peer-strategy setups and incorporates environment-memory evidence. | Do not restore the source file over the shim. Doing so would introduce a duplicate `CTradeDecision` definition and bypass Midas's strategy-selection architecture. |
| `EA/includes/Decision/DecisionEngine.mqh` | Midas adds `EnvironmentPolicy` arbitration and explicit setup-geometry validation before routing an action. | Preserve Midas gates; test their thresholds and invalid-geometry handling rather than porting the source router wholesale. |


| `medis_touch/app/parameter_proposal/*` | Source-only 22-file proposal package. Its own README explicitly says the production evaluator must be wired to real outcome data and the EA's replay callback, and calls out PostgreSQL persistence, multiple-testing provenance, state-machine deployment, and integration/failure-injection tests as remaining release gates. Midas has a separate research stack in `tools/optimizer.py`, `champion_challenger.py`, `walk_forward.py`, `oos_firewall.py`, `recalibration_guard.py`, and related tests. | Do not copy the package wholesale: it is an implementation foundation, not a proven complete capability. Map each remaining gate against Midas's actual replay, data, and activation paths before porting; never imply it is live-validated. |


| `EA/includes/Decision/DecisionStore.mqh` | Midas persists the expanded decision record and execution-leg identity/target fields, supporting multi-leg restoration and per-leg outcome attribution. | Preserve Midas's expanded serialization contract. Replacing it with the source's shorter CSV record would lose Midas decision lineage and leg data. |
| `EA/includes/Signals/SignalPublisher.mqh` | Midas adds decision-fingerprint transport and preserves the target's current outcome/provenance contract. | Preserve target payload fields and bridge schema alignment; only port source behavior if a contract test demonstrates a missing field. |
| `EA/includes/Analysis/Scoring.mqh` | The target retains the core SMC score path and adds an explicit value-area contradiction block control; Midas strategy diagnostics remain separate from the base confidence sum. | Preserve the target's evidence-separation rule and contradiction gate. Do not merge old component scores in a way that double-counts the same structural evidence. |

## Validation in this PR

- ORM metadata tests assert all seven restored tables and critical idempotency, lease, broker-reference, holdout, and outcome fields.
- Tests assert the new tables coexist with Midas-specific `signal_delivery_outbox`, configuration registry, configuration evaluation, and config-sync state models.
- Migration ancestry is checked as `0017 → 0016 → 0018 → 0019` (Midas already owns revision `0018` for outcome-completeness provenance; the portfolio-scope migration must therefore be `0019`).
- Latest CI for PR #81 at the inspected head passed all six jobs in run `38359317052`: Python tests, research-tool tests, handbook reference tests, MQL5 structural validation, bridge quality/security, and PostgreSQL migration upgrade/downgrade/re-upgrade. This is repository CI evidence, not MetaEditor or terminal evidence.
- These checks do **not** substitute for applying the Alembic migration to a disposable PostgreSQL database, MetaEditor compilation, MT5 Strategy Tester, demo forward testing, or broker reconciliation.

## Non-negotiable migration rule

A missing filename is only a lead, not proof of a missing feature. Preserve Midas-specific execution state, partial-fill handling, decision/leg lineage, immutable configuration, outcome provenance, and signal delivery. Migrate only a behavior that is both genuinely absent and compatible with Midas's current call graph; add regression tests for the behavior before merge.


## Research-module behavior audit (source-only package)

The source proposal package contains these 22 modules. Matching names are not treated as proof of equivalence; the status below records where the behavior is represented and what remains to be proven.

| Source module / behavior | Midas-side analogue | Audit disposition / missing proof |
| --- | --- | --- |
| `bounds.py`, `canonical_config.py`, `schema.py` | Configuration registry and canonical trade/config contracts | Preserve Midas's immutable registry. Add round-trip contract tests before treating all source validation rules as covered. |
| `candidates.py`, `proposer.py`, `search_budget.py` | `tools/optimizer.py`, adaptive research | Candidate generation exists in a different architecture. Search-budget equivalence and bounded-compute behavior require matched tests. |
| `challenger.py`, `objective.py`, `evaluator.py` | `tools/champion_challenger.py`, `tools/metrics_engine.py`, configuration evaluations | Broad capability overlap. Do not port source scoring until objective parity is demonstrated against Midas's costs-inclusive expectancy and strategy/asset-class breakdown. |
| `statistics.py`, `paired_stats.py`, `multiple_testing.py` | Research/statistical tools and optimizer tests | Exact statistical equivalence is **not yet established**. Require paired tests, multiple-testing correction tests, and reproducible seeds/provenance. |
| `walk_forward.py`, `holdout.py`, `robustness.py` | `tools/walk_forward.py`, `tools/oos_firewall.py`, `tools/recalibration_guard.py` | Analogues exist; verify temporal leakage barriers, disjoint windows, locked holdout immutability, and robustness acceptance rules end-to-end. The new compatibility API records chronology/provenance but does not itself run these analyses. |
| `registry.py`, `versioning.py`, `deployment.py`, `gates.py` | Immutable configuration registry, activation/recalibration state, Midas promotion gates | Preserve Midas promotion authority. End-to-end atomicity between approval, activation, EA acknowledgement, rollback, and audit still needs integration tests. |
| `models.py` | Midas research/configuration models plus restored experiment/validation tables | The seven-table schema has been restored additively. Full data-model semantic parity and migration of legacy research records have not been established. |

## Execution and portfolio behavior audit

| Behavior | Current Midas coverage | Remaining validation / blocker |
| --- | --- | --- |
| Duplicate decision/order submission | EA `OrderManager` keys tracked trades by decision and leg; bridge reserve uses a unique request ID | A deterministic request-ID contract joining EA decision+leg to bridge account+server is not yet wired into `COrderManager::Submit`. |
| Broker send ambiguity / network timeout | Bridge keeps expired leases in `RECOVERING` and retains ACTIVE risk reservations | EA does not yet reserve before broker send or transition to SENT/ACKED/FILLED through the API. A timeout after broker acceptance remains an unclosed integration case. |
| Partial fills and partial closes | Broker adapter and recovery/outcome code have Midas-specific partial-fill/leg behavior | No end-to-end broker deal-volume ledger reconciles cumulative deals, current position volume, commissions/swaps/fees, and remaining risk reservation. |
| Restart recovery | EA `RecoveryEngine` restores trades from broker state/history using trade comments and decision/leg identity | No account-wide startup handshake imports all open positions/orders into bridge risk state before new entries. Existing positions with missing/unparseable comments require an explicit conservative orphan-position policy. |
| Duplicate broker fills / history replay | State-machine and recovery safeguards exist locally | No durable broker-deal uniqueness/idempotency endpoint is currently called by the EA; duplicate-fill fault injection across EA, API, and PostgreSQL remains outstanding. |
| Broker/database disagreement | Bridge refuses to infer rejection from lease expiry and requires evidence for terminal transitions | There is no complete account-snapshot reconciliation endpoint/caller that can classify broker-only, DB-only, partially closed, and conflicting positions. The safe action must be retain risk and block new entries until reconciled. |
| Portfolio risk | Midas EA has batch admission, symbol/group caps and fail-closed risk calculation; bridge has per-`portfolio_key` heat reservation | EA/bridge risk-unit normalization is not yet defined end-to-end. A 3R bridge heat ceiling must not be interpreted as 3% account risk without a documented conversion and matched tests. |
| Existing account positions | EA recovery is scoped by its configured symbol/magic, while portfolio-risk needs account-wide exposure | Account-wide import across symbols/magic numbers and netting-vs-hedging account behavior is unproven. |

## Explicit release gates

1. Define a canonical portfolio key (broker server + account login; do not include magic number if exposure is account-wide), request ID (portfolio + EA instance strategy + decision ID + leg), and documented risk units.
2. Add broker snapshot/deal reconciliation API semantics that are idempotent by broker deal/ticket identity and do not release risk on missing/partial history.
3. Call reservation and pre-send state transitions in the authoritative EA submit path; after a broker call, record broker return codes and tickets without retrying an ambiguous send.
4. Reconcile all account positions and pending orders before enabling entries on startup/restart; fail closed on orphan positions, incomplete history, or DB/broker disagreement.
5. Add fault-injection tests for duplicate fills, partial closes, terminal restarts, and DB/network outages; then compile in MetaEditor, run matched Strategy Tester runs, and forward-test on a demo account.
6. Keep PR #81 draft and unmerged until these gates pass. Current CI is green for bridge/schema/structural checks only; it does not satisfy gates 1–5.
