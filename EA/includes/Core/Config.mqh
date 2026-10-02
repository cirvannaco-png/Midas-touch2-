#property copyright "Medis Touch"
#property version   "2.00"

#ifndef CONFIG_MQH
#define CONFIG_MQH

#include "NewsFilter.mqh"

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
enum ENUM_VALUE_PROFILE_SOURCE { VA_SOURCE_UNDEFINED, VA_SOURCE_REAL_TRADE_TICKS, VA_SOURCE_BROKER_TRADE_TICKS, VA_SOURCE_REAL_VOLUME_BARS, VA_SOURCE_TICK_VOLUME_BARS };
enum ENUM_VALUE_PROFILE_STATE { VA_STATE_UNDEFINED, VA_STATE_BALANCED, VA_STATE_ACCEPTED_ABOVE, VA_STATE_ACCEPTED_BELOW, VA_STATE_REJECTED_ABOVE, VA_STATE_REJECTED_BELOW };
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
enum ENUM_INDUCEMENT_STRUCTURE { INDUCEMENT_STRUCTURE_NONE, INDUCEMENT_STRUCTURE_SINGLE_SWING, INDUCEMENT_STRUCTURE_EQUAL_POOL };
enum ENUM_STRUCTURAL_STATE { STRUCTURE_INVALID, STRUCTURE_DEGRADED, STRUCTURE_VALID, STRUCTURE_NOT_APPLICABLE };
enum ENUM_LIQUIDITY_SCOPE { LIQUIDITY_SCOPE_UNKNOWN, LIQUIDITY_SCOPE_INTERNAL, LIQUIDITY_SCOPE_EXTERNAL };
enum ENUM_LIQUIDITY_ARCHETYPE { LIQUIDITY_ARCHETYPE_NONE, LIQUIDITY_ARCHETYPE_SINGLE_SWING, LIQUIDITY_ARCHETYPE_EQUAL_POOL, LIQUIDITY_ARCHETYPE_EXTERNAL_POOL };
enum ENUM_STRUCTURE_STAGE { STRUCTURE_STAGE_NO_STRUCTURE, STRUCTURE_STAGE_LIQUIDITY_IDENTIFIED, STRUCTURE_STAGE_LIQUIDITY_SWEPT, STRUCTURE_STAGE_VALID_DISPLACEMENT, STRUCTURE_STAGE_CONFIRMING_BOS, STRUCTURE_STAGE_CAUSAL_FVG, STRUCTURE_STAGE_LOCATION_VALID, STRUCTURE_STAGE_FRESHNESS_VALID, STRUCTURE_STAGE_INVALIDATION_DEFINED, STRUCTURE_STAGE_STRUCTURALLY_VALID, STRUCTURE_STAGE_STRUCTURALLY_INVALID };
enum ENUM_DECISION_STATE { DECISION_REJECT, DECISION_WAIT, DECISION_TRADE };
enum ENUM_RISK_CLASS { RISK_CLASS_NONE, RISK_CLASS_MINIMAL, RISK_CLASS_STANDARD, RISK_CLASS_HIGH_CONVICTION };
enum ENUM_SETUP_LIFECYCLE { SETUP_DETECTED, SETUP_ARMED, SETUP_WAITING_RETEST, SETUP_RETEST_CONFIRMED, SETUP_ENTRY_ELIGIBLE, SETUP_FILLED, SETUP_MANAGED, SETUP_CLOSED, SETUP_EXPIRED };
enum ENUM_FIREWALL_LAYER { FIREWALL_NONE, FIREWALL_STRUCTURE, FIREWALL_ENVIRONMENT, FIREWALL_EXECUTION, FIREWALL_RISK, FIREWALL_CALIBRATION };

struct ImpulseLeg { bool valid; datetime start_time; datetime end_time; int start_bar; int end_bar; double start_price; double end_price; bool bullish; double strength; };
struct InducementResult
  {
   bool valid; bool impulseFound; bool internalStructureFound; bool sweepFound; bool bosConfirmed;
   double impulseScore; double structureScore; double sweepScore; double bosScore; double totalScore;
   ImpulseLeg leg; string reason; ENUM_SWEEP_GRADE sweepGrade; double sweepGradeScore;
   double bosStrength; int barsSinceSweep; int barsSinceBOS; double timeDecay; double bosClosePrice; int bosBarIndex;
   ENUM_INDUCEMENT_STRUCTURE structureType;
   double liquidityPoolPrice;
   int liquidityPoolNearBarIndex;
   int liquidityPoolFarBarIndex;
   int liquidityPoolBarSpan;
   double liquidityPoolSpacingATR;
   int liquidityAgeBars;
   double sweepPenetrationATR;
   double sweepRejectionRatio;
   double sweepShapeScore;
   bool sweepFollowThrough;
   int sweepFollowThroughBarIndex;
   double displacementATR;
   double displacementBodyRatio;
   double bosDistanceATR;
   datetime bosTime;
  };
struct OutcomeStats { int wins; int losses; int scratches; int ambiguous; double netPnL; double grossProfit; double grossLoss; double totalCommission; double totalSpreadCost; double totalSlippageCost; double sumRMultiple; int resolvedCount; int ExcludingAmbiguousTotal() const { return wins + losses; } double WinRateExcludingAmbiguous() const { int t=wins+losses; return t>0?100.0*wins/t:0.0; } double WinRateAmbiguousAsLoss() const { int t=wins+losses+ambiguous; return t>0?100.0*wins/t:0.0; } double WinRateAmbiguousAsWin() const { int t=wins+losses+ambiguous; return t>0?100.0*(wins+ambiguous)/t:0.0; } double ProfitFactor() const { if(grossLoss>0)return grossProfit/grossLoss; return grossProfit>0?-1.0:0.0; } double ExpectancyPerTrade() const { return resolvedCount>0?netPnL/resolvedCount:0.0; } double AverageRMultiple() const { return resolvedCount>0?sumRMultiple/resolvedCount:0.0; } };
struct CandleData { datetime time; double open; double high; double low; double close; long tick_volume; long real_volume; double atr; };
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
   bool value_area_ok; ENUM_VALUE_AREA_ZONE va_zone; double va_poc; double va_high; double va_low; ENUM_VALUE_PROFILE_SOURCE value_profile_source; ENUM_VALUE_PROFILE_STATE value_profile_state; double va_poc_migration_atr; double va_source_quality; double va_score; bool value_area_contradiction; bool htf_ob_confluence; ENUM_OB_STATE htf_ob_state;
   ENUM_VOL_REGIME vol_regime; ENUM_TRADING_SESSION session; bool session_ok; ENUM_SWEEP_GRADE sweep_grade; double bos_strength; double time_decay;
   double chase_dist_atr; bool chase_ok; ENUM_NEWS_RISK news_risk; string news_label; int news_minutes_to_event; double contradiction_penalty; double env_score;
   double exec_score; double env_exec_confidence; ENUM_MARKET_REGIME regime; double momentum_score; double breakout_score; ENUM_BREAKOUT_CLASS breakout_class;
   double reversion_score; ENUM_REVERSION_CLASS reversion_class; ENUM_KEYLEVEL_SOURCE keylevel_source; ENUM_KEYLEVEL_REACTION keylevel_reaction; double keylevel_score;
   ENUM_SELECTED_STRATEGY selected_strategy; double selected_strategy_score;
   ENUM_LIQUIDITY_SCOPE liquidity_scope; ENUM_LIQUIDITY_ARCHETYPE liquidity_archetype;
   double liquidity_event_price; double liquidity_event_strength; bool liquidity_event_external;

   // Structural provenance and hierarchical decision telemetry.
   ENUM_INDUCEMENT_STRUCTURE inducement_structure_type; double liquidity_pool_price; int liquidity_pool_near_bar_index; int liquidity_pool_far_bar_index;
   int liquidity_pool_bar_span; double liquidity_pool_spacing_atr; int liquidity_age_bars; double sweep_penetration_atr; double sweep_rejection_ratio;
   double sweep_shape_score; bool sweep_follow_through; int sweep_follow_through_bar_index; double displacement_atr; double displacement_body_ratio; double bos_distance_atr; datetime bos_time;
   ENUM_FVG_STATE fvg_state; int fvg_age_bars; double fvg_distance_atr; bool fvg_causal; int fvg_bos_age_gap;
   double invalidation_distance_atr;
   ENUM_STRUCTURAL_STATE structural_state; ENUM_STRUCTURE_STAGE structural_stage; double structural_score; string structural_reason;
   double structure_family_score; double liquidity_family_score; double location_family_score; double execution_family_score; double environment_family_score; double quality_score;
   ENUM_DECISION_STATE decision_state; ENUM_FIREWALL_LAYER decision_blocking_layer; string decision_reason;
   ENUM_RISK_CLASS risk_class; ENUM_SETUP_LIFECYCLE setup_lifecycle; string regime_id;
   // Environment telemetry. These are observations only and never act as
   // standalone trading gates.
   double trend_strength; double liquidity_score; int liquidity_bucket;
   double spread_points; double point_size; double atr_value;
   string environment_memory_status; int environment_memory_sample;
   double environment_memory_win_rate; double environment_memory_avg_r;
   double environment_memory_profit_factor; double environment_memory_adjustment;
};

struct TradeSetup {
   ENUM_ORDER_TYPE type;
   double entry_top;
   double entry_bottom;
   double invalidation;
   double stop_loss;
   double tp1;
   double tp2;
   double final_tp;
   double confidence;
   datetime creation_time;
   bool active;
   ENUM_DECISION_STATE decision_state;
   ENUM_RISK_CLASS risk_class;
   ENUM_SETUP_LIFECYCLE setup_lifecycle;
   SetupReasons reasons;
   double calibrated_probability;
   int calibration_sample;
   bool calibration_has_enough_data;
};

double ResolveExecutionEntry(const TradeSetup &setup) { return setup.type==ORDER_TYPE_BUY?setup.entry_top:setup.entry_bottom; }

struct PendingSetup {
   TradeSetup setup; double entryRef; double riskDist; double mfePrice; double maePrice; bool tp1Hit; bool tp2Hit; int barsElapsed; datetime lastBarTime; bool filled; datetime fillTime; int barsToFill; bool sameBarCollision;
   double sizingEntryPrice; double mgmtRiskDist; double weightedRiskDistLots; double lots; double entryFillPrice; double currentSL; bool beDone; bool partialDone; double remainingLots; double realizedPnL; double totalCommission; double totalSpreadCost; double totalSlippageCost; double maeR; double mfeR; int timeToMAE; int timeToMFE; datetime maeTime; datetime mfeTime;
   double confidenceAtSignal; double confidenceDecayed; int decayBars; long decisionId; string decision_fingerprint;
};

#endif
//+------------------------------------------------------------------+
