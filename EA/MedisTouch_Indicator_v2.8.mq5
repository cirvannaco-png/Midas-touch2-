//+------------------------------------------------------------------+
//|                                                   MedisTouch.mq5  |
//|                                            Medis Touch Indicator  |
//+------------------------------------------------------------------+
#property copyright "Medis Touch"
#property version   "2.80"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

#include "includes/Core/Config.mqh"
#include "includes/Core/CandleData.mqh"
#include "includes/Core/ObjectManager.mqh"
#include "includes/Core/SignalLogger.mqh"
#include "includes/Analysis/TFContext.mqh"
#include "includes/Analysis/Scoring.mqh"
#include "includes/Trading/TradeZone.mqh"
#include "includes/Trading/RiskEngine.mqh"
#include "includes/Trading/OutcomeTracker.mqh"
#include "includes/UI/Dashboard.mqh"
#include "includes/UI/Visuals.mqh"

input group "General"
input int InpMaxHistoryBars = 500;
input group "Structure"
input int InpSwingStrength = 3;
input group "Per-Concept Timeframes"
input ENUM_TIMEFRAMES InpTrendTF = PERIOD_D1;
input ENUM_TIMEFRAMES InpBOSTF = PERIOD_H4;
input ENUM_TIMEFRAMES InpLiquidityTF = PERIOD_M15;
input ENUM_TIMEFRAMES InpFVGTF = PERIOD_M15;
input group "Fair Value Gaps"
input double InpFVGMinSizeATR = 0.1;
input group "Liquidity"
input double InpInternalLiqThresholdATR = 0.2;
input group "Risk"
input double InpMinRiskReward = 1.5;
input double InpMaxSLDistanceATR = 1.5;
input double InpSLBufferATR = 0.25;
input double InpMinStopSpreadMult = 3.0;
input group "Inducement Engine (v2.1)"
input int    InpImpulseLookbackBars = 40;
input double InpImpulseATRMult = 1.2;
input double InpImpulseBodyRatio = 0.6;
input double InpEqualTolATR = 0.2;
input int    InpMaxLegExtend = 10;
input bool   InpRequirePremiumDiscount = true;
input bool   InpRequireDistributionPhase = false;
input int    InpPhaseRangeLookback = 20;
input double InpPhaseCompressionATRMult = 2.5;
input group "Volume Engine (v2.6)"
input bool   InpRequireVolumeConfirmation = true;
input double InpRVOLThreshold = 1.5;
input int    InpRVOLLookback = 20;
input group "Fibonacci Engine (v2.6)"
input bool   InpRequireFibonacciZone = true;
input double InpFibZoneMinPct = 50.0;
input double InpFibZoneMaxPct = 61.8;
input group "Value Area Engine (v2.6)"
input bool   InpRequireValueAreaLocation = false;
input int    InpVALookbackBars = 100;
input int    InpVANumBins = 24;
input double InpVAPercent = 70.0;
input group "HTF Order Block Engine (v2.8)"
input ENUM_TIMEFRAMES InpHtfObTF = PERIOD_H4;
input bool   InpRequireHtfOB = false;
input double InpOBDisplacementATRMult = 1.5;
input double InpOBMinBodyRatio = 0.5;
input double InpOBDistATRMax = 2.0;
input group "Volatility Regime (v2.8)"
input bool   InpBlockLowVolRegime = false;
input int    InpVolRegimeLookback = 100;
input double InpVolRegimeLowPct = 0.25;
input double InpVolRegimeHighPct = 0.75;
input group "Session Filter (v2.8)"
input bool   InpUseSessionFilter = true;
input bool   InpAllowTokyoSession = false;
input bool   InpAllowLondonSession = true;
input bool   InpAllowNewYorkSession = true;
input bool   InpAllowLondonNYOverlap = true;
input group "Declutter / Visuals"
input bool InpShowFVGs = true;
input bool InpShowLiquidity = true;
input bool InpShowDashboard = true;
input int InpMaxBOSDraw = 5;
input int InpMaxFVGDraw = 4;
input int InpMaxLiquidityDraw = 4;
input int InpMaxSRDraw = 4;
input group "Alerts & Logging"
input bool InpAlertOnSetup = false;
input bool InpLogSignals = true;
input bool InpTrackOutcomes = true;
input int InpMaxTrackingBars = 100;
input int InpSessionGMTOffsetOverride = 999;
input group "Outcome Fill Policy (same-bar SL/TP resolution)"
input ENUM_FILL_POLICY InpFillPolicy = FILL_CONSERVATIVE;
input ENUM_TIMEFRAMES InpReplayTF = PERIOD_M1;
input group "Trade Simulator (v2.7)"
input double InpSimRiskPercentPerTrade = 0.5;
input bool   InpSimAllowMinLotOverride = true;
input double InpSimBreakEvenAtR = 1.0;
input double InpSimPartialAtR = 2.0;
input double InpSimPartialFraction = 0.5;
input double InpSimTrailATRMult = 1.5;
input double InpSimCommissionPerLot = 7.0;
input double InpSimSpreadPoints = 10.0;
input double InpSimSlippagePoints = 2.0;

CTFContextPool     g_pool;
CObjectManager     g_objMan("Medis_");
CScoringEngine     g_scoring;
CTradeDecision     g_decision;
CRiskEngine        g_risk;
CVisuals           g_visuals;
CDashboard         g_dashboard;
CSignalLogger      g_logger;
COutcomeTracker    g_tracker;
CTFContext*        g_chartCtx = NULL;
CTFContext*        g_trendCtx = NULL;
CTFContext*        g_bosCtx = NULL;
CTFContext*        g_liqCtx = NULL;
CTFContext*        g_fvgCtx = NULL;
CTFContext*        g_htfObCtx = NULL;
TradeSetup         g_lastSetup;
datetime           g_lastAlertTime = 0;
datetime           g_lastLoggedTime = 0;

int OnInit()
  {
   g_pool.Configure(_Symbol, InpMaxHistoryBars, InpSwingStrength, InpFVGMinSizeATR, InpInternalLiqThresholdATR,
                    InpRVOLLookback, InpVALookbackBars, InpVANumBins, InpVAPercent / 100.0,
                    InpOBDisplacementATRMult, InpOBMinBodyRatio);
   g_chartCtx = g_pool.Get(_Period);
   g_trendCtx = g_pool.Get(InpTrendTF);
   g_bosCtx   = g_pool.Get(InpBOSTF);
   g_liqCtx   = g_pool.Get(InpLiquidityTF);
   g_fvgCtx   = g_pool.Get(InpFVGTF);
   g_htfObCtx = g_pool.Get(InpHtfObTF);
   if(g_chartCtx == NULL || g_trendCtx == NULL || g_bosCtx == NULL || g_liqCtx == NULL || g_fvgCtx == NULL || g_htfObCtx == NULL)
     {
      Print("MedisTouch: failed to initialize one or more timeframe contexts.");
      return INIT_FAILED;
     }
   g_scoring.Init(g_trendCtx, g_bosCtx, g_liqCtx, g_fvgCtx, g_chartCtx, &g_chartCtx.candles);
   g_scoring.ConfigureInducement(InpImpulseLookbackBars, InpImpulseATRMult, InpImpulseBodyRatio,
                                 InpEqualTolATR, InpMaxLegExtend,
                                 InpRequirePremiumDiscount, InpRequireDistributionPhase,
                                 InpPhaseRangeLookback, InpPhaseCompressionATRMult);
   g_scoring.ConfigureVolumeFibonacci(InpRequireVolumeConfirmation, InpRVOLThreshold,
                                      InpRequireFibonacciZone, InpFibZoneMinPct, InpFibZoneMaxPct);
   g_scoring.ConfigureValueArea(InpRequireValueAreaLocation);
   g_scoring.ConfigureHtfOrderBlock(g_htfObCtx, InpRequireHtfOB, InpOBDistATRMax);
   g_scoring.ConfigureVolatilityRegime(InpBlockLowVolRegime, InpVolRegimeLookback, InpVolRegimeLowPct, InpVolRegimeHighPct);
   g_scoring.ConfigureSessionFilter(InpUseSessionFilter, InpAllowTokyoSession, InpAllowLondonSession,
                                    InpAllowNewYorkSession, InpAllowLondonNYOverlap);
   g_decision.Init(&g_chartCtx.candles, g_fvgCtx, g_liqCtx, &g_scoring, InpSLBufferATR, InpMinStopSpreadMult);
   g_visuals.Init(&g_objMan);
   g_logger.Init(_Symbol, InpSessionGMTOffsetOverride);
   // Outcome tracking is execution/chart-timeframe based, never FVG-timeframe based.
   g_tracker.Init(&g_logger, _Symbol, _Period, InpMaxTrackingBars, InpFillPolicy, InpReplayTF);
   g_tracker.ConfigureSimulation(InpSimRiskPercentPerTrade, InpSimAllowMinLotOverride,
                                 InpSimBreakEvenAtR, InpSimPartialAtR, InpSimPartialFraction, InpSimTrailATRMult,
                                 InpSimCommissionPerLot, InpSimSpreadPoints, InpSimSlippagePoints);
   g_dashboard.Init(&g_objMan, g_trendCtx, g_bosCtx, g_liqCtx, &g_scoring, &g_decision, _Symbol, &g_tracker);
   ZeroMemory(g_lastSetup);
   return INIT_SUCCEEDED;
  }
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   g_pool.DetectAll();
   if(g_chartCtx == NULL || !g_chartCtx.candles.IsReady())
      return rates_total;

   double currentATR = g_fvgCtx.candles.GetATR(0);
   TradeSetup buySetup = g_decision.GenerateBuySetup();
   TradeSetup sellSetup = g_decision.GenerateSellSetup();
   g_lastSetup.active = false;
   if(buySetup.active && (!sellSetup.active || buySetup.confidence >= sellSetup.confidence))
     {
      if(g_risk.ValidateSetup(buySetup, InpMinRiskReward, InpMaxSLDistanceATR, currentATR))
         g_lastSetup = buySetup;
     }
   else if(sellSetup.active)
     {
      if(g_risk.ValidateSetup(sellSetup, InpMinRiskReward, InpMaxSLDistanceATR, currentATR))
         g_lastSetup = sellSetup;
     }

   if(g_lastSetup.active && g_lastSetup.creation_time != g_lastAlertTime)
     {
      if(InpAlertOnSetup)
         Alert(StringFormat("MedisTouch %s: %s setup, confidence %.0f%%",
               _Symbol, g_lastSetup.type == ORDER_TYPE_BUY ? "BUY" : "SELL", g_lastSetup.confidence));
      g_lastAlertTime = g_lastSetup.creation_time;
     }

   bool isNewSetup = (g_lastSetup.active && g_lastSetup.creation_time != g_lastLoggedTime);
   if(isNewSetup)
     {
      if(InpLogSignals)
        {
         ENUM_TREND_STATE t = g_trendCtx.trend.GetCurrentTrend();
         g_logger.LogSetup(g_lastSetup, _Symbol, InpFVGTF, EnumToString(t));
        }
      if(InpTrackOutcomes)
         g_tracker.AddSetup(g_lastSetup, -1);
      g_lastLoggedTime = g_lastSetup.creation_time;
     }

   if(InpTrackOutcomes)
      g_tracker.Update(g_chartCtx);

   g_visuals.ClearAll();
   g_visuals.DrawBOS(&g_bosCtx.bos, InpMaxBOSDraw);
   g_visuals.DrawCHOCH(&g_bosCtx.choch);
   if(InpShowFVGs) g_visuals.DrawFVG(&g_fvgCtx.fvg, InpMaxFVGDraw);
   if(InpShowLiquidity) g_visuals.DrawLiquidity(&g_liqCtx.liquidity, InpMaxLiquidityDraw);
   g_visuals.DrawSR(&g_chartCtx.sr, InpMaxSRDraw);

   bool setupFilled = false;
   double setupFillPrice = 0.0;
   datetime setupFillTime = 0;
   int setupBarsToFill = 0;
   if(InpTrackOutcomes && g_lastSetup.active)
      g_tracker.GetFillState(g_lastSetup.creation_time, -1, setupFilled, setupFillPrice, setupFillTime, setupBarsToFill);
   g_visuals.DrawTradeSetup(g_lastSetup, setupFilled, setupFillPrice, setupFillTime);
   if(InpShowDashboard)
      g_dashboard.Update();
   return rates_total;
  }
//+------------------------------------------------------------------+
