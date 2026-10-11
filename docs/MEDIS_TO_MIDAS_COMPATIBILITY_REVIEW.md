# Medis Touch → Midas Touch 2: compatibility review

## Status

This review distinguishes path absence from semantic absence. A full tree inventory and a first semantic pass of high-risk MQL5 execution, portfolio risk, configuration activation, research API and migration paths are complete. The remaining shared-file deltas still require function-by-function review before arbitrary code migration. No EA/business logic is changed by this review artifact.

## Compared snapshots

- Source: **cirvannaco-png/Medis-Touch**, tree SHA 5855bc2b5d5f223bbd394d3ed50ce8a532d34c23.
- Target: **cirvannaco-png/Midas-touch2-**, tree SHA cac007c3d721d9a9fc3ddf1a84a810f342147cbb.
- Inventory: source 232 files; target 380 files; 166 shared paths; 82 shared paths with changed content; 66 source-only paths; 214 target-only paths.

## High-priority compatibility findings

### A. Preserve Midas-specific execution and decision architecture

Midas' EA entry point composes its own SessionFilter, StrategyTradeZone, EnvironmentStrategyMemory, OutcomeTrackerLive, DailyTradeTarget, DecisionFingerprint, MultiTradeEngine, ExecutionAudit, and TradeControlPanel. These are meaningful target-specific additions. Do not replace the target root EA or these modules with source versions.

- **EA/includes/Execution/TradeStateMachine.mqh** is byte-identical in both repos (blob SHA 4f89105d1c9dd4e1879bb3010e0792f4b4293354); no transfer is needed.
- **EA/includes/Recovery/RecoveryEngine.mqh** differs. The Midas version wires in OutcomeTrackerLive and supports additional trade-identity/leg handling. Keep the target version; do not overwrite it with the source file.
- Source **EA/includes/Trading/TradeZone.mqh** is an active full CTradeDecision implementation with runtime overlays. Midas' same-path file is intentionally an 800-byte compatibility shim; the authoritative implementation is **EA/includes/Trading/StrategyTradeZone.mqh**, integrated with StrategySetupBuilders and EnvironmentStrategyMemory. This is a refactor, not a missing path to fill.
- Major changed hot spots include the two EA entry files, Core/Config, DecisionEngine/DecisionStore/TradeDecision, BrokerAdapter, OrderManager, PositionManager, PortfolioManager, RiskGuard, ConfigSync, SignalPublisher, CalibrationEngine, OutcomeTracker, RiskEngine, ValueAreaEngine, structure/strategy files and UI. Do not judge these changes by file size alone.

### B. Confirmed missing control: rolling cross-symbol correlation and factor-risk gate

Source **EA/includes/Portfolio/PortfolioManager.mqh** composes **PortfolioRiskEngine.mqh**; that engine estimates rolling M15-return correlation and per-factor exposure, then blocks a proposed trade when correlated-risk or factor-risk caps are exceeded. Midas' **PortfolioManager.mqh** retains useful Midas controls—aggregate portfolio-risk limit, per-symbol and group caps, batch validation for multi-leg entries, and rejection when existing risk cannot be computed—but has no corresponding rolling-correlation/factor-exposure calculation.

This is a genuine semantic difference. However, the source engine is not safe to copy verbatim: when return history is unavailable or variance is zero, its correlation helper returns 0.0, which can be interpreted as low correlation and let risk through. Recommended disposition: implement a Midas-native correlation/factor control with an explicit insufficient-data policy, conservative symbol mapping, aggregate multi-leg risk accounting, cache expiry/invalidation and tests. Keep all existing Midas checks. Do not simply copy the file and call it a migration.

### C. Runtime-parameter application was deliberately reduced to metadata acknowledgement

The source includes RuntimeParameters, RuntimeConfigBus and ConfigSync wiring that can overlay numeric strategy thresholds into CTradeDecision. The Midas EA uses ConfigSyncContract plus the new StrategyTradeZone and validates an immutable configuration envelope; the Midas contract states that it does not mutate inputs or strategy objects, and ConfigSync logs that live numeric inputs remain unchanged after an ACK.

Preserve that safety boundary rather than migrating live-mutating code. Clarify the control-plane contract: an ACK means that envelope metadata was validated and received; it is not proof that the EA applied the payload's numeric parameters. Any future activation must be a separately designed and tested transition with exact hash checking, schema/range checks, persisted active version, rollback and demo validation.

### D. Parameter proposal generation is missing, but the source proposer is not release-ready

The 23 source-only files under **medis_touch/app/parameter_proposal/** provide bounded candidate generation, immutable parameter/evaluation/proposal models, movement/statistical/regime/robustness gates, holdout/walk-forward helpers, and proposal versioning. Midas has no complete same-path or semantically equivalent candidate-generation/proposal state machine.

Midas already has a stricter MT5 Strategy Tester evidence boundary in **telegram-bridge/app/api/backtest_evidence.py**, plus configuration-registry/evaluation and environment-outcome modules. Reuse these target contracts instead of duplicating or weakening them. The source parameter-proposal README also says its evaluator needs a replay callback running actual EA decision logic and must not be used for live recommendations until that integration is wired to real historical data. Therefore, migrate only selectively and keep proposals non-activating until replay, persistence, human approval, EA-side application and rollback are implemented and verified.

### E. Authenticated durable research/execution API is missing from the target bridge

The source bridge mounts **config_routes.py**, **copy_routes.py** and **research_routes.py**. The research router exposes experiment creation, observation ingestion, champion/challenger gating, execution reservations/transitions, and recovery of expired leases. Its model/migration adds research experiments, observations/book results, validation runs, promotion-decision audits, an execution ledger and portfolio reservations.

Midas' **telegram-bridge/app/main.py** mounts its own config-sync, backtest-evidence, environment-outcome and general routers, not the source research router. The target models and migration chain do not define the same source research/control-plane schema. Midas' internal governed execution modules are useful but are not equivalent to a durable authenticated bridge API. If this control plane is still required, adapt its contracts to Midas types and auth, reuse existing config/evidence models where possible, and add a new forward migration from the Midas head with tests for duplicate requests, reservation conflicts, lease expiry/recovery, authorization and rollback.

### F. Migration histories diverged; do not transplant migrations by filename

Source revisions 0007/0008/0009 are parameter-config-registry, subscribers/payments, and research-execution-portfolio. The target uses 0007/0008/0009 for subscribers/payments, immutable configuration registry, and configuration evaluations, and continues through 0016 for config-sync, trade/outcome provenance and signal-delivery outbox. IDs and table semantics differ. Do not copy any source 0007–0009 migration as-is. A research-execution schema would need a new revision after the current Midas head and verification against both a fresh database and an already-migrated target database.

### G. Research analytics and validation tools are different implementations

- **tools/gating.py** and its tests differ. Midas fails closed when required metrics lack evidence and gates win rate, confidence AUC, and confidence-to-realized-R correlation. Preserve that behavior unless a targeted change is proven by tests.
- **tools/metrics_engine.py** and its tests differ. Both separate signal coverage from realized expectancy, but the target has its own bridge/database wiring. Review callers and semantics before transferring source code.
- The source validator **tools/validate_mql5_structure.py** is not present at the same path; Midas uses its own MQL5, architecture, edge-lineage and manifest validators. There is no need to copy validators simply to match filenames.

### H. Other source-only files are not automatically functionality gaps

AsyncExecutionEngine.mqh and PortfolioCoordinator.mqh are absent from the target, but neither is directly included by the source EA entry point. Prove active callers and end-to-end semantics before considering them. Source CI workflows are likewise not automatically needed because Midas has its own CI, MetaEditor compile and maintenance workflows. ZIPs, .replit and general docs/assets are not runtime features.

## Validation evidence and limits

- Pull request #47 is a draft. The checks on its documentation-only commit passed for all five Midas CI jobs: Python tests, research tools tests, handbook tests, MQL5 structural validation, and bridge quality/security.
- The latest main-branch MetaTrader 5 EA Compile workflow completed successfully for the unchanged target EA. This audit PR changes documentation only; it did not compile a newly migrated implementation.
- No portfolio-correlation change, bridge-schema migration, MT5 Strategy Tester run or demo-forward trading run was performed during this review. CI-green is not a claim of profitability or live-trading readiness.

## Appendix 1 — all source-only paths (66)

Absence inventory below is generated from the two Git trees; every path still requires semantic-equivalence assessment before it is classified as a user-visible feature gap.

- **.github/dependabot.yml**
- **.github/workflows/biweekly-recalibration.yml**
- **.github/workflows/daily-subscription-check.yml**
- **.github/workflows/ea-validate.yml**
- **.github/workflows/medis-touch-ci.yml**
- **.github/workflows/render-secrets.yml**
- **.github/workflows/telegram-bridge-ci.yml**
- **.replit**
- **EA/includes/Core/RuntimeConfigBus.mqh**
- **EA/includes/Core/RuntimeParameters.mqh**
- **EA/includes/Execution/AsyncExecutionEngine.mqh**
- **EA/includes/Execution/PortfolioCoordinator.mqh**
- **EA/includes/Portfolio/PortfolioRiskEngine.mqh**
- **LICENSE.md**
- **attached_assets/Medis-touch_FIXED_1786628036097.zip**
- **attached_assets/Medis-touch_v2.9_telegram-commands_1786628019509.zip**
- **docs/RESEARCH_EXECUTION_PORTFOLIO_ARCHITECTURE.md**
- **docs/adaptive-optimizer-architecture.md**
- **docs/medis-touch-ci-fix.md**
- **medis_touch/app/parameter_proposal/README.md**
- **medis_touch/app/parameter_proposal/__init__.py**
- **medis_touch/app/parameter_proposal/bounds.py**
- **medis_touch/app/parameter_proposal/candidates.py**
- **medis_touch/app/parameter_proposal/challenger.py**
- **medis_touch/app/parameter_proposal/config/__init__.py**
- **medis_touch/app/parameter_proposal/config/canonical.py**
- **medis_touch/app/parameter_proposal/config/schema.py**
- **medis_touch/app/parameter_proposal/deployment.py**
- **medis_touch/app/parameter_proposal/evaluator.py**
- **medis_touch/app/parameter_proposal/gates.py**
- **medis_touch/app/parameter_proposal/holdout.py**
- **medis_touch/app/parameter_proposal/models.py**
- **medis_touch/app/parameter_proposal/multiple_testing.py**
- **medis_touch/app/parameter_proposal/objective.py**
- **medis_touch/app/parameter_proposal/paired_stats.py**
- **medis_touch/app/parameter_proposal/proposer.py**
- **medis_touch/app/parameter_proposal/registry.py**
- **medis_touch/app/parameter_proposal/robustness.py**
- **medis_touch/app/parameter_proposal/search_budget.py**
- **medis_touch/app/parameter_proposal/statistics.py**
- **medis_touch/app/parameter_proposal/versioning.py**
- **medis_touch/app/parameter_proposal/walk_forward.py**
- **medis_touch/tests/test_parameter_deployment.py**
- **medis_touch/tests/test_parameter_evaluator.py**
- **medis_touch/tests/test_parameter_proposal.py**
- **medis_touch/tests/test_parameter_validation_pipeline.py**
- **telegram-bridge/app/config_routes.py**
- **telegram-bridge/app/control_plane.py**
- **telegram-bridge/app/copy_routes.py**
- **telegram-bridge/app/copy_settings.py**
- **telegram-bridge/app/deployment.py**
- **telegram-bridge/app/payment_models.py**
- **telegram-bridge/app/research/__init__.py**
- **telegram-bridge/app/research/books.py**
- **telegram-bridge/app/research/contracts.py**
- **telegram-bridge/app/research/execution_service.py**
- **telegram-bridge/app/research/portfolio.py**
- **telegram-bridge/app/research/promotion.py**
- **telegram-bridge/app/research/validation.py**
- **telegram-bridge/app/research_routes.py**
- **telegram-bridge/migrations/versions/0007_parameter_config_registry.py**
- **telegram-bridge/migrations/versions/0008_subscribers_and_payments.py**
- **telegram-bridge/migrations/versions/0009_research_execution_portfolio.py**
- **telegram-bridge/tests/test_imports.py**
- **telegram-bridge/tests/test_research_engine.py**
- **tools/validate_mql5_structure.py**

## Appendix 2 — all shared paths with changed content (82)

These exact-path deltas were identified by blob SHA. The list does not imply every line has already received a full semantic diff.

- **.gitignore**
- **EA/MedisTouch_Indicator_v2.8.mq5**
- **EA/MedisTouch_v2.8.mq5**
- **EA/README.md**
- **EA/includes/Analysis/Scoring.mqh**
- **EA/includes/Core/CandleData.mqh**
- **EA/includes/Core/Config.mqh**
- **EA/includes/Core/SignalLogger.mqh**
- **EA/includes/Decision/DecisionEngine.mqh**
- **EA/includes/Decision/DecisionStore.mqh**
- **EA/includes/Decision/TradeDecision.mqh**
- **EA/includes/Execution/BrokerAdapter.mqh**
- **EA/includes/Execution/OrderManager.mqh**
- **EA/includes/Execution/PositionManager.mqh**
- **EA/includes/Portfolio/PortfolioManager.mqh**
- **EA/includes/Portfolio/RiskGuard.mqh**
- **EA/includes/Recovery/RecoveryEngine.mqh**
- **EA/includes/Signals/ConfigSync.mqh**
- **EA/includes/Signals/SignalPublisher.mqh**
- **EA/includes/SmartMoney/ExtendedKeyLevels.mqh**
- **EA/includes/SmartMoney/FVG.mqh**
- **EA/includes/SmartMoney/FibonacciEngine.mqh**
- **EA/includes/SmartMoney/ValueAreaEngine.mqh**
- **EA/includes/Strategies/StrategySelector.mqh**
- **EA/includes/StrategySelector.mqh**
- **EA/includes/Structure/BOS.mqh**
- **EA/includes/Structure/CHOCH.mqh**
- **EA/includes/Structure/SwingDetector.mqh**
- **EA/includes/Trading/CalibrationEngine.mqh**
- **EA/includes/Trading/OutcomeTracker.mqh**
- **EA/includes/Trading/RiskEngine.mqh**
- **EA/includes/Trading/TradeZone.mqh**
- **EA/includes/UI/Dashboard.mqh**
- **README.md**
- **docs/CHANGELOG.md**
- **medis_touch/app/copy_trading.py**
- **medis_touch/app/execution_validation.py**
- **medis_touch/app/latency.py**
- **medis_touch/app/payments/ammer_pay.py**
- **medis_touch/mql5/Include/MedisTouch/TradeSetup.mqh**
- **render.yaml**
- **telegram-bridge/.dockerignore**
- **telegram-bridge/.env.example**
- **telegram-bridge/Dockerfile**
- **telegram-bridge/README.md**
- **telegram-bridge/app/__init__.py**
- **telegram-bridge/app/bot.py**
- **telegram-bridge/app/bot_handlers.py**
- **telegram-bridge/app/bot_promotions.py**
- **telegram-bridge/app/calibration.py**
- **telegram-bridge/app/config.py**
- **telegram-bridge/app/config_registry.py**
- **telegram-bridge/app/copy_trading.py**
- **telegram-bridge/app/copytrading_admin.py**
- **telegram-bridge/app/database.py**
- **telegram-bridge/app/formatter.py**
- **telegram-bridge/app/group_enforcement.py**
- **telegram-bridge/app/main.py**
- **telegram-bridge/app/models.py**
- **telegram-bridge/app/payments_bot.py**
- **telegram-bridge/app/routes.py**
- **telegram-bridge/app/settings_store.py**
- **telegram-bridge/app/subscriptions.py**
- **telegram-bridge/app/telegram.py**
- **telegram-bridge/app/validator.py**
- **telegram-bridge/migrations/env.py**
- **telegram-bridge/pyproject.toml**
- **telegram-bridge/scripts/render_sync_secrets.py**
- **telegram-bridge/tests/conftest.py**
- **telegram-bridge/tests/test_routes.py**
- **telegram-bridge/tests/test_settings_store.py**
- **telegram-bridge/tests/test_trade.py**
- **telegram-bridge/tests/test_validator.py**
- **tools/calibration_matrix.py**
- **tools/gating.py**
- **tools/metrics_engine.py**
- **tools/tests/conftest.py**
- **tools/tests/test_gating.py**
- **tools/tests/test_metrics_engine.py**
- **tools/tests/test_walk_forward.py**
- **tools/validate_mql5.py**
- **tools/walk_forward.py**

## Appendix 3 — selected target-only architecture to preserve

- **EA/includes/Decision/DecisionFingerprint.mqh**
- **EA/includes/Execution/DynamicStopEngine.mqh**
- **EA/includes/Execution/DynamicStopInputs.mqh**
- **EA/includes/Execution/ExecutionAudit.mqh**
- **EA/includes/Monitoring/SLModificationAudit.mqh**
- **EA/includes/Portfolio/EnvironmentPolicy.mqh**
- **EA/includes/Portfolio/MultiTradeEngine.mqh**
- **EA/includes/Signals/ConfigSyncContract.mqh**
- **EA/includes/Trading/DailyTradeTarget.mqh**
- **EA/includes/Trading/EnvironmentStrategyMemory.mqh**
- **EA/includes/Trading/OutcomeTrackerLive.mqh**
- **EA/includes/Trading/StrategySetupBuilders.mqh**
- **EA/includes/Trading/StrategyTradeZone.mqh**
- **EA/includes/UI/TradeControlPanel.mqh**
- **docs/ADAPTIVE_BACKTEST_PROTOCOL.md**
- **docs/CONTINUOUS_LEARNING_CONTRACT.md**
- **docs/DECISION_RESEARCH_CERTIFICATION.md**
- **docs/DURABLE_EXECUTION_RECOVERY.md**
- **medis_touch/app/adaptive_research.py**
- **medis_touch/app/execution_coordinator.py**
- **medis_touch/app/execution_recovery.py**
- **medis_touch/app/prediction_governance.py**
- **medis_touch/app/pretrade_risk.py**
- **medis_touch/app/strategy_pipeline.py**
- **telegram-bridge/app/api/backtest_evidence.py**
- **telegram-bridge/app/api/config_sync.py**
- **telegram-bridge/app/api/environment_outcomes.py**
- **telegram-bridge/app/signal_outbox.py**

## Merge decision

Do not merge a functional migration yet. Keep this review PR open as an audit record. Recommended implementation order: (1) Midas-native correlation/factor risk controls with explicit fail-closed data-quality behavior; (2) adapted durable bridge research/execution control-plane with a new migration; (3) bounded parameter-proposal integration only after actual EA replay and EA-side activation/rollback are wired and tested. Preserve Midas-specific execution, lifecycle, evidence, risk and fail-closed config behavior throughout.