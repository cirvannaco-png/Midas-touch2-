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
| `tools/gating.py` and `tools/metrics_engine.py` | Same paths differ. Midas gating is fail-closed on missing evidence and has explicit persistence requirements; metrics keep signal coverage separate from realized expectancy. | Do not wholesale replace. Any future change must be a small semantic patch with matched tests and evidence provenance. |
| `telegram-bridge/app/research/*` and `telegram-bridge/app/research_routes.py` | Source contains a broker-neutral research package and authenticated research/execution routes; these source paths are absent in target. Midas already has separate adaptive research, pre-trade risk, execution-recovery and research tooling, so a direct copy risks duplicate control paths. | This PR restores the missing durable schema only. The API/service layer remains an explicit follow-up, requiring an integration design and tests before enabling broker-facing calls. |

## Validation in this PR

- ORM metadata tests assert all seven restored tables and critical idempotency, lease, broker-reference, holdout, and outcome fields.
- Tests assert the new tables coexist with Midas-specific `signal_delivery_outbox`, configuration registry, configuration evaluation, and config-sync state models.
- Migration ancestry is checked as `0017 → 0016`.
- GitHub Actions runs Python tests, research-tool tests, handbook tests, MQL5 structural validation, and bridge lint/security. Results must be green before merge.
- These checks do **not** substitute for applying the Alembic migration to a disposable PostgreSQL database, MetaEditor compilation, MT5 Strategy Tester, demo forward testing, or broker reconciliation.

## Non-negotiable migration rule

A missing filename is only a lead, not proof of a missing feature. Preserve Midas-specific execution state, partial-fill handling, decision/leg lineage, immutable configuration, outcome provenance, and signal delivery. Migrate only a behavior that is both genuinely absent and compatible with Midas's current call graph; add regression tests for the behavior before merge.
