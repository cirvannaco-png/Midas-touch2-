# MetaEditor compile layout

## Source of truth

The repository's authoritative MQL5 source tree is:

~~~text
EA/
├── MedisTouch_v2.8.mq5
├── MedisTouch_Indicator_v2.8.mq5
└── includes/
    └── all MQL5 headers
~~~

The directory mql5/Experts/MedisTouch/ in the repository is documentation-only. It is not the source tree that should be opened in MetaEditor.

## Expert Advisor placement

Copy the following into the MT5 terminal data directory:

~~~text
<MQL5 data folder>/
└── Experts/
    └── MedisTouch/
        ├── MedisTouch_v2.8.mq5
        └── includes/
            ├── Core/
            ├── Analysis/
            ├── Structure/
            ├── SmartMoney/
            ├── Trading/
            ├── Decision/
            ├── Execution/
            ├── Recovery/
            ├── Portfolio/
            ├── Signals/
            └── Monitoring/
            ...remaining headers under EA/includes/...
~~~

This placement is required because the EA uses relative include paths such as:

~~~mql5
#include "includes/Core/Config.mqh"
#include "includes/Execution/MultiTradeEngine.mqh"
#include "includes/Recovery/RecoveryEngine.mqh"
~~~

The resulting physical paths are therefore:

~~~text
Experts/MedisTouch/MedisTouch_v2.8.mq5
Experts/MedisTouch/includes/Core/Config.mqh
Experts/MedisTouch/includes/Execution/MultiTradeEngine.mqh
Experts/MedisTouch/includes/Recovery/RecoveryEngine.mqh
~~~

Headers included from another header are resolved relative to that header's directory. For example:

~~~mql5
// EA/includes/Execution/OrderManager.mqh
#include "TradeStateMachine.mqh"
~~~

must become:

~~~text
Experts/MedisTouch/includes/Execution/TradeStateMachine.mqh
~~~

The staging script validates this dependency graph before copying.

## Indicator placement

The indicator is a separate MetaTrader program:

~~~text
<MQL5 data folder>/
└── Indicators/
    └── MedisTouch/
        ├── MedisTouch_Indicator_v2.8.mq5
        └── includes/
            └── the same EA/includes tree
~~~

Do not place the indicator .mq5 under Experts.

## MetaEditor procedure

1. Open MT5 and choose File → Open Data Folder.
2. Navigate to MQL5/Experts/MedisTouch/.
3. Stage or copy the EA entry point and complete includes directory there.
4. Open MedisTouch_v2.8.mq5 in MetaEditor.
5. Compile with F7.
6. Repeat for the indicator under MQL5/Indicators/MedisTouch/ when needed.
7. Treat 0 errors as the compile gate. Review warnings separately.

## Important distinction

tools/validate_mql5.py proves repository-level structural invariants. It does not run the MetaEditor compiler and therefore cannot prove MQL5 syntax, type resolution, terminal-build compatibility, account-mode APIs, or broker-specific runtime behavior.

The staging test closes the folder-placement/include-path gap. Only an actual MetaEditor F7 compile closes the compiler-verification gap.

## Repeatable compile preflight (Windows / local MT5 installation)

The repository now includes `tools/compile_mt5.ps1`. It first runs structural include validation, stages the complete expert and indicator into the selected terminal data folder, removes stale output binaries/logs, invokes MetaEditor independently for both entry points, and fails unless each log explicitly reports zero errors and a fresh `.ex5` exists.

From a PowerShell session at the repository root:

~~~powershell
.\tools\compile_mt5.ps1 -MetaEditorPath "C:\Program Files\MetaTrader 5\metaeditor64.exe" -TerminalDataPath "$env:APPDATA\MetaQuotes\Terminal\<YOUR_TERMINAL_ID>"
~~~

Replace `<YOUR_TERMINAL_ID>` with the folder that contains the selected terminal's `MQL5` directory. If MetaTrader was installed elsewhere, supply the actual `metaeditor64.exe` path. The script writes compile logs under `%TEMP%\MidasTouch-MetaEditor-Logs` by default. Treat compiler warnings as review items; the script prints a warning if any are reported. Do not use an old `.ex5` as evidence of a successful build—the script deletes it before compiling.

## Activation and dependency audit

The EA defaults to execution enabled, signal publishing enabled, outcome tracking enabled, adaptive-capacity governance enabled, multi-trade policy enabled, Dynamic Stop Engine enabled, recovery, monitoring, portfolio risk controls, and the daily qualified-trade objective enabled. Adaptive capacity remains gated by statistical sample/expectancy, drawdown, regime qualification, and execution health; enabling the governor does not guarantee that it will raise position limits.

Some features are intentionally opt-in because code alone cannot supply their external inputs:

- **News filter:** `InpUseNewsFilter=false` by default. Enable it only after a valid `MedisTouch_News.csv` is installed in the terminal's file sandbox and its timestamp/time-zone assumptions have been checked.
- **Session filter:** `InpUseSessionFilter=false` by default; enable only with the intended broker-server/session policy configured.
- **Configuration sync:** `InpConfigSyncEndpoint` is blank by default. Set a valid endpoint and ensure the endpoint is allowed in MT5 Tools → Options → Expert Advisors → WebRequest.
- **Signal delivery:** `InpEnableSignals=true`, but delivery still depends on the correct bridge endpoint configuration, WebRequest allow-list, and bridge credentials.
- **Outcome-driven capacity and daily qualified-trade counter:** these require `InpTrackOutcomes=true` and a retail-hedging account in the current implementation. Netting/exchange accounts deliberately disable the features that depend on one decision mapping cleanly to one position.

Do not enable an optional module without its data, credentials, and environment prerequisites. A feature being compiled into the source is not proof that its external dependency is configured.

## Strategy Tester release gate

After both entry points compile:

1. Run the EA in Strategy Tester on the actual intended symbol, broker specification, execution timeframe, and a chronological date range with adequate warm-up data.
2. Use the intended spread/commission model and realistic slippage. Record the MT5 build, symbol, timeframe, date range, modelling mode, deposit, leverage, account margin mode, and the complete input `.set` file alongside the report.
3. Confirm in the Journal that initialization succeeds; history/timeframe contexts are ready; no missing file, WebRequest, invalid stops, volume-step, unsupported-mode, recovery, or persistent-state errors appear.
4. Verify that trades retain server-confirmed initial SL/TP; Dynamic Stop changes are confirmed by server retcodes; partial closes are confirmed rather than inferred from the local request return value; recovery and duplicate-event paths do not create duplicate tracking; and portfolio/daily/drawdown guards behave as expected.
5. Run separate baseline and challenger passes on untouched out-of-sample dates. Do not use optimized in-sample values as a live-performance claim. Save the tester HTML report, Journal, EA inputs, and run metadata.

A successful compile and static CI are necessary but not sufficient for live certification. Before using a funded account, pass the Strategy Tester, then demo forward testing, and only then consider controlled live exposure.
