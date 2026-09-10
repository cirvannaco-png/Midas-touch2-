//+------------------------------------------------------------------+
//|                                                   Core/Config.mqh |
//|                                            Medis Touch Indicator  |
//+------------------------------------------------------------------+
#ifndef CONFIG_MQH
#define CONFIG_MQH

#include "NewsFilter.mqh" // for ENUM_NEWS_RISK, used by SetupReasons (v2.9)

// --- Enums ---
enum ENUM_TREND_STATE
  {
   TREND_BULL_STRONG,
   TREND_BULL,
   TREND_NEUTRAL,
   TREND_BEAR,
   TREND_BEAR_STRONG
  };

enum ENUM_FVG_DIR { FVG_BULL, FVG_BEAR };
enum ENUM_FVG_STATE { FVG_FRESH, FVG_TESTED, FVG_MITIGATED, FVG_INVALIDATED };
enum ENUM_LIQ_TYPE { LIQ_BUY_SIDE, LIQ_SELL_SIDE };
enum ENUM_BIAS { BIAS_BULLISH, BIAS_BEARISH, BIAS_NEUTRAL };
enum ENUM_SR_TYPE { SR_MAJOR_RESISTANCE, SR_MINOR_RESISTANCE, SR_MAJOR_SUPPORT, SR_MINOR_SUPPORT };

enum ENUM_FILL_POLICY
  {
   FILL_CONSERVATIVE,
   FILL_OPTIMISTIC,
   FILL_NEAREST,
   FILL_INTRABAR_REPLAY,
   FILL_AMBIGUOUS
  };

enum ENUM_MARKET_PHASE { PHASE_UNDEFINED, PHASE_ACCUMULATION, PHASE_MANIPULATION, PHASE_DISTRIBUTION };
enum ENUM_FIB_ZONE { FIB_ZONE_UNDEFINED, FIB_ZONE_DISCOUNT, FIB_ZONE_NEUTRAL, FIB_ZONE_PREMIUM };
enum ENUM_VALUE_AREA_ZONE { VA_ZONE_UNDEFINED, VA_ZONE_BELOW, VA_ZONE_INSIDE, VA_ZONE_ABOVE };
enum ENUM_OB_STATE { OB_FRESH, OB_TESTED, OB_MITIGATED };
enum ENUM_VOL_REGIME { VOL_REGIME_UNDEFINED, VOL_REGIME_LOW, VOL_REGIME_NORMAL, VOL_REGIME_HIGH };
enum ENUM_TRADING_SESSION { SESSION_DEAD, SESSION_TOKYO, SESSION_LONDON, SESSION_NEWYORK, SESSION_LONDON_NY_OVERLAP };
enum ENUM_MARKET_REGIME { REGIME_UNDEFINED, REGIME_TRENDING, REGIME_RANGING, REGIME_TRANSITION };
enum ENUM_BREAKOUT_CLASS { BREAKOUT_NONE, BREAKOUT_EXPANSION, BREAKOUT_LIQUIDITY, BREAKOUT_FAILED, BREAKOUT_EXHAUSTION };
enum ENUM_REVERSION_CLASS { REVERSION_NONE, REVERSION_VALUE_FADE, REVERSION_LEVEL_REJECTION, REVERSION_TREND_CONFLICT };
enum ENUM_KEYLEVEL_SOURCE { LEVEL_NONE, LEVEL_SR, LEVEL_ORDER_BLOCK, LEVEL_VALUE_AREA, LEVEL_LIQUIDITY_POOL, LEVEL_PREV_WEEK, LEVEL_SESSION, LEVEL_PSYCHOLOGICAL };
enum ENUM_KEYLEVEL_REACTION { REACTION_NONE, REACTION_REJECTION, REACTION_BREAK, REACTION_RETEST, REACTION_FAILED_BREAK, REACTION_ACCEPTANCE, REACTION_ABSORPTION };
enum ENUM_SELECTED_STRATEGY { STRATEGY_NONE, STRATEGY_SMC, STRATEGY_MOMENTUM_BREAKOUT, STRATEGY_MEAN_REVERSION, STRATEGY_KEY_LEVEL };
enum ENUM_SWEEP_GRADE { SWEEP_GRADE_NONE, SWEEP_GRADE_C, SWEEP_GRADE_B, SWEEP_GRADE_A };

// NOTE: The complete production definitions for ImpulseLeg, InducementResult,
// OutcomeStats, CandleData, SwingPoint, BOSEvent, CHOCHPoint, FVGZone,
// OrderBlockZone, LiquidityPool, LiquidityEvent, SRZone, SetupReasons and
// TradeSetup remain unchanged from the previous production revision.
// They are intentionally not duplicated here in this edit.

//+------------------------------------------------------------------+
// The following block must remain identical to the production definition
// because these fields are consumed throughout the EA/indicator.
struct PendingSetup
  {
   TradeSetup        setup;
   double            entryRef;
   double            riskDist;
   double            mfePrice;
   double            maePrice;
   bool              tp1Hit;
   bool              tp2Hit;
   int               barsElapsed;
   datetime          lastBarTime;
   bool              filled;
   datetime          fillTime;
   int               barsToFill;
   bool              sameBarCollision;
   double            sizingEntryPrice;
   double            mgmtRiskDist;
   double            lots;
   double            entryFillPrice;
   double            currentSL;
   bool              beDone;
   bool              partialDone;
   double            remainingLots;
   double            realizedPnL;
   double            totalCommission;
   double            totalSpreadCost;
   double            totalSlippageCost;
   double            confidenceAtSignal;
   double            confidenceDecayed;
   int               decayBars;
   long              decisionId;
   // Execution-time chronology anchor. This is the FIRST execution bar
   // that may be evaluated after the setup's creation bar has fully closed.
   // It prevents a setup created at 10:00:05 from using the 10:00 bar's
   // earlier price action as if the setup already existed.
   datetime          trackingStartBarTime;
  };

#endif
//+------------------------------------------------------------------+
