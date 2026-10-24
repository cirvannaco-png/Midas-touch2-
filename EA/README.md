# EA — MedisTouch v2.8 (MQL5)

MetaTrader 5 source for the Medis Touch engine. The backend that receives
its signals lives in [`../telegram-bridge`](../telegram-bridge).

## Layout

```text
EA/
├── MedisTouch_v2.8.mq5              # Expert Advisor (trading + signal publishing)
├── MedisTouch_Indicator_v2.8.mq5    # chart indicator (visuals/dashboard, no trading calls)
└── includes/
    ├── InducementEngine.mqh         # v2.8 facade -> SmartMoney/Inducement + MarketPhase + PremiumDiscount
    ├── HTF_OrderBlock.mqh           # v2.8 facade -> SmartMoney/OrderBlock (run on an HTF context)
    ├── VolatilityRegime.mqh         # v2.8 facade -> Analysis/VolatilityRegime (ATR percentile regime)
    ├── Core/                        # Config, CandleData, ObjectManager, SessionFilter, SignalLogger
    ├── Analysis/                    # TFContext, Scoring, TrendEngine, VolatilityRegime
    ├── Structure/                   # SwingDetector, BOS, CHOCH
    ├── SmartMoney/                  # FVG, Liquidity, OrderBlock, Inducement, PremiumDiscount, ValueArea, Volume, Fibonacci, SupportResistance, MarketPhase
    ├── Trading/                     # TradeZone, RiskEngine, Targets, OutcomeTracker
    ├── Decision/                    # TradeDecision (records), DecisionEngine (policy router), DecisionStore (CSV persistence)
    ├── Execution/                   # BrokerAdapter, OrderManager, PositionManager, TradeStateMachine
    ├── Recovery/                    # RecoveryEngine (reconciles broker state after a restart)
    ├── Portfolio/                   # PortfolioManager, MultiTradeEngine (capital allocation / multi-leg policy), cross-symbol risk caps
    ├── Signals/                     # SignalPublisher (HTTP -> telegram-bridge), SubscriberPlatform
    ├── Monitoring/                  # ProductionMonitor (heartbeat, drawdown alerts, reject counters)
    └── UI/                          # Dashboard, Visuals (indicator only)
```

The three facade headers are the stable include paths for the v2.8
additions. They only `#include` the real implementation next to the
concepts it depends on, so the internal folder layout can move without
breaking call sites. Every underlying header has an include guard, so
including a facade and the concrete header together is safe.

## Why two `.mq5` files

MQL5 forbids trading calls (`OrderSend`, `CTrade`) from an indicator
context. `MedisTouch_Indicator_v2.8.mq5` is the visualisation-only chart
indicator; `MedisTouch_v2.8.mq5` is the robot that runs under `OnTick()`
where trading is legal. They share the same analysis engine and can run
on the same chart together.

## Install / compile

1. Copy `MedisTouch_v2.8.mq5` and the whole `includes/` folder into
   `MQL5/Experts/MedisTouch/` in your terminal's data folder
   (File → Open Data Folder in MT5), keeping the relative layout —
   the EA includes with paths like `includes/Core/Config.mqh`.
2. Copy `MedisTouch_Indicator_v2.8.mq5` (plus the same `includes/`) into
   `MQL5/Indicators/MedisTouch/` if you want the chart visuals.
3. Open each `.mq5` in MetaEditor and press F7. Expect 0 errors.
4. In MT5: Tools → Options → Expert Advisors → allow WebRequest for the
   backend URL, otherwise `SignalPublisher` cannot post signals.

Compiled `.ex5` output is git-ignored on purpose — build it locally.

## Multi-symbol portfolio trading (forex, metals, indices, crypto where broker-supported)

The account is intended to take qualified trades across multiple symbols, not just multiple legs on one chart. **Attach one EA instance to each symbol chart you want it to trade** (for example XAUUSD, EURUSD, GBPUSD, USDJPY, and supported indices); this EA build does not independently scan and execute a user-defined watchlist from a single chart. Keep the same `InpMagicNumber` and the same account risk-profile settings across those instances so the portfolio manager can aggregate their open positions and pending orders. The portfolio manager checks existing EA exposure across symbols, applies per-symbol and correlation-group position limits, and enforces the configured account-equity open-risk cap. Do not run instances with inconsistent risk caps or magic numbers if you expect them to share a portfolio budget. Forex pairs can be correlated (for example, several USD exposures), so correlation grouping is deliberately conservative and should be validated against the actual symbols offered by the broker.

“Multiple successful trades” means the EA should keep evaluating valid setups on all enabled symbol charts and record winners separately; it cannot guarantee a specific number of profitable trades. Each entry must still pass strategy qualification, session/news/spread checks, protective-stop validation, execution-ledger health, and portfolio risk gates. The daily target is an objective, never a reason to force an entry.

Nothing in the engine is XAUUSD-specific: pip/point sizing
(`Core/PipCalculator.mqh`) is derived from broker symbol properties, and
the volatility regime classifier (`Analysis/VolatilityRegime.mqh`) is
ATR-percentile-based against each symbol's own history, not a hardcoded
absolute threshold. Trading EURUSD, USDJPY, or EURGBP alongside XAUUSD
means attaching another instance of `MedisTouch_v2.8.mq5` to that
symbol's chart with its own `InpWeightSetVersion` — MT5 runs one EA
instance per chart/symbol by design, this isn't a single process
handling multiple symbols. Every instance posts to the same bridge;
`signals`/`signal_outcomes` already carry `symbol` as a first-class
column, so `tools/metrics_engine.py --regime-matrix` and
`tools/calibration_matrix.py` break down by symbol automatically once
more than one is live.

## Signal publishing

`Signals/SignalPublisher.mqh` posts each routed decision to the FastAPI
service in `telegram-bridge`. The service broadcasts to `CHAT_ID` and
accepts bot commands only from `ADMIN_CHAT_ID`.

Each signal is tagged with `regime`, `session`, `sweep_grade`,
`htf_ob_aligned`, and `weight_version` (the `InpWeightSetVersion` input —
bump this by hand whenever a scoring-formula change ships; nothing
enforces it yet). `Trading/OutcomeTracker.mqh` posts the matching
resolved outcome (win/loss/scratch/no_fill/ambiguous, realized R,
MFE/MAE) to `POST /outcome` the moment it resolves a setup, via the same
`decision_id` the signal was published under — see that file's
`PublishIfConfigured()` and `Config.mqh`'s `PendingSetup.decisionId` for
why `AddSetup()` has to happen *after* `CDecisionRouter::Decide()` mints
that id, not before.

`Signals/ConfigSync.mqh` (opt-in via `InpConfigSyncEndpoint`, blank by
default) polls `GET /config/{symbol}` on a timer (`InpConfigSyncPollMinutes`)
and warns in the terminal log if the bridge's most-recently-approved
weight_version differs from this instance's compiled `InpWeightSetVersion`.
It never changes behavior automatically — see `telegram-bridge/README.md`'s
"Trade tagging & recalibration" section for why nothing can yet.

## Decision persistence

`Decision/DecisionStore.mqh` appends every routed decision and every
submitted execution to CSV files in the terminal's `MQL5/Files` folder
(`MedisTouch_Decisions_<SYMBOL>.csv`, `MedisTouch_Executions_<SYMBOL>.csv`).
`Recovery/RecoveryEngine.mqh` reads them at startup and matches broker
tickets back to the setup that created them via the `MT#<decision_id>`
order comment. Deleting those files means a restarted terminal can no
longer manage trades opened by a previous session.


## On-chart operator panel, trailing protection, and sessions

The EA exposes an optional on-chart control panel (InpShowTradeControlPanel=true):

- **BUY / SELL** submit a market entry through the normal order manager. They use ATR-based stops, broker lot sizing, spread/news checks, both the existing DST-aware session gate and the optional custom session gate, daily/equity risk guards, and the portfolio-risk budget. TP1 itself clears the setup validator's minimum R:R requirement; final TP uses InpManualRiskReward, which must be at least InpMinRiskReward + 0.3R. They do not bypass the EA's execution-risk controls.
- **CLOSE ALL** cancels this EA's managed pending orders and closes positions for the current chart symbol and InpMagicNumber only. It does not close positions belonging to another symbol, manual trading, or another EA magic number. On netting/exchange accounts, BUY/SELL also refuse to add same-symbol exposure while any position or pending order for that symbol exists, because MT5 aggregates trade identity at symbol level; resolve existing exposure first.
- **EMERGENCY STOP** persists a per-symbol/per-magic halt in terminal global variables, blocks new EA entries, and attempts to cancel/close matching exposure. It stays latched after a terminal restart until the operator presses **RESUME**. Check the execution audit and broker state if a close is rejected; a button click is not proof that every broker position closed. RESUME is refused while matching positions or pending orders remain. If the panel is hidden while the emergency latch is set, the panel is temporarily shown so the operator can recover the EA.
- The panel shows managed position count, floating PnL, magic number, session status, and whether dynamic trailing protection is enabled. On MT5 **netting** accounts, all activity for one symbol is consolidated into a single net position. Manual BUY/SELL and automated execution therefore fail closed whenever any position or pending order already exists for that symbol; close/manage existing exposure before opening another trade on that symbol. Do not mix this EA with external manual or other-EA orders on the same symbol when you need isolated close-all semantics; use a dedicated symbol/account or a hedging account. The EA also emits an account-mode warning at initialization when it detects a netting/exchange account.
- `InpAllowConcurrentOpposingPositions` is **true by default**, as requested. It permits independent opposing BUY/SELL positions only on an MT5 **retail-hedging** account and only when a valid opposite-side setup passes all strategy, execution, trailing-stop, portfolio-risk and position-count gates. On netting/exchange accounts the EA remains fail-closed; the input does not make simultaneous independent long/short positions possible there. Set it false to disable concurrent opposing entries.

Dynamic trailing protection is enabled by default through InpEnableDynamicStop=true and is mandatory whenever the EA is attached to a terminal outside Strategy Tester. If the input is disabled outside the tester, OnInit refuses to start; the tester-only exception exists for a controlled matched ablation, not for demo/live operation. The trail begins after the configured favourable-R threshold, uses breakeven protection and an ATR/confirmed-structure trail, and never intentionally widens an existing stop. Broker stop/freeze levels and connectivity can delay or reject a modification, so monitor the Experts log and SL-modification audit rather than assuming every update succeeded.

### Configurable sessions

The existing DST-aware Tokyo/London/New York session filter remains independent. When InpUseSessionFilter is enabled, it governs both automated and button-initiated entries. The additional optional custom gate uses **broker-server time** and is disabled by default to preserve existing behaviour. Enable InpUseCustomTradingSessions, then configure up to three enable/start/end windows (HH:MM). Windows crossing midnight are supported; equal start/end times do not create an all-day window. When the custom gate is enabled but no valid window matches, new automated and button-initiated entries are denied. If both gates are enabled, both must allow the entry. Open-position management and outcome tracking continue outside the configured windows.

### Execution audit and trade identification

The EA writes detailed, append-only event rows to MQL5/Files/MidasTouch_ExecutionAudit_<SYMBOL>.csv and mirrors them to the terminal Experts log. Events include decisions, automated/manual submissions, rejected orders, fills, exits with net costs, pending-order cancellations, close-all summaries, and emergency-stop/resume actions. The audit writer is isolated in `includes/Execution/ExecutionAudit.mqh`; `includes/UI/TradeControlPanel.mqh` owns chart presentation and operator events only. Every managed trade carries InpMagicNumber and an MT#<decision_id> comment; manual panel trades use the same decision store, order manager, and execution persistence path, but are deliberately excluded from automated strategy calibration and environment-memory learning so operator discretion cannot bias the model's training evidence.

### Daily trade objective and direction policy

`InpMinimumQualifiedTradesPerDay=3` is an objective, not a quota enforced by fabricated entries. The EA tracks **executed entry orders** separately from **qualified closed winners** (net profitable, fully closed tracked outcomes meeting `InpMinimumQualifiedTradeR`, default 0.25R). While the qualified-winner objective remains outstanding on a weekday, it logs progress and continues normal setup evaluation only inside configured sessions and after risk, news, stop, spread, and execution safeguards. Entry counts do not include rejected signals, and partial-fill callbacks for the same broker order are deduplicated.

Both BUY and SELL setups are evaluated independently. A direction can change when conditions change; the EA does not treat the three-trade objective as permission to weaken setup quality. Simultaneous opposing same-symbol exposure is a separate capability, controlled explicitly by `InpAllowConcurrentOpposingPositions` and available only with an MT5 retail-hedging account. The requested small-account profile now has a configured ceiling of three positions and a 20% portfolio stop-risk cap. Runtime concurrency still starts at one position and increases by one only when every existing chart-symbol position is floating-profitable and protected by a break-even-or-better stop. This is a high-risk research candidate, not live-validated; test any multi-position behavior only on an isolated Exness demo, and do not treat green CI as profitability evidence. Foreign manual/other-EA positions or pending orders on the chart symbol fail closed because their risk is outside this instance's ledger attribution. See [the MT5 hedging demo validation gate](../docs/MT5_HEDGING_DUAL_DIRECTION_DEMO_GATE.md).

### Backtesting and optimization

All panel, custom-session, risk/reward, stop, execution, and strategy controls are standard MQL5 input parameters, so they can be selected in Strategy Tester optimization. Run visual backtests when validating the buttons/panel; use non-visual tests for parameter sweeps. Keep spread, commission, slippage, broker symbol specifications, and account margin mode realistic. Chart-button actions are operator events and are not generated automatically during ordinary parameter optimization; evaluate the automated strategy separately from manual control-path testing.

### Self-improvement activation is a separate production gate

The repository contains EA-side outcome/calibration and environment-memory telemetry plus the backend's evidence-ingestion and guarded recalibration lifecycle. That does **not** by itself prove the live engine is autonomously running or that new weights are approved. Production scheduling is owned by GitHub Actions via .github/workflows/production-maintenance.yml; create the GitHub Actions production environment, restrict it to main, and configure the `BRIDGE_API_KEY` environment secret (the workflow's base URL is non-secret and configured in YAML); then verify a due run returned status=ok with a persisted cycle ID. Genuine MT5 backtest evidence must separately pass chronological walk-forward and locked-OOS gates before a candidate is evaluated. Promotion still requires the explicit approval/configuration-hash gate. GitLab is a mirror only and its maintenance jobs are disabled. A CI-green source branch is not proof of a live recalibration or validated trading performance.

## CI and build validation

- `.gitlab-ci.yml` runs `tools/validate_mql5.py` on changes under `EA/`: it resolves every `#include`, rejects missing or case-mismatched headers and unbalanced include guards, and prevents compiled binaries (`*.ex5`/`*.ex4`) from entering the repository.
- `.github/workflows/mql5-compile.yml` installs the official MetaTrader 5 terminal on a Windows runner and compiles `MedisTouch_v2.8.mq5` with MetaEditor. The job requires a parseable compiler summary, zero compile errors, and a generated EX5; the log is retained as a CI artifact, while the EX5 stays on the ephemeral runner.
- A successful MetaEditor compile is not a Strategy Tester run and does not establish profitability, broker execution correctness, or live-trading readiness. Run realistic visual and non-visual backtests and demo/forward tests before live deployment.
