# Order-Flow Diagnostics: Deterministic Test Plan

Status: specification only. No test in this document is claimed to have run.

## Scope

Test `EA/includes/Analysis/OrderFlowDiagnostics.mqh` as a diagnostic utility. Passing these tests does not prove a profitable trading edge. The EA input `InpEnableOrderFlowDiagnostics` must remain false until compile and runtime verification are complete. When enabled, the EA synchronously reads tick history, prints diagnostics, and appends a CSV row before ordinary setup evaluation; that adds I/O latency and may affect live fill timing even though it does not feed the diagnostic fields into setup selection.

## Evidence export and exact attribution

When diagnostics are enabled, the EA appends per-closed-bar records to `MedisTouch_OrderFlowEvidence_v3_<symbol>_<timeframe>.csv` in the terminal file sandbox. Missing bar/tick history and invalid windows receive explicit status records, allowing the usable-evidence fraction to be reported rather than silently omitting them. It writes a deterministic event key plus bar boundary epochs and proxy features. Use `tools/order_flow_research.py` to join these events to `MedisTouch_Signals_<symbol>.csv` and `MedisTouch_Outcomes_v2_<symbol>.csv`. Preferred mode is exact `SignalID` → event-key attribution via `MedisTouch_OrderFlowAttribution_v2_<symbol>_<timeframe>.csv`; pass it with `--attribution`. Attribution v2 also stores the router decision ID and fingerprint; the analyzer still accepts historical v1 files. When that file is supplied, missing, invalid, or stale links are rejected and the analyzer must not fall back to nearest-time matching. Time-based nearest-prior-bar matching is a separately reported fallback only when no attribution file is supplied; it requires exact symbol/timeframe, a bar boundary no later than signal time, and a bounded gap. The default gap is one bar duration for recognized timeframes; unknown timeframes require an explicit positive override. Review direct-link coverage, fallback mode, match/rejection counts, and usable-data rates before interpreting metrics. Review match and rejection counts before interpreting metrics. Existing rows are never rewritten. Restart duplicates with conflicting values are rejected rather than silently merged. Direct attribution is considered usable only if its event end is no later than signal creation and is no older than one configured FVG-timeframe bar.

## Unit-test seam

The `Analyze` method accepts a chronological `MqlTick[]`, count, prior range, completed-bar OHLC, ATR, output snapshot, and an optional evaluation timestamp. Production passes the end boundary of the closed evidence window. Build a small MQL5 test harness or script that constructs deterministic ticks. If the compiler/test framework cannot construct the required structures cleanly, extract pure calculations into a testable helper without changing production trade decisions.

For all fixtures, ticks must have valid positive bid/ask, ask >= bid, valid timestamps, and known chronological order unless the case intentionally tests invalid input.

## Required cases

| ID | Fixture | Expected result |
|---|---|---|
| OF-001 | Fewer than configured minimum valid ticks | `Analyze` returns false; quality unavailable; no signal flags |
| OF-002 | At least minimum ticks, all mids unchanged | Returns true; pressure ratio 0; signed pressure 0 |
| OF-003 | More upward than downward midpoint changes | Positive pressure ratio |
| OF-004 | More downward than upward midpoint changes | Negative pressure ratio |
| OF-005 | Equal upward/downward midpoint changes | Pressure ratio 0 |
| OF-006 | Invalid bid, invalid ask, ask < bid, or timestamp <= 0 mixed into valid series | Invalid rows ignored; succeeds only if enough valid ticks remain |
| OF-007 | Tick timestamps move backward | Returns false; caller logs rejected data; no trading effect |
| OF-008 | ATR <= 0 or priorHigh <= priorLow | Returns false |
| OF-009 | Completed bar low below prior low and close above prior low | Bullish sweep/reclaim true |
| OF-010 | Completed bar high above prior high and close below prior high | Bearish sweep/reclaim true |
| OF-011 | Sweep without close back across the reference level | Corresponding reclaim false |
| OF-012 | Large price progress with strong directional pressure | Absorption proxy false unless other explicit conditions independently satisfy its rule |
| OF-013 | Small price progress + strong pressure near prior range edge | Absorption proxy may flag; assert only exact documented heuristic, not actual absorption |
| OF-014 | Bar range >= 2 ATR and absolute pressure < 0.20 | Exhaustion proxy true |
| OF-015 | Bar range < 2 ATR or absolute pressure >= 0.20 | Exhaustion proxy false |
| OF-016 | Last tick older than configured threshold relative to explicit evaluation time | `data_stale` true |
| OF-017 | Last tick within configured threshold before explicit evaluation time | `data_stale` false |
| OF-030 | Replay the same historical window later using the same evaluation time | Identical stale classification |
| OF-031 | Any valid tick occurs after the supplied evaluation boundary | `Analyze` returns false; no usable evidence snapshot |
| OF-018 | Diagnostics disabled at EA level | No diagnostic CopyTicksRange call/log; signal generation and execution path remain unchanged |
| OF-019 | Diagnostics enabled with no tick history | A clear unavailable message; no trade decisions changed |
| OF-020 | Same fixture replayed twice with the same evaluation timestamp | Identical snapshot fields and log values, including stale state |

## Additional v3 cases

| ID | Fixture | Expected result |
|---|---|---|
| OF-021 | Valid POC/VAH/VAL and close below VAL | Auction context available; location is below VAL; no entry-policy effect |
| OF-022 | Invalid or low-quality value-profile source | Auction context marked unavailable; no fabricated POC/VAH/VAL conclusion |
| OF-023 | Strong midpoint tick pressure disagrees with first-to-last midpoint progress | Pressure/progress divergence tagged for research only |
| OF-024 | Close beyond a prior 20-bar level with aligned pressure | Continuation hypothesis tagged separately; no live entry effect |
| OF-025 | Sweep/reclaim with directionally aligned pressure | Reversal hypothesis tagged separately; no automatic fade |
| OF-026 | Consecutive valid bars with midpoint direction counts | UTC-day cumulative pressure is chronological and resets at day boundary or a missing-bar-sized gap |
| OF-027 | Positive cumulative tick pressure while price moves materially lower | Cumulative pressure/price divergence reported as a proxy, not true CVD |
| OF-028 | Signal attributed to a cached event older than one FVG-timeframe bar | Attribution row records `NO_USABLE_EVENT`; no stale direct link |
| OF-029 | Legacy v2 CSV and new v3 CSV are analyzed | v2 remains supported; v3 fields are validated when v3 schema is declared |

## Review risks to resolve before declaring the module tested

1. `CopyTicksRange` expects millisecond bounds. The EA helper converts `datetime` seconds to milliseconds; preserve and test that conversion.
2. Tick chronology is checked with `MqlTick.time_msc` when available, with a seconds-based fallback when millisecond timestamps are absent.
3. Data quality must remain proxy-only because the method infers midpoint direction; it must never imply exchange-quality aggressor data.
4. Production staleness is measured against the explicit closed-window end time, not the wall clock. The optional `TimeCurrent()` fallback exists only for standalone callers that do not provide an evaluation time. Future-dated ticks beyond the evaluation boundary are rejected to preserve no-look-ahead behavior.
5. `positive_tick_count` and `negative_tick_count` are counts of price-changing midpoint observations, not trade volume. Preserve these names and labels.
6. Confirm that `iHighest` / `iLowest` ranges use the intended prior 20 completed bars (starting at shift 2) and that no current/incomplete bar enters the reference range.
7. Confirm array ordering returned by `CopyTicksRange` on the supported MT5 build. The method intentionally rejects out-of-order input rather than silently sorting it.
8. Confirm include paths, class/struct syntax, `CopyTicksRange` overload, `PrintFormat` format specifiers, and warnings in MetaEditor.
9. Verify that diagnostic logs cannot alter confidence, candidate selection, position sizing, stop/target values, trailing logic, or order execution.
10. Check runtime cost for frequent new bars and large tick windows; bound the request to one closed bar as implemented.

## Integration validation sequence

1. Compile the exact EA in the target MetaEditor build; archive compiler output.
2. Run the test fixtures and preserve the test report.
3. Run Strategy Tester with diagnostics disabled and enabled on the same data. First compare decision-level outputs, setup selection, risk decisions, SL/TP calculations, and state transitions. Separately examine fill timing and tester determinism, because synchronous file I/O can affect timing on a live terminal. Any unexplained decision-path difference blocks release.
4. Run the existing baseline test suite and structural/security checks.
5. Run matched-cost backtests and ablations only after the diagnostic output is proven not to affect execution.
6. Run walk-forward and untouched out-of-sample tests.
7. Demo-forward test with logs and reconciliation.
8. Require human review before any production flag or execution policy changes.

## Release gate

Do not merge or deploy based only on this plan. Required evidence: clean compile, test outputs, zero-difference diagnostic-on/off comparison, matched-cost test results, out-of-sample evidence, and demo-forward observations.
