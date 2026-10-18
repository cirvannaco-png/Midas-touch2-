# MT5 diagnostic parity, cost-inclusive validation, and Exness demo release gate

## Scope and current status

This protocol closes the evidence gap between source-level tests and evidence from a real MetaTrader 5 Strategy Tester and broker account. The audit deliberately does **not** infer market performance from mathematical-mode fixtures.

**Release status remains BLOCKED** until genuine terminal exports pass this protocol and the frozen candidate is reconciled on an Exness demo account. No parameter set is promoted by these tools. Green repository CI means software checks passed; it does not mean a trading edge exists.

## 1. Diagnostic OFF versus ON: use the actual controls

The EA does not expose one InpDiagnosticsMode switch. The v2.10 diagnostics are four individual inputs in EA/MedisTouch_v2.8.mq5 and are documented as diagnostic-only:

| Input | Diagnostic OFF | Diagnostic ON |
| --- | ---: | ---: |
| InpDiagContradictionWeight | 0 | 0.25 |
| InpDiagEnvWeight | 0 | 1.0 |
| InpDiagExecWeight | 0 | 1.0 |
| InpDiagDecayHalfLifeBars | 0 | 12.0 |

The OFF arm zeros the diagnostic weights and disables confidence-decay output. The ON arm uses repository defaults. Both arms must use the exact same EA source/build, symbol and broker specification, terminal build, real-tick archive, date interval, account settings, risk/execution inputs, signal/outcome logging settings, and fill model. Only these four declared diagnostic inputs may differ.

This is a **bundle ablation**: if any report differs, it tests whether enabling the diagnostic bundle changed observable trading behavior; it does not identify which individual input caused a difference. All other preset keys and MT5 optimization metadata must be identical. Do not change thresholds, confidence gates, stop/TP settings, volume/risk, sessions, strategy selection, or broker execution inputs between arms.

Diagnostic score fields are allowed to differ: ContradictionPenalty, EnvScore, ExecScore, EnvExecConfidence, and outcome telemetry ConfidenceDecayed / DecayBars. Direction, setup geometry, final policy decision/action, authorization, fills/deal economics, and outcome classification must not change merely because display/diagnostic fields changed. Any such difference blocks promotion and must be investigated.

## 2. Required evidence from each real terminal run

For each arm, save the original artifact and a separately normalized copy where needed:

- Actual MT5 input preset (.set).
- Native Strategy Tester HTML report and tester/journal log for that exact run.
- Immutable historical tick archive covering the declared period; record its SHA-256. Use real ticks where the broker's history supports them; never label generated/math-test data as real ticks.
- Exported signal CSV: MedisTouch_Signals_<SYMBOL>.csv.
- Versioned outcome CSV: MedisTouch_Outcomes_v2_<SYMBOL>.csv. Preserve explicit OutcomeEpoch, RealizedNetPnL, commission/spread/slippage fields, and fill/ambiguity flags.
- Candidate-to-decision CSV: MidasTouch_DecisionTrace_<SYMBOL>.csv, written by CDecisionTraceLogger. It links a signal ID to the resulting action and records ignored/rejected router outcomes with DecisionID=0 where no durable ID was allocated.
- Broker/tester deal-history CSV with one unique deal ticket per row; position ID, UTC time, entry/exit type, positive executed volume, price P&L, signed commission, signed swap, and signed broker fee must be explicit.
- Open-position ID CSV at the end of the tester run, even when it has header only.

The EA writes to the active terminal/Strategy Tester agent's MQL5 file area. Run OFF and ON in isolated tester-agent/data folders, or copy and checksum each file immediately after each run. The EA appends to CSVs; reusing one file set across runs contaminates the comparison. Never rename a synthetic or stale log and call it evidence from a new run.

Native MT5 exports often use broker-specific headers and time presentation. Keep originals untouched. Normalize a copy to the exact field names described by the audit and preserve a documented original-to-normalized mapping. Do not manufacture missing tickets, costs, timestamps, risk cash, or outcomes. Unknown cost values must remain unknown and block the test, not be converted to zero.

## 3. Run the diagnostic audit

From the repository root:

    python tools/audit_mt5_diagnostic_parity.py --manifest path/to/diagnostic_parity_manifest.json --output path/to/diagnostic_parity.json

The manifest schema_version is 1 and declares experiment_id, dataset_path, test_context, and exactly two runs with roles diagnostic_off and diagnostic_on. test_context must include the actual symbol/timeframe, UTC interval, locked-OOS interval, tick-archive SHA-256, EA source SHA/build and MT5 terminal build, data vendor, tester model, spread model, cost assumptions, swap/fill policy, account currency/leverage/balance, and a diagnostic_inputs object mapping each of the four inputs above to {"off": ..., "on": ...}. Each run repeats the common context, excluding diagnostic_inputs, and supplies paths for input_preset, tester_report, tester_log, signals_csv, outcomes_csv, decisions_csv, deals_csv, and open_positions_csv. See tools/audit_mt5_diagnostic_parity.py for exact accepted keys and validation rules.

The audit:
1. Verifies the tick snapshot hash and matched context.
2. Verifies paired presets differ only in the four declared diagnostic inputs.
3. Rejects known mathematical-test/no-history/no-symbol/no-tick log signatures.
4. Measures unique signal IDs, one-decision-record-per-signal coverage, signal-to-outcome attribution, and whether independent event clusters can actually be counted.
5. Compares signal/decision/outcome fields and position-level deal economics without relying on run-local ticket numbers.
6. Requires explicit finite broker commission, swap, and fee columns, and emits blockers rather than a promotion status when evidence is incomplete.

A parity audit result can at most state diagnostic_parity_verified_not_performance_certified. It is not proof of profitability, statistical independence, data quality, or broker reconciliation. Review the original native report and logs manually even if the audit passes.

## 4. Cost-inclusive matched strategy tests

Use tools/risk_trailing_experiment.py for trading performance; do not use the diagnostic parity audit as a return calculator. The strategy experiment requires five roles, actual distinct .set files, HTML reports, complete deal history, open-position lists, a shared immutable tick dataset and matching context. It rejects context/preset drift and now rejects blank cost/risk cells rather than defaulting them to zero.

    python tools/risk_trailing_experiment.py --manifest path/to/five_arm_manifest.json --output path/to/cost_wf_oos_comparison.json --simulations 2000 --seed 20261013

The five arms are the declared current baseline, trailing-off ablation, trailing candidate, tight-risk arm, and calibrated-risk arm. Respect the tool's isolation contract: trailing candidates may change only configured dynamic-stop parameters; risk arms may change only their selected risk profile. Execution-cost inputs remain identical across all arms.

### Required cost accounting

- Tester deal profit must already include actual historic entry/exit spread from the recorded tick model.
- Signed commission, swap and broker fee are summed from actual deal records.
- In analysis, apply only declared incremental spread-widening stress and additional per-deal slippage stress. Do not charge embedded historic spread a second time.
- Set spread points to null when using real ticks and the protocol permits it; do not substitute an invented fixed spread. Record baseline spread, widening multiplier, slippage points and cash value per point per lot from the exact broker/account/symbol contract specification.
- Verify commission schedule, triple-swap/holding effects, point/tick size, tick value, contract size, account currency and volume before building the manifest. A manifest declaration and SHA hash establish what was submitted, not that an incorrect declaration is true.

Report net expectancy, profit factor, position win rate, average wins/losses, drawdown, loss streaks, and baseline deltas. Compare the harness's closed-position drawdown with native MT5 balance/equity and intratrade drawdown. Permutation Monte Carlo describes sensitivity to the order of observed trades; it is not a forecast.

## 5. Chronological walk-forward and locked out-of-sample

- Declare locked_oos_start and locked_oos_end before reading results. Never use locked-OOS returns to select parameters.
- Use the tool's three sequential fixed-parameter test windows wholly before the locked-OOS boundary. Fully matured positions only count; positions that close beyond a fold cutoff are censored, not assigned fabricated wins/losses.
- Freeze the candidate/source commit, inputs, symbol/account specification and execution-cost assumptions before entering locked OOS. Do not tune after seeing results.
- Require at least 30 fully resolved locked-OOS positions and three reasonably consistent chronological forward folds before even considering a demo-forward test. Thirty observations is a minimum screening floor, not a guarantee of sufficient power; increase sample size where confidence intervals remain wide. Verify regime/session coverage and avoid overlapping or duplicate market-event observations masquerading as independent samples.
- The intended +600% net return and 87% win rate are hypotheses, not release criteria by themselves. A +600% net return means net profit equal to six times starting equity over the predeclared horizon after all costs; with no deposits or withdrawals, final equity would be seven times starting equity. “87% accuracy” is ambiguous; unless another definition is frozen in advance, report it as the proportion of completed positions with positive net P&L, with scratches shown separately. Do not conflate win rate with classifier accuracy. Show sample size, uncertainty, drawdown, expectancy and profit factor alongside both targets.

A 600% return target can incentivize catastrophic risk-taking if it is treated as a quota. Do not increase risk or weaken stop protections to force the target or a daily trade count. Keep risk caps and the production trailing-stop path enabled in the release candidate.

## 6. Exness demo-forward and broker reconciliation

Run only on the designated Exness demo account until every gate passes. Save the account/server label without secrets, terminal build, symbol suffix/specification, account margin mode, deposit currency/leverage, exact EA commit/build, exact .set, initial/final balance-equity and the time interval.

Exercise these paths deliberately and document the native evidence:
- BUY and SELL entry intent, broker acceptance/rejection, actual fill price/volume and confirmed initial SL/TP.
- Partial closes and stop modifications, including broker rejection, timeout and requote responses.
- Bridge/API/database unavailable before send: new entries remain blocked.
- Ambiguous submission timeout: retain the reservation for reconciliation; never blindly resend an uncertain order.
- Open positions, pending orders and closed history on startup/restart; replay history without duplicate fills or missing exits.
- Emergency stop: block new entries, apply the documented exposure-management action and confirm the stop latch survives terminal/EA restart.
- Commission, swaps (including applicable rollover days), broker fees, spread, slippage, volume, position IDs and all deal tickets.

Reconcile each submitted order/decision to the broker's order, deal and position history wherever the account's execution model supplies those identifiers. Match opened and closed volumes, partial fills/exits, realized cashflows, swaps, commissions and fees. Require zero unexplained missing/orphan tickets, zero unexplained volume/P&L differences, and no unknown-cost rows. Explain known rounding and broker-specific accounting conventions with evidence. Verify hedging versus netting mode explicitly: MT5 netting can aggregate same-symbol exposure from multiple sources.

Capture a timestamped reconciliation file/report and raw MT5 Journal/Experts logs. If the broker fills diverge from the tester, stop and investigate slippage, spread, request timing, volume rounding, rejected stop changes and account mode before extending the run. Demo-forward results are necessary execution evidence, not a guarantee of live performance.

## 7. Reproducible checks and release gate

Run focused tests in an environment with repository-declared Python dependencies:

    PYTHONPATH="$PWD:$PWD/telegram-bridge" pytest -q tools/tests/test_audit_mt5_diagnostic_parity.py tools/tests/test_risk_trailing_experiment.py tools/tests/test_production_invariants.py

Retain the CI run URL, exact head commit, native MetaEditor compilation result for the revised EA/include, test output, both audit JSON reports, original reports/logs, dataset digest, walk-forward/OOS results and demo reconciliation evidence with the release decision.

**Do not merge or enable live order flow while any of the following remains true:** mathematical/no-history tester mode; missing/invalid native exports; different non-diagnostic inputs between matched arms; missing explicit financial fields; incomplete attribution; behavioral diagnostic parity failure; insufficient locked-OOS samples; unstable walk-forward results; unreviewed native equity drawdown; unresolved Exness order/position/cashflow discrepancies; or failed emergency-stop/restart tests.


## 6. Auxiliary LONA / StrategyTune research findings (2026-10-18)

These are research-platform diagnostics only. They are **not** native MT5 Strategy Tester evidence, an Exness broker reconciliation, or release authorization.

### LONA daily session-gate defect and regression

- Original strategy: `d3e8d7e7-ea99-42f0-968f-6d8a9beff63d`, version 1.0.2; XAUUSD daily data; 2024-01-01 through 2024-12-31; starting balance USD 10,000; configured commission 0.0005; leverage 10.
- With `use_session_filter=true`, reports `1a6b58a9-9d6b-42af-9f7b-38f1db4c9237` and `f2f47145-6b02-431e-bb50-b6bb2da74f2b` both recorded zero trades. The code was checking an intraday UTC-hour window (07:00–21:00) on daily bars timestamped at 00:00 UTC, so it could suppress all entries.
- Diagnostic control with `use_session_filter=false`, report `45ee809b-5a12-4e41-b248-32e2ba35517d`: 27 trades, reported P&L -$8.56, 59.26% win rate, 0.82 profit factor, -$0.32 expectancy per trade, 0.50% maximum drawdown, and 7.8 average bars held.
- A first fork using the feed's internal timeframe enum (`92a76e09-3bc3-486f-afd8-b1329fd6a652`) still produced zero daily trades; that fix is rejected as ineffective.
- A second research-only fork infers bar cadence from recent timestamp gaps: `9f61339b-f925-44a7-9245-ab170faa6b90`, version 1.0.4. Its dry run completed and emitted order events. The D1 regression report `9b687c59-fa52-4b1f-9f99-60d417cab109`, with `use_session_filter=true`, reproduced the same 27 trades and -$8.56 as the filter-disabled control. This verifies the daily gating correction for this dataset only; intraday session-filter parity still needs its own test. The negative expectancy remains a performance failure, not a candidate for promotion.

### StrategyTune exploratory runs

- The saved script `l4zdo1wehylq2zrc3df62y1h` completed multiple H1 runs on EURUSD / IC Markets data for 2025-10-18 through 2026-10-16, with USD 10,000 starting balance. These are not Exness or MT5 runs.
- Across the retrieved runs, reported gross P&L ranged from $106.66 to $537.84; larger samples reported roughly 55.7%–58.5% position win rate. The script's **estimated**, not broker-charged, commission-plus-slippage adjustment ranged from $2.34 to $121.32 in the retrieved runs; one 82-position result reported $537.84 gross, $115.92 estimated costs, $421.92 estimated after-cost P&L, and $344.69 estimated maximum drawdown after costs.
- Run history did not preserve a complete, independently recoverable input manifest for these variants in the retrieved summaries. Therefore these runs must not be treated as matched ablations, walk-forward folds, locked-OOS evidence, or proof that +600% return / 87% win rate has been achieved. Several runs recorded zero days meeting the configured minimum daily-trade target; that target is diagnostic, not a reason to loosen risk gates.
- The requested new four-arm fallback-attribution run (strict-only, single-swing-only, continuation-only, micro-momentum-only) was rejected by the platform because the free-tier daily compute allowance was exhausted (14 minutes used against a 10-minute limit). No new attribution result is claimed. Resume when compute is available or run the controlled experiment in the native MT5 harness.

### Release implication

Keep PR #115 draft and keep live execution disabled. The LONA correction is a research-code fix only. Continue with complete run manifests, native MT5 real-tick paired exports, five-arm deal histories with verified broker costs, three chronological folds, frozen locked OOS, and Exness demo reconciliation/emergency-stop/restart evidence.
