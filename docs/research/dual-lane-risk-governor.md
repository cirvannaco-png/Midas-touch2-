# Dual-Lane Risk Governor — Research Contract

Status: isolated research branch; nothing is merged into `main` or deployed from this branch. It contains research-only analytics plus proposed risk-engine guard changes. Merging `EA/includes/Trading/RiskEngine.mqh` changes setup rejection and lot sizing, so it requires MetaEditor compilation and MT5 tester review before any live use. Source of truth remains `EA/MedisTouch_v2.8.mq5` and `EA/includes/`.

## Target

The requested account-return target is a $10,000 starting balance, +$8,700 net profit, and $18,700 ending balance (+87%). This is a target, not a forecast or demonstrated capability. A high win rate alone is not a promotion criterion.

## Architectural responsibility boundaries

- Analysis/scoring identifies candidate setups but does not silently change order size.
- Decision policy classifies a candidate and persistently records its risk lane.
- Risk engine sizes from the executable entry to the protective stop via MT5 `OrderCalcProfit` in account currency, then rounds down to broker volume constraints. This estimate excludes gap/slippage, commission and swap.
- Portfolio governor enforces aggregate open-stop risk before a batch is submitted; unknown risk must fail closed.
- Execution/recovery must reconstruct the same lane after restart; lane state cannot exist only in memory.
- Position management owns partial exits, break-even protection, trailing stops and time exits.
- Outcome analytics groups partial closes into one position before calculating position-level metrics.

The existing CMultiTradeEngine splits one approved setup into TP1/TP2/final-target legs. That is not equivalent to two independent setup-quality lanes. Leg index must never stand in for a lane identifier.

## Proposed research policy

| Control | Lane A: core/high conviction | Lane B: opportunity/lower confidence |
|---|---:|---:|
| Risk per setup | 0.25% | 0.10% |
| Aggregate Lane B risk ceiling | Shared overall cap | 0.50% |
| Overall open risk ceiling | 2.25% | Same 2.25% |
| Daily entry ceiling | 6 | 6 |
| Daily minimum | None | None |
| Entry | Full causal SMC, displacement and FVG/retest confluence | Independently validated continuation/fallback pattern |
| Stop | Setup invalidation plus buffer | Setup invalidation plus buffer |

These are experiment defaults, not live recommendations. Gaps, liquidity and execution mean actual losses can exceed planned stop risk.

## Risk and runner invariants

1. Size against the effective stop at the executable entry, not only the prior close.
2. Sum remaining risk using each live position's current volume and effective protective stop; a trailing stop reduces risk only if active at the broker.
3. A position missing valid protection or with an uncomputable account-currency stop-loss estimate counts as unknown risk and blocks new exposure until reconciled. A verified stop at or beyond entry (long: SL >= entry; short: SL <= entry) contributes zero remaining price-stop risk, not unknown risk. Gaps and slippage can still cause losses beyond stop-defined risk.
4. Reserve the full intended order-batch risk before submitting its first leg; reconcile partial broker acceptance.
5. TP1 reduces only the configured fraction; after confirmed closure, move remaining stops to entry plus/minus the configured offset.
6. TP2 reduces its configured fraction and arms the runner trail only after confirmed closure.
7. Trailing stops must ratchet only in the profitable direction. A replacement must not create an unprotected gap.
8. Hard time exit cancels conflicting pending orders, closes remaining volume and reconciles the actual broker position.
9. State transitions must be idempotent across duplicate ticks, callbacks and restarts.
10. Daily trade count is a maximum only; the strategy must never weaken entry quality to fill a quota.
11. Active pending orders reserve portfolio risk and count against symbol/group concurrency limits. Missing or invalid protection on a pending order is unknown exposure and blocks new entries.
12. A market request without a confirmed deal must remain pending until the transaction event reconciles order to position; a request-method boolean alone is not fill confirmation.
13. Stop modification, pending-order cancellation, and close operations must check the trade-server retcode; a successful local request call is not sufficient evidence that the broker accepted the operation.

## Test design

- Instrument/timeframe: XAUUSD M15; use IC Markets data where available.
- Start balance: $10,000 USD.
- Compare long-hold against balanced exits with identical entry rules, risk caps, commissions and date ranges.
- Window A: 2026-07-01 through 2026-10-06.
- Adverse window B: 2024-10-07 through 2025-01-05.
- Report net P&L, account return, max drawdown, PF, average win/loss, position-level win rate (including and excluding breakeven), realized R, per-lane contribution, incomplete/open positions and sample size.
- Collapse all partial closes by originating position. Commission, swap and fees must be included.
- Distinguish MT5/tester tick-level equity drawdown from the closed-position settlement drawdown computed by tools/position_ledger_metrics.py.
- Do not tune the final held-out window.

## Promotion gates

A candidate is not promotable merely because one run reaches +87%. Require complete recent and adverse M15 runs, reconciled net P&L, positive post-cost expectancy and PF above 1 on the held-out adverse window, compliant drawdown, separated lane statistics, passing partial-close/break-even/trail/time-exit/rejection/recovery tests, static include validation, Python regression tests, MetaEditor compilation, MT5 tester validation, code review and demo/forward test.

## Known blocker as of 2026-10-09

StrategyTune's daily cloud-compute allowance was exhausted. LONA rejected XAUUSD M15 global data on the current Free/basic entitlement. Daily fallback reports had zero trades and do not validate the M15 strategy. Keep performance status unvalidated until suitable intraday data and complete clean runs are available.
