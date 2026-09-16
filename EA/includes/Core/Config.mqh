//+------------------------------------------------------------------+
//|                                                   Core/Config.mqh |
//|                                            Medis Touch Indicator  |
//+------------------------------------------------------------------+
#property copyright "Medis Touch"
#property version   "2.00"

#ifndef CONFIG_MQH
#define CONFIG_MQH

#include "NewsFilter.mqh"

// --- Enums ---
enum ENUM_TREND_STATE { TREND_BULL_STRONG, TREND_BULL, TREND_NEUTRAL, TREND_BEAR, TREND_BEAR_STRONG };
enum ENUM_FVG_DIR { FVG_BULL, FVG_BEAR };
enum ENUM_FVG_STATE { FVG_FRESH, FVG_TESTED, FVG_MITIGATED, FVG_INVALIDATED };
enum ENUM_LIQ_TYPE { LIQ_BUY_SIDE, LIQ_SELL_SIDE };
enum ENUM_BIAS { BIAS_BULLISH, BIAS_BEARISH, BIAS_NEUTRAL };
enum ENUM_SR_TYPE { SR_MAJOR_RESISTANCE, SR_MINOR_RESISTANCE, SR_MAJOR_SUPPORT, SR_MINOR_SUPPORT };
enum ENUM_FILL_POLICY { FILL_CONSERVATIVE, FILL_OPTIMISTIC, FILL_NEAREST, FILL_INTRABAR_REPLAY, FILL_AMBIGUOUS };
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

struct ImpulseLeg { bool valid; datetime start_time; datetime end_time; int start_bar; int end_bar; double start_price; double end_price; bool bullish; double strength; };
struct InducementResult { bool valid; bool impulseFound; bool internalStructureFound; bool sweepFound; bool bosConfirmed; double impulseScore; double structureScore; double sweepScore; double bosScore; double totalScore; ImpulseLeg leg; string reason; ENUM_SWEEP_GRADE sweepGrade; double sweepGradeScore; double bosStrength; int barsSinceSweep; int barsSinceBOS; double timeDecay; double bosClosePrice; int bosBarIndex; };
struct OutcomeStats { int wins; int losses; int scratches; int ambiguous; double netPnL; double grossProfit; double grossLoss; double totalCommission; double totalSpreadCost; double totalSlippageCost; double sumRMultiple; int resolvedCount; int ExcludingAmbiguousTotal() const { return wins + losses; } double WinRateExcludingAmbiguous() const { int t=wins+losses; return t>0?100.0*wins/t:0.0; } double WinRateAmbiguousAsLoss() const { int t=wins+losses+ambiguous; return t>0?100.0*wins/t:0.0; } double WinRateAmbiguousAsWin() const { int t=wins+losses+ambiguous; return t>0?100.0*(wins+ambiguous)/t:0.0; } double ProfitFactor() const { if(grossLoss>0)return grossProfit/grossLoss; return grossProfit>0?-1.0:0.0; } double ExpectancyPerTrade() const { return resolvedCount>0?netPnL/resolvedCount:0.0; } double AverageRMultiple() const { return resolvedCount>0?sumRMultiple/resolvedCount:0.0; } };
struct CandleData { datetime time; double open; double high; double low; double close; long tick_volume; double atr; };
struct SwingPoint { datetime time; double price; bool is_high; int bar_index; double strength; };
struct BOSEvent { datetime time; double price; bool is_bullish; double strength; int bar_index; string label; };
struct CHOCHPoint { datetime time; double price; bool bullish; int bar_index; };
struct FVGZone { datetime time; double top; double bottom; ENUM_FVG_DIR dir; ENUM_FVG_STATE state; double width; int bar_index; };
struct OrderBlockZone { datetime time; double top; double bottom; ENUM_FVG_DIR dir; ENUM_OB_STATE state; double displacement_atr; int bar_index; };
struct LiquidityPool { double price_top; double price_bottom; ENUM_LIQ_TYPE type; int touches; bool external; int confirmed_at_shift; };
struct LiquidityEvent { datetime time; double price; ENUM_LIQ_TYPE type; double strength; bool swept; int bar_index; bool external; };
struct SRZone { double top; double bottom; ENUM_SR_TYPE type; int touches; datetime startTime; };

struct SetupReasons {
   bool trend_aligned; bool bos_confirmed; bool liquidity_swept; bool fresh_fvg; bool sr_confluence; bool inducement_valid; bool premium_discount_ok;
   ENUM_MARKET_PHASE phase; string risk_warning; double rvol; bool volume_confirmed; ENUM_FIB_ZONE fib_zone; bool fib_in_zone; double fib_nearest_level;
   bool value_area_ok; ENUM_VALUE_AREA_ZONE va_zone; double va_poc; double va_high; double va_low; bool htf_ob_confluence; ENUM_OB_STATE htf_ob_state;
   ENUM_VOL_REGIME vol_regime; ENUM_TRADING_SESSION session; bool session_ok; ENUM_SWEEP_GRADE sweep_grade; double bos_strength; double time_decay;
   double chase_dist_atr; bool chase_ok; ENUM_NEWS_RISK news_risk; string news_label; int news_minutes_to_event; double contradiction_penalty; double env_score;
   double exec_score; double env_exec_confidence; ENUM_MARKET_REGIME regime; double momentum_score; double breakout_score; ENUM_BREAKOUT_CLASS breakout_class;
   double reversion_score; ENUM_REVERSION_CLASS reversion_class; ENUM_KEYLEVEL_SOURCE keylevel_source; ENUM_KEYLEVEL_REACTION keylevel_reaction; double keylevel_score;
   ENUM_SELECTED_STRATEGY selected_strategy; double selected_strategy_score;
};

struct TradeSetup {
   ENUM_ORDER_TYPE type;
   double entry_top;
   double entry_bottom;
   // Strategy thesis boundary. This is deliberately distinct from the broker protective stop.
   double invalidation;
   double stop_loss;
   double tp1;
   double tp2;
   double final_tp;
   double confidence;
   datetime creation_time;
   bool active;
   SetupReasons reasons;
   double calibrated_probability;
   int calibration_sample;
   bool calibration_has_enough_data;
};

double ResolveExecutionEntry(const TradeSetup &setup) { return setup.type==ORDER_TYPE_BUY?setup.entry_top:setup.entry_bottom; }

struct PendingSetup {
   TradeSetup setup; double entryRef; double riskDist; double mfePrice; double maePrice; bool tp1Hit; bool tp2Hit; int barsElapsed; datetime lastBarTime; bool filled; datetime fillTime; int barsToFill; bool sameBarCollision;
   double sizingEntryPrice; double mgmtRiskDist; double lots; double entryFillPrice; double currentSL; bool beDone; bool partialDone; double remainingLots; double realizedPnL; double totalCommission; double totalSpreadCost; double totalSlippageCost;
   double confidenceAtSignal; double confidenceDecayed; int decayBars; long decisionId;
};

#endif
//+------------------------------------------------------------------+
