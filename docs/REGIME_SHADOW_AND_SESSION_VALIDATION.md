# Regime shadow, broker-session telemetry, and promotion gate

**Status:** research instrumentation only. Live execution remains gated by the existing EA policy, and this work does not certify that the regime detector or any strategy is profitable.

## What the source currently does

CRegimeDetector::Classify() derives a market regime from the existing trend engine, ATR-percentile volatility classifier, and market-phase heuristic. The phase component is heuristic and must be treated as uncertain evidence.

The detector is **not purely diagnostic at the whole-EA level**. CTradeDecision::SelectPeerStrategy() reads SetupReasons.regime in the executable setup path, selects which challenger family may compete, and returns no selection for REGIME_UNDEFINED. For defined regimes, the SMC baseline may still be selected if eligible. CScoringEngine::PopulateStrategyDiagnostics() also runs a separate diagnostic selector whose selection is not the final executable selection. These are distinct code paths. This instrumentation does not refactor or alter either path.

## Shadow telemetry

The enabled-by-default, disableable InpEnableRegimeShadowLogging input writes MidasTouch_RegimeShadow_<SYMBOL>_<TIMEFRAME>.csv under the MT5 terminal's file area. It is observational and is not consulted by setup eligibility, sizing, authorization, or order routing.

The append-only log records event/signal IDs, direction, regime, volatility regime, market phase, trend context, selected strategy and score, challenger scores/classes, selection/rejection status, the liquidity-session policy result, broker-session schedule result, spread points, point size, ATR, spread-to-ATR, and entry/invalidation/stop/target levels when a setup exists. Additional statuses emitted by the execution path distinguish setup generation, final risk validation, and execution policy authorization/rejection.

The existing signal/outcome exports carry SignalID, Regime, SelectedStrategy, OutcomeEpoch, Filled, RealizedNetPnL, commission, simulated spread cost, and slippage cost. Join by the canonical SignalID (SYMBOL_BUY_or_SELL_creation_epoch) before attributing subsequent recorded outcomes. Do not treat no-fill or unfilled signals as realized trades. The EA's outcome file alone is not proof of broker reconciliation: reconcile it with unique native tester/broker deal tickets and actual broker costs.

Limitations must remain explicit:
- Candidates rejected before a complete setup exists have no trusted entry/stop/target geometry for a counterfactual result. Record the rejection; do not invent a win/loss.
- The SETUP_BUILT, RISK_VALIDATED_CANDIDATE, and POLICY_* rows can share a SignalID. Reduce to the last lifecycle status for an event before counting candidates; do not count lifecycle rows as separate trades.
- SpreadAssessment is a telemetry label (HIGH_SPREAD_TO_ATR_REVIEW at 0.15 ATR or higher), not an independently validated no-trade threshold.
- Broker market availability is read from SymbolInfoSessionTrade. It is UNKNOWN when the terminal does not expose a schedule. It is telemetry only; a probe result does not overrule a broker rejection.
- Rollover telemetry is NOT_CONFIGURED by default. Setting the start/end values labels a configured broker-server-time window; it does not block entries. Only use times verified against the target broker.

## Separate controls, do not collapse them

1. **Market availability:** use the target broker's per-symbol weekly trade schedule and session breaks. OPEN/CLOSED/UNKNOWN describes availability only.
2. **Liquidity session:** CSessionFilter classifies Tokyo/London/New York/overlap windows in GMT with separate DST handling. This is a liquidity policy, not a universal market-hours calendar.
3. **Spread:** record broker spread points and spread-to-ATR independently; compare to a broker/instrument-calibrated limit only in a separate, matched research arm.
4. **Rollover:** configure a server-time observation window from the actual broker and log it separately. Do not assume all brokers roll over at the same time.
5. **Volatility:** preserve VOL_REGIME_LOW/NORMAL/HIGH/UNDEFINED; do not silently convert UNDEFINED to NORMAL. Validate regime × volatility outcomes separately.

A separate CMarketConditionsPolicy module can enforce market availability, an explicit liquidity-session allowlist, absolute spread, spread-to-ATR, a configured rollover window, and volatility state. Its master input InpEnableBrokerAwareEntryGate defaults to false. Missing broker schedule, unconfigured required thresholds, or invalid rollover configuration fail closed if the master gate is explicitly enabled. No new gate changes eligibility under the default preset. Do not enable this option in live trading until a matched tester and broker-demo review confirms its behavior for the exact symbol specification.

## LONA reconciliation findings

The evidence manifest docs/evidence/lona_report_reconciliation_2026-10-18.json records six LONA report summaries and their reconstructed trade histories. Known results:

| Report | Stored metrics | Reconstructed rows | Audit treatment |
|---|---|---:|---|
| ddbe4ba0-9d2d-453e-ac0a-f29b1f6e2211 (v1.0.4 daily XAUUSD baseline) | 27 trades; -$8.56 net; 59.26% win; PF 0.82 | 9; gross rows sum -$3.8835 | Count mismatch; block |
| ffbe0f09-5bc3-4d38-afb4-2f1f532c2d50 (v1.0.5 shadow parameters) | Same baseline metrics | 9; same gross row sum | Count mismatch; not a distinct validated treatment |
| 2797b900-501b-4b9a-bd2e-1435f83ff8e6 (v1.0.5 regime-gated arm) | 3 trades; +$10.52 net; 100% win; PF 0 | 1; gross +$10.7928 | Incomplete sample, metric inconsistency; block |
| 5f278eb6-5419-40a1-bf06-b73bddb6ebf3 (v1.0.5 low-risk gated arm) | 3 trades; +$5.26 net; 100% win; PF 0 | 1; gross +$5.3964 | Incomplete sample, metric inconsistency; block |
| 10fcaf68-8503-4013-84aa-6f501f509e9e (v1.0.4 later window) | 21 trades; +$65.71 net; 100% win; PF 0 | 7; gross +$67.6888 | Incomplete sample, metric inconsistency; block |
| d607d6eb-01b0-4a0a-92f4-3fe6fe0e36f2 (v1.0.5 later window) | 0 trades | 0 | No performance evidence |

The LONA endpoint documentation explicitly permits reconstructed counts below the stored report count for legacy-redacted histories. These are not merely a missing second page: every endpoint returned has_next=false. The exact missing-trade cause and records cannot be recovered through the currently exposed trade endpoint. Keep stored summary metrics as platform-authoritative, but mark the underlying row-level reconciliation **unresolved**; never compare gross reconstructed P&L directly with stored net P&L because the endpoint excludes commissions/fees.

A new tools/audit_lona_report_consistency.py and tools/tests/test_audit_lona_report_consistency.py enforce this fail-closed policy. Cost verification is deliberately false in the captured manifest because these LONA runs do not prove actual broker costs.

## Required matched evaluation

Use the same source commit/build, symbol specification, tick dataset hash, period, broker/server, risk parameters, and verified costs across arms. Keep these as distinct arms:
- **Baseline:** current implementation and settings; unchanged execution path.
- **Shadow only:** exactly the same settings/selection behavior, with telemetry turned on; verifies the logger does not alter outputs and measures regimes and lifecycle statuses.
- **Research-gated candidate:** an offline or separately frozen branch using validated regime policies. Never deploy it by toggling a live input before the comparison has passed.

Match actual candidate IDs and outcomes, reconcile each closed position to deal history, and report net expectancy, PF, drawdown, win rate with scratches/ambiguous trades separate, cost-inclusive average win/loss, regime transitions, rejected opportunity counts, and any validated counterfactual outcomes. For missed opportunities, use a fully specified test candidate plus subsequent real ticks/bars and conservative same-bar collision handling; no setup geometry means no counterfactual label.

Lock chronologically later out-of-sample dates before examining outcomes. Require matched real-tick MT5 exports and at least three pre-OOS walk-forward folds, an untouched locked-OOS sample with fully matured trades, and a designated selected broker demo run with broker deal reconciliation, emergency-stop persistence/restart checks, and zero unexplained tickets/cost gaps. Any missing or ambiguous artifacts remain blockers.

## Current promotion state

- Static source and Python checks can validate the instrumentation contract, not trading performance.
- MetaEditor compile is needed for the new MQL5 files and all EA call sites.
- No matched real-tick ON/OFF report or verified-cost OOS evidence has been produced by these changes.
- No selected broker demo forward reconciliation has been completed by this instrumentation.
- Do not merge or deploy this candidate, and do not claim production/live-trading readiness, until all release gates pass.
