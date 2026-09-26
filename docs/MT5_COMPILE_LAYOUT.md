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
