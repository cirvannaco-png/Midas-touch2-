# Midas-touch2 performance-target audit and promotion gates

**Audit date:** 2026-10-13  
**Audited source:** GitHub `main` at `8d81d839161fdc11ef3501562cc7fa2518e9764a`  
**Scope:** source-level review of scoring architecture, recent profitability experiments, open execution/research work, and release evidence. This is not a claim that MT5 Strategy Tester or broker-forward tests were run.

## Executive decision

Do not change live defaults to chase a 90% win rate or 600% return. Keep the current EA as the baseline, retain trailing protection enabled, and promote candidate behavior only after matched, costs-inclusive MT5 testing and locked out-of-sample validation. The objective is positive net expectancy with bounded drawdown and robust execution, not a headline win rate.

## Findings

### 1. Evidence consolidation already exists

`EA/includes/Analysis/Scoring.mqh` documents the inducement engine as the authoritative entry-timeframe source for impulse, structure, sweep, and post-sweep BOS evidence. Legacy BOS/liquidity point scorers are not summed again. Preserve this rule: do not add a new weighted SMC score that awards duplicate points for the same event.

The v2.10 multiplicative environment/execution score and confidence decay are diagnostic-only. Do not wire them into entry gating, sizing, or execution merely because the formula looks more sophisticated. First compare ranking quality and realized R on resolved trades, then validate behavioral changes on held-out data.

### 2. The latest exit research does not justify promotion

The 2026-10-13 payoff research reports inconsistent outcomes across windows: the candidate's profit factor was below 1 in development, above 1 in one inspected holdout, and below 1 in another. A stricter lane also deteriorated in the September window. The StrategyTune proxy omitted commission/slippage and was not parameter-faithful to the EA's `InpMinRiskReward` setup-admission gate versus `InpPartialAtR` partial-close trigger.

**Decision:** keep the exit candidate research-only. Do not raise the live minimum R:R or delay partial exits based on proxy results. Run a matched experiment in actual MT5 with the entry R:R floor and partial-close trigger varied independently.

### 3. Trailing stop remains enabled; measure its contribution

The EA documents `InpEnableDynamicStop=true` by default. Preserve that default. Test trailing ON and OFF on identical tick data, spread, commission, slippage, symbols, time windows, and risk settings. Compare net expectancy, profit factor, maximum equity drawdown, realized R, stop-modification failures, and average winner/loser. Do not infer that trailing always improves results or silently disable it.

### 4. Account-profile work is not production approval

Open draft PR #82 describes a `MICRO_RESEARCH` profile with an 8% nominal risk-per-trade envelope and explicitly blocks it on real-money accounts outside Strategy Tester. Treat this as a high-risk research envelope, not a recommended small-account default or production setting. Keep the PR draft until risk values, profile isolation, and restart behavior are independently reviewed and external validation gates pass. Preserve the existing `PROP_FIRM` baseline and separate small-account configuration; never let a profile switch silently alter live exposure while positions remain open.

### 5. Execution/recovery work remains a separate release gate

Open draft PR #81 documents durable execution-ledger and reconciliation work but also identifies incomplete end-to-end research promotion gates, multi-magic account aggregation/orphan detection questions, and missing MT5 Strategy Tester and selected-broker demo evidence. Green Python/structural CI does not prove broker correctness.

## Required promotion gates

A candidate may be promoted only when evidence is attached to the exact candidate commit:

1. **Source and compile:** full CI green; MetaEditor compile with zero errors and warnings; include-tree and source-contract checks pass.
2. **No look-ahead/repainting:** confirmed-bar and swing logic tested for future-bar leakage; signals remain stable after restart and historical refresh.
3. **Matched experiment:** one change at a time; baseline and candidate share data, symbols, timeframe, costs, risk, and execution assumptions.
4. **Costs-inclusive results:** commission, variable spread, swaps where applicable, and realistic slippage included. Report net P&L and account-equity drawdown, not only closed-trade balance curves.
5. **Statistics:** sample size; win rate with confidence interval; mean/median R; expectancy; profit factor; maximum equity drawdown; recovery factor; maximum consecutive losses; exposure and turnover; results by symbol, session, and regime.
6. **Robustness:** walk-forward validation, a locked out-of-sample period untouched by parameter selection, parameter-neighborhood sensitivity, and Monte Carlo trade-order resampling.
7. **Exit parity:** trailing ON/OFF comparison; test breakeven, partial close, and structural exits separately; verify actual EA trigger semantics rather than proxy parameter names.
8. **Risk/profile isolation:** automated and manual orders pass the same effective profile/risk guard; volumes round down to broker steps; invalid/uncomputable stop risk rejects the trade; aggregate and correlated exposure account for managed positions and pending orders.
9. **Recovery/accounting:** inject duplicate fills, partial closes, restarts, incomplete history, missing SL, ambiguous submissions, and broker/database disagreements. Only complete, reconciled outcomes enter training or promotion data.
10. **Demo forward validation:** use a demo account with the MT5-compatible broker selected by the operator and its actual specifications; attach evidence for startup/restart, partial fills/closes, stop modifications, and reconciliation.
11. **Promotion control:** no automatic live parameter changes. Candidate configuration remains versioned, reproducible, reviewable, and rollback-capable.

## Metric definitions and targets

- **Win rate** = profitable completed positions / all valid completed positions. Group partial exits by parent position/decision; do not count partial closes as separate wins.
- **Net expectancy** = mean realized P&L or R per completed position after costs. This is the primary performance metric, alongside drawdown and risk constraints.
- **600% return** means net profit equals six times initial capital (ending equity seven times initial capital) over a stated period. Always state the period and maximum drawdown; a target is not a forecast.
- **90% win rate** is an experimental aspiration, not a mandatory filter or proof of edge. Reject candidates whose apparent win rate depends on tiny targets, unbounded losses, or omitted costs.
- **Three successful trades per weekday** remains a measurement objective, never a quota that forces weak entries or bypasses spread, session, execution, or risk guards.

## Immediate next actions

1. Keep current `main` behavior as the reproducible baseline.
2. Finish review of the open execution-ledger and account-profile draft PRs without merging around documented blockers.
3. Re-run current main CI and MetaEditor compile; record exact commit SHAs and results.
4. Run a parameter-faithful MT5 matrix for entry R:R floor, partial-exit threshold, and trailing ON/OFF, one factor at a time.
5. Keep candidates unpromoted until all applicable gates above have evidence.

## Evidence references

- Scoring source: `EA/includes/Analysis/Scoring.mqh`
- Trailing-stop default and operational caveats: `EA/README.md`
- Payoff-asymmetry research: `docs/PROFITABILITY_ASYMMETRY_RESEARCH_FINDINGS_2026-10-13.md` on the relevant research branch
- Execution-ledger/reconciliation draft: PR #81
- Runtime account-profile draft: PR #82
- Payoff-asymmetry/exit research draft: PR #76


## Post-audit remediation status — 2026-10-13

The following source-level fixes have since been merged to `main`:

- **PR #85** — this audit and the explicit strategy-promotion gates.
- **PR #87** — removed the baked-in 87% account-return label from ledger metrics. Return targets are now optional, passed explicitly as `--target-return-pct`, and scaled to the supplied initial balance.
- **PR #90** — validated partial-close volumes against broker volume steps/minimums; corrected the weekday-success objective to count only fully closed, reconciled, positive-net positions meeting the configured realized-R threshold (default +0.25R). Entry fills no longer count as wins.
- **PR #91** — portfolio exposure now includes active pending orders, including their price, stop, current volume, per-symbol and correlation-group capacity. Missing or invalid pending-order protection fails closed. Positions with a stop at/beyond entry no longer create a false "unknown risk" block; their planned stop-price loss is zero, while gap/slippage/cost risk remains possible.

### Verified source checks

The exact source trees were tested before merge on the corresponding PR heads:

- **PR #90:** Midas Touch CI run #1068 passed all six jobs; MetaEditor run #288 reported **0 errors, 0 warnings**.
- **PR #91:** Midas Touch CI run #1074 passed all six jobs; MetaEditor run #294 reported **0 errors, 0 warnings**.
- The added regression tests cover optional return targets, broker-valid partial-close requests, complete closed-trade qualification, weekday filtering, persisted deduplication, and pending-order portfolio exposure.

These results establish source/CI and compiler readiness for those changes. They do **not** establish trading profitability or live readiness.

### Outstanding live-trading gates

As of this update, no verified evidence is attached for an actual MT5 Strategy Tester run of the EA using broker-representative ticks plus commission, variable spread, swaps, and slippage; a locked out-of-sample period; walk-forward and Monte Carlo validation; or a selected-broker demo-forward run covering startup/restart, partial fills/closes, stop modifications, and broker/database reconciliation. The repository integration does not independently prove production bridge secrets or live broker/service health.

**Release decision: compile-ready, not yet certified live-trading-ready.** Keep research/runtime candidates gated and do not infer a 90% win rate or 600% return from the green compiler/CI. Those goals require empirical evidence from the validation gates above. Keep the execution-ledger and account-profile work in draft until its outstanding reconciliation and external-validation blockers are resolved.
