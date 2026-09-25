# Midas Touch Architecture Audit — 2026-09-25

## Scope

Repository: `cirvannaco-png/Midas-touch2-`

Baseline audited: `main` at `b894506a2bfe819ac7d718a84854e9b33014763d`

Audit branch: `audit/midas-touch-deep-hardening-20260925`

The audit covers the MQL5 EA, MQL5 include graph, Python governance/research tooling, GitHub Actions, and GitLab CI contracts.

## Defects fixed

1. **Duplicate decision authority**
   - `EA/includes/Trading/TradeZone.mqh` and `StrategyTradeZone.mqh` both defined `CTradeDecision`.
   - `StrategyTradeZone.mqh` is now the sole authoritative implementation.
   - `TradeZone.mqh` remains as a compatibility shim that forwards to `StrategyTradeZone.mqh`.

2. **Legacy architectural coupling**
   - RiskEngine, Dashboard, Visuals, and the indicator were consuming the legacy TradeZone header.
   - Core consumers now reference the authoritative strategy header.
   - RiskEngine no longer depends on the compatibility shim.

3. **Implicit dependency**
   - OrderManager used `CProductionMonitor` without declaring the header that owns it.
   - The ProductionMonitor include is now explicit.

4. **Malformed confidence/calibration inputs**
   - Multi-trade planning now rejects non-finite and out-of-range confidence/probability before threshold comparisons.
   - This preserves the existing high-probability execution requirement and fails closed on malformed numeric state.

5. **Decision ID interface mismatch**
   - `CDecisionEngine` declared `SeedNextId()` and the EA invoked it, but the implementation was absent.
   - The implementation now clamps the next ID to a valid positive value.

6. **Governance coverage gaps**
   - Added static MQL5 architecture validation for include resolution, case mismatches, duplicate type definitions, include cycles, interface arity, decision-authority boundaries, multi-trade gates, and execution ordering.
   - Added repository-wide Python bytecode compilation to CI.
   - Updated strategy-lineage and production-invariant tests to reflect the authoritative header.

## Migration contract

Existing consumers that still include `TradeZone.mqh` remain source-compatible through the shim. New code must include `StrategyTradeZone.mqh` directly.

No trading-strategy thresholds or execution ordering were intentionally changed by this audit.

## Verification

The MQL5 structural validator currently reports:
- 76 MQL5 source files
- 219 includes resolved
- 0 include cycles
- architecture/interface validation clean
- edge-lineage validation clean

Python bytecode compilation passed in CI.

A native MetaEditor compilation remains required on a Windows/MetaEditor environment because MetaEditor is the authoritative MQL5 compiler; Linux CI performs static structural validation instead.

## External synchronization blocker

The repository's GitHub-to-GitLab synchronization is currently blocked by the existing `GITLAB_SYNC_TOKEN` credential being rejected by GitLab. This is an infrastructure credential issue, not a source-code failure. Per repository governance, the patch should not be treated as release-complete until the synchronization credential is repaired and the GitLab pipeline is green.
