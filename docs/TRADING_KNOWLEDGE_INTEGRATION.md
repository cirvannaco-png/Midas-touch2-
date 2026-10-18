# Midas-touch2: Trading Knowledge Integration and Evidence Governance

Status: research and test specification; not a claim of a validated profitable strategy.
Target branch: `feature/order-flow-confirmation-engine`

## Objective

Build a traceable knowledge-to-hypothesis pipeline for Midas-touch2. Books, educators, videos, academic research, broker documentation, and observed strategy results can inform hypotheses, but none may directly become a live trade rule merely because an educator presents it convincingly.

The governing loop is:

1. Capture a source and exact claim.
2. Separate observable market data from the teacher's interpretation.
3. Translate the claim into a falsifiable, deterministic hypothesis.
4. Define market, timeframe, session, entry, invalidation, exit, and risk rules before testing.
5. Test with realistic costs and no look-ahead.
6. Compare against a baseline and a simple control.
7. Validate out-of-sample and on demo forward data.
8. Enable in production only after review, with kill-switch and existing risk controls intact.

## Source registry and evidence grades

Every knowledge item should record: title, author/teacher, URL or bibliographic citation, publication date, exact lesson/page/timestamp, market/instrument, data type, extracted claim, implementation hypothesis, known caveats, test ID, and result.

- **A — primary/technical:** exchange or broker data specifications, platform documentation, peer-reviewed or university-press market-microstructure research.
- **B — transparent educational source:** books and educator material that clearly explains method and examples, but does not establish general profitability.
- **C — anecdotal:** social clips, testimonials, screenshots, discretionary trade recaps, unverified performance claims.
- **D — unverified:** missing source, unclear attribution, edited context, or claims that cannot be reconstructed.

Evidence grade applies to the source's support for a claim, not to the strategy's profitability. A high-quality source still requires strategy testing.

## Initial source library

### Market microstructure and execution

- Larry Harris, *Trading and Exchanges: Market Microstructure for Practitioners*, Oxford University Press (2002). Use for market participants, order types, market structure, trading costs, and the distinction between market mechanics and trader narratives.
  - https://academic.oup.com/book/52292
- *Market Liquidity: Theory, Evidence, and Policy*, Oxford University Press. Use to frame liquidity, price discovery, heterogeneous participants, and why order flow contains both information and noise.
  - https://academic.oup.com/book/12230
- Irene Aldridge (ed.), *High-Frequency Trading*, chapter “Market Microstructure, Orders, and Limit Order Books.” Use as a technical reference for order types and limit-order-book mechanics.
  - https://onlinelibrary.wiley.com/doi/abs/10.1002/9781119203803.ch3

### Systematic trading validation and price-action research

- Ernest P. Chan, *Algorithmic Trading: Winning Strategies and Their Rationale*, Wiley. Use for systematic hypothesis formation, backtesting design, mean reversion/momentum research, and implementation costs. It is a research-method source, not proof that any candidate strategy will remain profitable.
  - https://www.wiley.com/en-us/algorithmic-trading-winning-strategies-and-their-rationale-p-9781118676998
- Adam Grimes, *The Art and Science of Technical Analysis: Market Structure, Price Action, and Trading Strategies*, Wiley. Use to challenge pattern assumptions and require statistical validation across market conditions.
  - https://onlinelibrary.wiley.com/doi/book/10.1002/9781119202837
- Jigsaw Trading, Order Flow Foundations and educational videos. Use as a second educator perspective on ladder/footprint interpretation and trade management. Distinguish platform-specific tools and exchange-traded futures examples from the data available on the target MT5 broker feed.
  - https://www.jigsawtrading.com/education-jigsaw-professional-trading-education/

### Order-flow educators and videos

- Axia Futures, *Trading with Price Ladder and Order Flow Strategies*: topics include auctioning and market velocity, absorption, large orders, failed breaks, imbalances, momentum breakouts, and replay drills.
  - https://axiafutures.com/course/trading-with-order-flow/
- Axia Futures, *The Footprint Edge Course*: topics include absorption and auctioning, failed support/resistance breaks, auction imbalances, exhaustion, initiative drives, auction reversals, and risk-event trading.
  - https://axiafutures.com/course/the-footprint-edge-course/
- Axia Futures, *Footprint Strategies You Can Apply in Your Trading*: use as an educational source for footprint examples, not as proof that a setup generalizes to spot FX/CFDs.
  - https://axiafutures.com/blog/footprint-strategies-you-can-apply-in-your-trading/
- José Luis Rodríguez, *ORDER FLOW — Market Mechanics* (2026). Potential reference for footprint, delta/CVD, absorption, spoofing, imbalances, and volume profile. Verify each edition and its data assumptions before coding.
  - https://orderflow.ing/en/

The exact “Axiu Fusio” / “Axia Fusio” creator attribution remains unverified. Do not attribute a lesson to a similarly named teacher unless the user supplies the channel/video URL or the exact source is independently confirmed.

## Translation rules for Midas-touch2

### 1. Auction context before trigger

Classify the market regime using only data available at decision time: directional expansion, balance/compression, transition, or uncertain. Use higher-timeframe context (D1/H4/H1) and lower-timeframe execution (M30/M15/M5/M1) as a hierarchy, not as six independent votes. Define conflict resolution explicitly; do not count correlated timeframes as independent evidence.

### 2. Sweep and failed-break hypotheses

A sweep is not automatically a reversal. Define the reference level, penetration distance, close-back-inside condition, confirmation window, and invalidation. Test separately:
- sweep + reclaim in a balanced regime;
- sweep + reclaim against a strong directional regime;
- breakout + acceptance beyond the level;
- breakout failure without a confirmed reclaim.

### 3. Absorption and exhaustion

True absorption requires evidence of aggressive executed volume meeting passive liquidity with limited price progress. Exhaustion requires a defined decline in initiative/participation and a price response. OHLC candles and tick-direction proxies alone cannot prove either condition. If true bid/ask executed volume or depth is unavailable, label the feature **proxy**, expose its data-quality state, and never describe it as actual footprint delta or institutional order flow.

### 4. Delta, imbalance, and CVD

Use actual bid/ask-classified executed volume only where the feed genuinely provides it. Do not relabel tick counts or broker tick volume as traded contract volume. Any delta proxy must be named accordingly and evaluated as a separate feature. Stacked imbalance needs pre-registered ratio, minimum-volume, adjacent-level, and location rules; isolated imbalances are not standalone signals.

### 5. Volume profile and auction references

POC, VAH, VAL, HVNs, and LVNs are context features, not automatic entry instructions. Record the profile source, session definition, timezone, tick size, and whether the profile uses exchange volume, broker tick volume, or another proxy. Never combine unlike volume sources as if they were equivalent.

### 6. Liquidity, stops, and market manipulation claims

A candle wick does not prove that institutional stops were hunted. A visible resting order does not prove that it will remain or execute. Do not infer spoofing, iceberg orders, or hidden institutional intent without data capable of supporting the claim. Keep such labels out of production logic unless observable and independently testable.

## Critical instrument-data constraint

Midas-touch2 commonly trades through Exness MT5 instruments, including OTC spot FX/CFD feeds. These are not a single consolidated exchange order book. Broker ticks and tick volume may be useful proxies, but cannot be treated as complete market-wide aggressor volume, centralized footprint, or exchange depth. Futures education can inspire hypotheses; it cannot be copied verbatim into an OTC feed without adapting and testing the data assumptions.

## Experiment contract

Each candidate hypothesis must have a frozen specification containing:

- Hypothesis ID and source references.
- Instrument(s), broker/feed, date range, session and timezone.
- Timeframes and exact bar/tick fields used.
- Deterministic signal, entry, stop, target, trailing and time-exit rules.
- Spread, commission, slippage, swap/financing, and execution assumptions.
- Data sufficiency rules and missing/stale-data behavior.
- Baseline and ablation variants (remove one feature at a time).
- In-sample, validation, walk-forward and untouched out-of-sample periods.
- Trade count, expectancy in R and money, profit factor, max equity drawdown, MAE/MFE, loss streak, exposure, costs, and regime breakdown.
- Multiple-testing/selection-bias notes and final go/no-go decision.

Do not optimize solely for win rate or profit. Reject candidates whose apparent edge disappears under plausible cost stress, a nearby parameter range, another period, or out-of-sample data. Do not use the same period repeatedly to tune and then call it independent validation.

## Integration and safety gates

- New knowledge features remain **diagnostic-only and disabled by default** until separately validated.
- No source lesson can bypass the current risk controller, broker/account-mode checks, authenticated ledger/reconciliation, emergency stop, or restart recovery.
- Preserve the existing production trailing stop; do not silently change risk limits, sizing, SL/TP, or execution behavior.
- A feature flag is not sufficient isolation if the code path changes order decisions. Review diffs and prove unchanged behavior with deterministic baseline comparisons.
- Never enable live trading based only on a backtest, screenshots, educator claims, or a small number of trades.
- Log data quality, signal inputs, decision, rejected-trade reason, actual fill, costs, and eventual outcome so each hypothesis can be audited.

## Current implementation boundary

The branch contains a diagnostic-only order-flow proxy, version-2 per-bar evidence export with unavailable-window status rows, a separate exact SignalID-to-event attribution CSV, and the tools/order_flow_research.py analyzer. This code has not yet been compiled in MetaEditor or validated by real-tick backtests in this environment. Tick-pressure, absorption, and exhaustion labels are heuristics, not validated edge. When attribution CSV is supplied, evidence joins through exact SignalID→event-key links and does not fall back for missing links; otherwise the analyzer uses a documented nearest-prior-bar join. Match rates and rejected rows must be reviewed. The default matching window is one bar duration for known timeframes; unknown timeframes are rejected unless explicitly overridden. The report also exposes unique event counts and clusters signals sharing a feature snapshot to avoid overstating independent sample size. Diagnostics remain disabled by default; enabling them adds synchronous I/O latency and may affect live fill timing. Keep them off in live trading until MetaEditor compilation, deterministic tests, decision-path comparisons, matched-cost backtests, out-of-sample testing, and demo-forward validation are complete.

## Next implementation sequence

1. Compile the EA and included diagnostic module in the target MetaEditor build; source-level structural validation is not an MQL5 compile.
2. Run the committed Python research unit tests and the MQL5 structural validation workflow; capture the actual CI result.
3. Export sample CSVs from MT5 and validate column integrity, event match rate, stale-event rejection counts, and conflicting duplicate handling.
4. Add direct decision-ID/fingerprint attribution if nearest-prior-bar joins prove ambiguous; never loosen the join window just to increase sample size.
5. Add independently testable strategy hypotheses and ablations, then run matched-cost Strategy Tester, walk-forward, and untouched out-of-sample evaluations.
6. Conduct demo-forward validation with reconciliation and human review before considering any diagnostic feature for execution decisions.
