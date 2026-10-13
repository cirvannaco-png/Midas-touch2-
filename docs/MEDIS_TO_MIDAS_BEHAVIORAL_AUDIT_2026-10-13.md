# Medis Touch → Midas Touch 2 Behavioral Compatibility Audit
**Audit date:** 2026-10-13  
**Source:** `cirvannaco-png/Medis-Touch`  
**Target:** `cirvannaco-png/Midas-touch2-`  
**Status:** static source audit; not a certification of live execution.

## Executive result

Midas Touch 2 is not a file-for-file copy of Medis Touch, and it should not become one. Several target modules deliberately strengthen configuration immutability, evidence gates, decision/leg identity, execution costs, and recovery. Those must remain authoritative. The confirmed schema gap is now restored by the target migration chain, and PR #81 supplies authenticated compatibility APIs, but the bridge APIs are not yet wired into the authoritative MT5 order lifecycle. That is a material integration gap, not a cosmetic TODO.

## Research package: source-to-target map

| Source module | Target analogue / status | Audit disposition |
|---|---|---|
| `parameter_proposal/bounds.py` | `tools/optimizer.py` has explicit numeric bounds and steps; not proven semantically identical to source validators. | Partial equivalent; compare per-parameter constraints before porting. |
| `candidates.py` | `tools/optimizer.py`, `medis_touch/app/adaptive_research.py` | Candidate generation and adaptive SMC research exist; parity of candidate identity/deduplication not established. |
| `challenger.py` | `tools/champion_challenger.py`, `tools/recalibration_guard.py` | Strong analogue exists; keep locked-OOS, sample-size, cost-robustness and regime-stability gates. |
| `config/canonical.py`, `config/schema.py` | Configuration registry, immutable config hash and config-sync contract in target bridge/EA | Partial equivalent across separate boundaries; canonical serialization parity must be tested with shared golden vectors. |
| `deployment.py` | `tools/recalibration_guard.py` plus registry/activation controls | Partial equivalent; no evidence that source deployment state machine can be dropped in without duplicating Midas activation authority. |
| `evaluator.py` | `tools/walk_forward.py`, `tools/metrics_engine.py`, research tooling | Partial equivalent; production replay callback / real MT5 result ingestion must be demonstrated. |
| `gates.py` | `tools/gating.py`, `tools/recalibration_guard.py` | Midas's fail-closed persistent evidence requirements are stricter; preserve them. |
| `holdout.py` | `tools/oos_firewall.py`, locked holdout logic in research tools and the new research API | Partial equivalent. The new API records lock/provenance; it does not itself prove that every evaluator respects the lock. |
| `models.py` | `medis_touch/app/execution_models.py`, target bridge ORM models | Split model domains; no one-to-one schema equivalence established. |
| `multiple_testing.py` | No verified one-to-one production equivalent found in the target path reviewed | **Coverage unproven.** Need module-level behavior tests before claiming parity. |
| `objective.py` | `tools/recalibration_guard.py` composite objective | Partial equivalent; normalization is intentionally caller-owned, so objective weights and transforms require golden-vector comparison. |
| `paired_stats.py`, `statistics.py` | `tools/stats.py`, `tools/metrics_engine.py` | Partial equivalent; confidence interval, paired test and missing-data behavior need matched tests. |
| `proposer.py`, `search_budget.py` | `tools/optimizer.py` bounded deterministic proposal engine | Core bounded proposal capability exists; exact search ordering/budget parity unproven. |
| `registry.py`, `versioning.py` | Immutable target configuration registry and versioned EA decision/config lineage | Equivalent concepts, different contracts; preserve target schema and add cross-boundary hash tests. |
| `robustness.py` | `tools/recalibration_guard.py`, stress tests and execution-cost models | Partial equivalent; no assertion of complete stress-test parity. |
| `walk_forward.py` | `tools/walk_forward.py`, `medis_touch/app/walk_forward.py` | Strong functional analogue. Target tool requires provenance and rejects ambiguous exports; still needs actual MT5 Strategy Tester datasets to prove real validation. |
| Source proposal README release gates | Target research stack and CI | Source itself documents remaining integration gates; importing it wholesale would not magically complete them. |

### Research conclusion

The source's 22-file package is **not** yet demonstrated to be behaviorally equivalent in every module. Target equivalents cover much of bounded search, challenger selection, walk-forward/OOS validation, immutable registry, execution-cost measurement, and risk-governed activation. The specific gaps requiring focused parity tests are multiple-testing correction, paired-statistics semantics, canonical configuration golden vectors, and proof that the locked-OOS restriction is enforced end-to-end by the real evaluation/activation path.

## Execution and recovery audit

| Behavior | Midas target finding | Status |
|---|---|---|
| Decision/leg identity | Target `OrderManager.mqh` identifies decision + leg; `RecoveryEngine.mqh` parses `MT#<decision>:L<leg>`; target DecisionStore persists leg metadata. | Preserve target implementation. |
| Restart recovery of currently open positions | EA recovery scans matching symbol/magic open positions and restores those with parseable decision comments and a local DecisionStore record. | Partial. It is not account-wide broker/ledger reconciliation. |
| Positions with unknown/missing local decision | Recovery logs and skips a position if the decision is not found or the comment is not parseable. | **Unresolved discrepancy**; skipping is not proof of safe reconciliation. New entries must remain blocked until unknown exposure is classified. |
| Duplicate fills / duplicate transaction delivery | Local order manager prevents duplicate decision+leg submission in its in-memory collection; durable bridge API has request idempotency. | Partial; not yet proven end-to-end across EA restart, broker deal replay and bridge request retries. |
| Partial closes | Target recovery infers a runner when current volume is below submitted volume; live outcome tracker records close outcomes. | Partial; this is not a durable, idempotent per-deal ledger proving every partial close and commission/swap/fee. |
| Broker/database disagreements | Python source includes a reconciliation helper that freezes on unknown broker state, but the target EA/bridge flow does not yet invoke the new execution-ledger APIs from its broker lifecycle. | **Not integrated / not proven.** |
| Ambiguous send timeout | New bridge service retains reservation in recovery rather than assuming rejection. | Bridge-side safeguard exists; MT5 caller integration and fault-injection tests are missing. |
| Broker deal identity | Target stores local execution ticket and parses position identity; execution ledger has broker order/deal/position fields. | Partial until transaction callbacks and startup snapshots populate and reconcile those fields. |

## Portfolio-risk audit

- The target EA's `PortfolioManager.mqh` performs batch admission, symbol/group position-count checks, and fail-closed open-risk calculation; `MultiTradeEngine.mqh` plans multiple legs; `RiskGuard.mqh` applies account drawdown/daily-loss policies. Preserve these target-specific controls.
- The source `PortfolioRiskEngine.mqh` is not directly included by the inspected EA facade. Its absence at the same path does not prove the capability is absent.
- The target Python stack includes `portfolio_risk.py` (notional concentration/factor exposure) and `pretrade_risk.py` (risk gates and persistent admission). These are not yet proven to be the same risk domain or connected to the MT5 EA's actual order path.
- PR #81's bridge reservation API applies a portfolio-scoped 3R normalized-heat cap. That is a second control plane until an explicit mapping converts EA cash risk into normalized R, defines portfolio/account identity, and reconciles broker positions into the reservation book. Do not enable it as authoritative live risk without that mapping and tests.
- Existing Midas portfolio controls should not be replaced with source logic. Reconcile risk units and portfolio scope first; otherwise two individually reasonable caps can disagree or double-count exposure.

## New bridge API integration boundary

PR #81 provides authenticated `POST /execution-ledger/reserve`, `POST /execution-ledger/transition`, and lease recovery, plus authenticated research provenance endpoints. CI proves bridge-level tests and schema migration behavior only. The API explicitly does not send, cancel, or retry broker orders.

**The EA does not yet call these endpoints at the authoritative `g_orders.Submit(...)` boundary or from `OnTradeTransaction`.** Therefore it is not yet safe to claim:
- reservations are acquired atomically before every market/limit order;
- broker acknowledgements/fills are correlated to the same durable request ID;
- partial-close deals are recorded idempotently;
- startup compares the full account broker snapshot with ledger reservations;
- broker/database conflicts freeze new entries until reconciled.

This boundary requires a durable broker-event ingestion contract (stable event/deal identity, cumulative fill quantity, partial-close accounting, and explicit terminal reconciliation) before a complete EA integration. A simple synchronous preflight POST alone would not prove recovery correctness.

## Validation evidence and limits

- Latest observed GitHub Actions run for PR #81: run `38359317052`, commit `951f586eaaae4b506c203dc77e785dbdbdcb76ea`, **success**. It includes bridge Python tests, PostgreSQL migration upgrade/downgrade/re-upgrade, research-tool tests, static MQL5 structural validation, handbook tests, and bridge quality/security checks.
- Earlier run `38358829295` failed because the branch had two migrations both identified as revision `0018`; this was fixed by sequencing portfolio scoping as `0019` after the existing target `0018`. The latest successful run includes that fix.
- CI's MQL5 structural validator is **not** MetaEditor compilation.
- No MetaEditor compile, MT5 Strategy Tester run, demo-broker execution, or broker-account startup/restart fault-injection test has been run or established by these results.

## Release decision

Keep PR #81 unmerged. The bridge schema/API work is CI-green, but full behavioral compatibility and live execution readiness remain unproven until the broker-event contract, EA order-path integration, account-wide reconciliation, and real MT5 validation are implemented and evidenced.
