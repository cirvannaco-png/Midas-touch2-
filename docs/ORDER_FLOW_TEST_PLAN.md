# Order-Flow Diagnostics: Deterministic Test Plan

Status: specification only. No test in this document is claimed to have run.

## Scope

Test `EA/includes/Analysis/OrderFlowDiagnostics.mqh` as a diagnostic utility. Passing these tests does not prove a profitable trading edge. The EA input `InpEnableOrderFlowDiagnostics` must remain false until compile and runtime verification are complete.

## Unit-test seam

The `Analyze` method accepts a chronological `MqlTick[]`, count, prior range, completed-bar OHLC, ATR, and output snapshot. Build a small MQL5 test harness or script that constructs deterministic ticks. If the compiler/test framework cannot construct the required structures cleanly, extract pure calculations into a testable helper without changing production trade decisions.

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
| OF-016 | Last tick older than configured threshold relative to test clock | `data_stale` true |
| OF-017 | Last tick recent relative to test clock | `data_stale` false |
| OF-018 | Diagnostics disabled at EA level | No diagnostic CopyTicksRange call/log; signal generation and execution path remain unchanged |
| OF-019 | Diagnostics enabled with no tick history | A clear unavailable message; no trade decisions changed |
| OF-020 | Same fixture replayed twice | Identical snapshot fields and log values, excluding intentionally clock-relative stale state |

## Review risks to resolve before declaring the module tested

1. `CopyTicksRange` expects millisecond bounds. The EA helper converts `datetime` seconds to milliseconds; preserve and test that conversion.
2. The module validates `MqlTick.time` in seconds. If sub-second ordering matters, consider `time_msc` and define fallback behavior for brokers that omit it.
3. `OF_QUALITY_TICK_DATA` must not be used to imply exchange-quality aggressor data. Currently the diagnostic should report proxy-only quality because the method infers midpoint direction.
4. Staleness is relative to `TimeCurrent()`; Strategy Tester and live-server time behavior should be checked. A closed-bar window naturally ends before the current tick, so do not mistake ordinary bar closure for a broken feed.
5. `positive_tick_count` and `negative_tick_count` are counts of price-changing midpoint observations, not trade volume. Preserve these names and labels.
6. Confirm that `iHighest` / `iLowest` ranges use the intended prior 20 completed bars (starting at shift 2) and that no current/incomplete bar enters the reference range.
7. Confirm array ordering returned by `CopyTicksRange` on the supported MT5 build. The method intentionally rejects out-of-order input rather than silently sorting it.
8. Confirm include paths, class/struct syntax, `CopyTicksRange` overload, `PrintFormat` format specifiers, and warnings in MetaEditor.
9. Verify that diagnostic logs cannot alter confidence, candidate selection, position sizing, stop/target values, trailing logic, or order execution.
10. Check runtime cost for frequent new bars and large tick windows; bound the request to one closed bar as implemented.

## Integration validation sequence

1. Compile the exact EA in the target MetaEditor build; archive compiler output.
2. Run the test fixtures and preserve the test report.
3. Run Strategy Tester with diagnostics disabled and enabled on the same data. Compare trade timestamps, directions, entries, exits, volumes, SL/TP, and all risk-state transitions. Differences must be zero; any unexplained difference blocks release.
4. Run the existing baseline test suite and structural/security checks.
5. Run matched-cost backtests and ablations only after the diagnostic output is proven not to affect execution.
6. Run walk-forward and untouched out-of-sample tests.
7. Demo-forward test with logs and reconciliation.
8. Require human review before any production flag or execution policy changes.

## Release gate

Do not merge or deploy based only on this plan. Required evidence: clean compile, test outputs, zero-difference diagnostic-on/off comparison, matched-cost test results, out-of-sample evidence, and demo-forward observations.
