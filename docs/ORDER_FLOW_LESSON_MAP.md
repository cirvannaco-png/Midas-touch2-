# Order-Flow Lesson Map: Sources → Hypotheses → Tests

Status: educational source register and implementation map. Nothing here is a profitability claim or a live-trading recommendation.

## Evidence rule

Educator material is a source of hypotheses, not proof of edge. Record what the source directly demonstrates, what data it uses, and which parts Midas-touch2 can actually observe. Never convert language such as “institutional buying,” “stop hunt,” “iceberg,” “spoofing,” or “true delta” into a system label without the supporting data feed.

## Source register

| Source ID | Source and exact lesson/page | Grade | Useful lesson | Transfer limitation |
|---|---|---|---|---|
| OF-SRC-001 | Jigsaw Trading, [Free Order Flow Analysis Lessons](https://www.jigsawtrading.com/free-order-flow-analysis-lessons/) — Lessons 5 (Summary Tape), 7 (Depth & Sales), 8 (Cumulative Delta), 10 (Iceberg Orders) | B | Distinguish tape/executions, order-book depth, cumulative delta and hidden-liquidity hypotheses | These concepts rely on order-flow-specific feeds/tools. OTC MT5 quote ticks are not equivalent to exchange executions or a consolidated order book. |
| OF-SRC-002 | Jigsaw Trading, [Order Flow Absorption & Market Reversals by Axia Futures](https://www.jigsawtrading.com/blog/order-flow-absorption-market-reversals/) (2018-08-01; Richard Bailey / Axia Futures video hosted on Jigsaw) | B | Pressure can persist while price fails to progress; waiting for follow-through is different from trying to pick the exact high/low | The demonstrated exchange-futures example contains depth/executed-volume context not available from ordinary MT5 FX/CFD ticks. |
| OF-SRC-003 | Jigsaw Trading, [How to Learn Order Flow the Right Way](https://www.jigsawtrading.com/blog/how-to-learn-order-flow-the-right-way/) (2025-07-07) | B | Learn one context/skill at a time; compare pullbacks with trend continuation; use replay drills | Educational guidance is not a statistical proof that a pattern is profitable. |
| OF-SRC-004 | CME Group, [The Importance of Depth (Volume)](https://www.cmegroup.com/education/courses/introduction-to-equity-index-products/the-importance-of-depth-volume) | A | Depth, traded activity and execution impact are distinct; liquidity varies | CME futures/equity-index material is not an Exness OTC FX feed specification. |
| OF-SRC-005 | CME Group, [What Is Volume?](https://www.cmegroup.com/education/courses/introduction-to-futures/what-is-volume) | A | Futures volume counts contracts traded; volume is not merely the count of price updates | Broker tick volume and midpoint changes must not be relabelled as contracts traded. |
| OF-SRC-006 | Larry Harris, *Trading and Exchanges: Market Microstructure for Practitioners*, Oxford University Press (2002), [publisher page](https://academic.oup.com/book/52292) | A | Market mechanics, order types, participants and transaction costs | A conceptual foundation, not a ready-made signal or a claim of strategy profitability. |
| OF-SRC-007 | Ernest P. Chan, *Algorithmic Trading: Winning Strategies and Their Rationale*, Wiley, [publisher page](https://www.wiley.com/en-us/algorithmic-trading-winning-strategies-and-their-rationale-p-9781118676998) | B | Formalize hypotheses; account for costs and implementation risk; validate against controls | Results from a book cannot substitute for matched tests on our instruments and broker data. |
| OF-SRC-008 | Axia Futures, [Trading with Order Flow](https://axiafutures.com/course/trading-with-order-flow/) and [The Footprint Edge](https://axiafutures.com/course/the-footprint-edge-course/) | B | Auctioning, market velocity, absorption, failed breaks, imbalances, breakouts and replay | Course summaries are topic maps; each rule still needs its exact lesson and timestamp captured before attributing a specific implementation to it. |

The term “Axia Fusio” is not established by the sources above. The identified educator brand is **Axia Futures**. Do not attribute lessons to “Axia Fusio” unless the exact channel/video is supplied or independently verified.

## Translation into Midas-touch2 hypotheses

| Hypothesis ID | Source(s) | Observable rule in this codebase | Test requirement | Production status |
|---|---|---|---|---|
| OF-H01 Tick pressure | OF-SRC-001, OF-SRC-005 | Count upward/downward midpoint changes, with explicit proxy-only data quality | Compare against a suitable actual bid/ask execution feed where available; test by symbol/session/regime | Diagnostic only; not true executed volume |
| OF-H02 Pressure vs price progress | OF-SRC-002 | Tag disagreement between signed tick-direction pressure and midpoint progress | Predefine level/context and confirmation window; compare incremental value against the unchanged baseline | Diagnostic only |
| OF-H03 Sweep and reclaim | OF-SRC-002, OF-SRC-008 | Use completed-bar OHLC relative to a prior range to tag a possible sweep/reclaim | Test balanced vs strong-trend regimes, both directions; prevent hindsight/repaint | Diagnostic hypothesis only |
| OF-H04 Absorption proxy | OF-SRC-002 | Strong tick-direction proxy + limited price progress near a prior range edge | Verify proxy false-positive rates against execution/depth data where possible; do not call it true absorption otherwise | Diagnostic proxy only |
| OF-H05 Exhaustion proxy | OF-SRC-001, OF-SRC-003 | Extended completed bar with weak tick-direction pressure | Separate reversal from continuation outcomes; measure after costs | Diagnostic proxy only |
| OF-H06 Continuation vs reversal | OF-SRC-003, OF-SRC-008 | Keep breakout continuation tags separate from sweep/reclaim reversal tags | Independent ablation and locked chronological holdout; test long/short and multiple regimes | No gate or score change |
| OF-H07 Auction context | OF-SRC-004, OF-SRC-005 | Attach existing POC/VAH/VAL, source-quality and price-location context | Preserve source/timezone/session and distinguish exchange volume from broker tick-volume profiles | Context only |
| OF-H08 DOM/iceberg/spoofing | OF-SRC-001, OF-SRC-004 | No production inference from current feed | Requires a suitable, time-stamped Level-2 feed and evidence of executions/cancellations; define spoofing carefully | Not implemented; fail closed |

## Required experiment protocol

1. Freeze the hypothesis, thresholds, instrument, timeframe, session/timezone, entry/invalidation/exit, data source, and risk policy before looking at holdout outcomes.
2. Use exact SignalID → event_key → decision_id/fingerprint lineage from the current v3 attribution export, including SMC inducement/liquidity/BOS context. The analyzer retains v1/v2 compatibility. Report unmatched, stale, invalid, duplicate and conflicting rows; do not quietly fall back to a nearest-time match when a supplied attribution row is missing or invalid.
3. Compare diagnostic-disabled baseline and diagnostic-enabled recording on identical recorded input. They must generate identical trade decisions, confidence, sizing, SL/TP, trailing-stop and execution/ledger behavior.
4. For any future candidate entry gate, use costs-inclusive matched testing (spread, commissions, swap/financing, slippage and broker constraints), chronological walk-forward, a locked out-of-sample period and uncertainty intervals.
5. Require Exness demo forward evidence and broker/database reconciliation before review for any promotion. Keep diagnostics disabled by default until this is complete.

## Current code status

The canonical MQL5 diagnostics module tags midpoint tick pressure, sweep/reclaim, absorption/exhaustion proxies, pressure/progress divergence, continuation/reversal hypotheses, and existing value-area context. The production EA passes the closed evidence-window boundary into the module, so stale classification can be replayed deterministically and ticks after the boundary are rejected. These tags remain diagnostic-only and do not establish an edge.

The existence of these sources or features does not establish profitability. The source register should be extended only with traceable book editions, lesson URLs and timestamps; social clips without reconstructable context are anecdotal until independently tested.
