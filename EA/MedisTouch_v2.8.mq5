//+------------------------------------------------------------------+
//|                                                MedisTouch_EA.mq5  |
//|                                   Medis Touch — Trading/Signal EA |
//+------------------------------------------------------------------+
#property copyright "Medis Touch"
#property version   "2.80"
#property strict

#include "includes/Core/Config.mqh"
#include "includes/Core/CandleData.mqh"
#include "includes/Core/SignalLogger.mqh"
#include "includes/Analysis/TFContext.mqh"
#include "includes/Analysis/Scoring.mqh"
#include "includes/Trading/TradeZone.mqh"
#include "includes/Trading/RiskEngine.mqh"
#include "includes/Trading/OutcomeTracker.mqh"
#include "includes/Decision/DecisionEngine.mqh"
#include "includes/Decision/DecisionStore.mqh"
#include "includes/Execution/BrokerAdapter.mqh"
#include "includes/Execution/OrderManager.mqh"
#include "includes/Execution/PositionManager.mqh"
#include "includes/Recovery/RecoveryEngine.mqh"
#include "includes/Portfolio/PortfolioManager.mqh"
#include "includes/Portfolio/RiskGuard.mqh"
#include "includes/Core/NewsFilter.mqh"
#include "includes/Signals/SubscriberPlatform.mqh"
#include "includes/Signals/SignalPublisher.mqh"
#include "includes/Signals/ConfigSync.mqh"
#include "includes/Monitoring/ProductionMonitor.mqh"

input group "General"
input int    InpMaxHistoryBars = 500;
input group "Structure"
input int    InpSwingStrength = 3;
input group "Per-Concept Timeframes"
input ENUM_TIMEFRAMES InpTrendTF = PERIOD_D1;
input ENUM_TIMEFRAMES InpBOSTF = PERIOD_H4;
input ENUM_TIMEFRAMES InpLiquidityTF = PERIOD_M15;
input ENUM_TIMEFRAMES InpFVGTF = PERIOD_M15;
input group "Fair Value Gaps"
input double InpFVGMinSizeATR = 0.1;
input group "Liquidity"
input double InpInternalLiqThresholdATR = 0.2;
input group "Risk (setup validation)"
input double InpMinRiskReward = 1.5;
input double InpMaxSLDistanceATR = 1.5;
input double InpSLBufferATR = 0.25;
input double InpMinStopSpreadMult = 3.0;
input double InpMaxEntryDeviationATR = 0.15;
input group "Inducement Engine"
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
input group "Sweep Quality / Chase Filter / FVG Proximity (v2.9)"
input bool   InpRequireMinSweepGrade = false;
input int    InpMinSweepGrade = 2;
input bool   InpRequireFreshSetup = false;
input int    InpMaxBarsSinceBOS = 5;
input bool   InpRequireChaseFilter = false;
input double InpMaxChaseDistATR = 0.75;
input double InpFVGMaxDistATR = 1.25;
input double InpMinDirectionalAdvantage = 0.0;
input group "Signal Lifecycle (v2.9)"
input bool   InpPublishLifecycleUpdates = false;
input int    InpSignalExpiryBars = 12;
input double InpSignalStaleChaseATR = 1.0;
input double InpInvalidateOpposingConfidence = 70.0;
input group "Confidence Diagnostics (v2.10) - measured, NOT acted on"
input double InpDiagContradictionWeight = 0.25;
input double InpDiagEnvWeight = 1.0;
input double InpDiagExecWeight = 1.0;
input double InpDiagDecayHalfLifeBars = 12.0;
input group "Strategy Diagnostics (v2.12) - measured, NOT acted on"
input int    InpMomentumBreakoutRecencyBars = 10;
input int    InpBreakoutLiqOverlapBars = 2;
input int    InpBreakoutExtensionLookbackBars = 15;
input double InpBreakoutExhaustionATRMult = 3.0;
input int    InpMomentumLookbackBars = 10;
input group "Mean Reversion Diagnostics (v2.13) - measured, NOT acted on"
input double InpReversionMinStretchATR = 1.0;
input double InpReversionSRZoneATRTolerance = 0.25;
input double InpReversionWickRejectionRatio = 0.55;
input int    InpReversionLiqRecencyBars = 10;
input int    InpReversionTrendConflictRecencyBars = 10;
input double InpReversionTrendConflictMinStrength = 0.5;
input group "Key-Level Reaction Diagnostics (v2.14) - measured, NOT acted on"
input int    InpKeyLevelLookbackBars = 5;
input double InpKeyLevelSearchATRMax = 3.0;
input double InpKeyLevelTouchToleranceATRMult = 0.15;
input int    InpKeyLevelAbsorptionMinTouches = 3;
input double InpKeyLevelWickRejectionRatio = 0.55;
input double InpKeyLevelRoundStep = 10.0;
input group "Strategy Selection (v2.15) - measured, NOT acted on"
input double InpMinSelectionScore = 60.0;
input group "Logging"
input bool   InpLogSignals = true;
input bool   InpTrackOutcomes = true;
input int    InpMaxTrackingBars = 100;
input int    InpCalibrationMinSample = 30;
input int    InpSessionGMTOffsetOverride = 999;
input ENUM_FILL_POLICY InpFillPolicy = FILL_CONSERVATIVE;
input ENUM_TIMEFRAMES  InpReplayTF = PERIOD_M1;
input group "Policy — what this account does with a validated setup"
input bool   InpEnableExecution = false;
input bool   InpEnableSignals = false;
input double InpMinConfidenceExecute = 70.0;
input double InpMinConfidenceSignal = 60.0;
input double InpFullRiskConfidence = 85.0;
input int    InpMaxSpreadPoints = 0;
input group "Execution"
input bool   InpUseMarketOrders = true;
input double InpRiskPercentPerTrade = 0.5;
input int    InpMaxOpenTrades = 3;
input ulong  InpMagicNumber = 987654321;
input bool   InpAllowMinLotOverride = false;
input double InpMaxDailyLossPercent = 3.0;
input double InpMaxDrawdownPercent = 10.0;
input double InpDeriskStartPercent = 5.0;
input double InpDeriskFloor = 0.25;
input bool   InpUseNewsFilter = false;
input string InpNewsFilterFile = "MedisTouch_News.csv";
input int    InpNewsMinutesBefore = 15;
input int    InpNewsMinutesAfter = 5;
input int    InpNewsWarnMinutesBefore = 60;
input int    InpNewsWarnMinutesAfter = 30;
input double InpNewsWarnMultiplier = 0.85;
input group "Position Management"
input double InpBreakEvenAtR = 1.0;
input double InpPartialAtR = 2.0;
input double InpPartialFraction = 0.5;
input double InpTrailATRMult = 1.5;
input group "Trade Simulator costs (v2.7)"
input double InpSimCommissionPerLot = 7.0;
input double InpSimSpreadPoints = 10.0;
input double InpSimSlippagePoints = 2.0;
input group "Portfolio (account-wide, across every symbol this magic number trades)"
input double InpMaxPortfolioRiskPercent = 3.0;
input int    InpMaxPositionsPerSymbol = 2;
input int    InpMaxPositionsPerGroup = 3;
input group "Signal Transport"
input int    InpWebRequestTimeoutMs = 5000;
input string InpBridgeApiKey = "";
input string InpWeightSetVersion = "v2.10-baseline";
input string InpConfigSyncEndpoint = "";
input int    InpConfigSyncPollMinutes = 15;
input group "Production Monitoring"
input int    InpHeartbeatIntervalSec = 60;
input double InpMaxDrawdownAlertPercent = 10.0;

CTFContextPool     g_pool;
CScoringEngine     g_scoring;
CTradeDecision     g_decision;
CRiskEngine        g_risk;
CSignalLogger      g_logger;
COutcomeTracker    g_tracker;
CTFContext*        g_chartCtx = NULL;
CTFContext*        g_trendCtx = NULL;
CTFContext*        g_bosCtx = NULL;
CTFContext*        g_liqCtx = NULL;
CTFContext*        g_fvgCtx = NULL;
CTFContext*        g_htfObCtx = NULL;
CDecisionEngine    g_router;
CBrokerAdapter     g_broker;
COrderManager      g_orders;
CPositionManager   g_positions;
CDecisionStore     g_store;
CRecoveryEngine    g_recovery;
CPortfolioManager  g_portfolio;
CRiskGuard         g_riskGuard;
CNewsFilter        g_newsFilter;
CSubscriberPlatform g_subscribers;
CSignalPublisher   g_publisher;
CConfigSync        g_configSync;
CProductionMonitor g_monitor;
datetime           g_lastLoggedTime = 0;
datetime           g_lastBarTime = 0;
long               g_lifecycleDecisionId = 0;
datetime           g_lifecycleCreationTime = 0;
TradeSetup         g_lifecycleSetup;
string             g_lifecycleStatus = "valid";

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
      Print("MedisTouch EA: failed to initialize one or more timeframe contexts.");
      return INIT_FAILED;
     }
   if(InpHtfObTF <= InpFVGTF || InpHtfObTF <= InpBOSTF)
      Print("MedisTouch EA: WARNING — InpHtfObTF (", EnumToString(InpHtfObTF),
            ") is not strictly higher than InpFVGTF/InpBOSTF. HTF Order Block confluence will be comparing zones on the same or a lower resolution than the entry timeframe, which defeats the point of the filter even if InpRequireHtfOB is left OFF for diagnostics only.");
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
   g_scoring.ConfigureSweepQuality(InpRequireMinSweepGrade, (ENUM_SWEEP_GRADE)InpMinSweepGrade,
                                   InpRequireFreshSetup, InpMaxBarsSinceBOS);
   g_scoring.ConfigureChaseFilter(InpRequireChaseFilter, InpMaxChaseDistATR);
   g_scoring.ConfigureFVGProximity(InpFVGMaxDistATR);
   g_scoring.ConfigureLearnedDiagnostics(InpDiagContradictionWeight, InpDiagEnvWeight, InpDiagExecWeight);
   g_scoring.ConfigureStrategyDiagnostics(InpMomentumBreakoutRecencyBars, InpBreakoutLiqOverlapBars,
                                          InpBreakoutExtensionLookbackBars, InpBreakoutExhaustionATRMult,
                                          InpMomentumLookbackBars);
   g_scoring.ConfigureMeanReversionDiagnostics(InpReversionMinStretchATR, InpReversionSRZoneATRTolerance,
                                               InpReversionWickRejectionRatio, InpReversionLiqRecencyBars,
                                               InpReversionTrendConflictRecencyBars, InpReversionTrendConflictMinStrength);
   g_scoring.ConfigureKeyLevelDiagnostics(InpKeyLevelLookbackBars, InpKeyLevelSearchATRMax,
                                          InpKeyLevelTouchToleranceATRMult, InpKeyLevelAbsorptionMinTouches,
                                          InpKeyLevelWickRejectionRatio, InpKeyLevelRoundStep);
   g_scoring.ConfigureStrategySelection(InpMinSelectionScore);
   g_decision.Init(&g_chartCtx.candles, g_fvgCtx, g_liqCtx, &g_scoring, InpSLBufferATR, InpMinStopSpreadMult);
   g_logger.Init(_Symbol, InpSessionGMTOffsetOverride);
   g_tracker.Init(&g_logger, _Symbol, InpFVGTF, InpMaxTrackingBars, InpFillPolicy, InpReplayTF);
   g_tracker.ConfigureSimulation(InpRiskPercentPerTrade, InpAllowMinLotOverride,
                                 InpBreakEvenAtR, InpPartialAtR, InpPartialFraction, InpTrailATRMult,
                                 InpSimCommissionPerLot, InpSimSpreadPoints, InpSimSlippagePoints);
   g_tracker.ConfigureCalibration(InpTrackOutcomes, InpCalibrationMinSample);
   g_tracker.ConfigureConfidenceDecay(InpDiagDecayHalfLifeBars);
   g_router.Init(_Symbol, InpEnableExecution, InpEnableSignals,
                InpMinConfidenceExecute, InpMinConfidenceSignal, InpFullRiskConfidence, InpMaxSpreadPoints);
   g_broker.Init(InpMagicNumber);
   g_monitor.Init(_Symbol, InpHeartbeatIntervalSec, InpMaxDrawdownAlertPercent);
   g_orders.Init(&g_broker, InpMaxOpenTrades, &g_monitor);
   // Dynamic-stop structural anchors must come from the EA execution/chart
   // timeframe. g_fvgCtx is a concept-specific timeframe (default M15) and
   // must not silently become the stop engine's structural source when the EA
   // is attached to H1/H4/etc. No synthetic structure is introduced.
   g_positions.Init(&g_orders, &g_broker, InpBreakEvenAtR, InpPartialAtR, InpPartialFraction, InpTrailATRMult,
                    0, 0.0, 0.0, 5, &g_chartCtx.swings);
   g_store.Init(_Symbol);
   g_subscribers.Init();
   g_publisher.Init(_Symbol, &g_subscribers, InpWebRequestTimeoutMs, InpBridgeApiKey);
   g_publisher.SetWeightVersion(InpWeightSetVersion);
   if(StringLen(InpConfigSyncEndpoint) > 0)
     {
      g_configSync.Init(_Symbol, InpConfigSyncEndpoint, InpBridgeApiKey, InpWeightSetVersion, InpWebRequestTimeoutMs);
      EventSetTimer(MathMax(60, InpConfigSyncPollMinutes * 60));
     }
   g_tracker.ConfigurePublishing(&g_publisher, InpWeightSetVersion);
   g_portfolio.Init(InpMaxPortfolioRiskPercent, InpMaxPositionsPerSymbol, InpMaxPositionsPerGroup, InpMagicNumber, &g_risk);
   g_riskGuard.Init(_Symbol, InpMaxDailyLossPercent, InpMaxDrawdownPercent, InpDeriskStartPercent, InpDeriskFloor);
   if(InpUseNewsFilter)
      g_newsFilter.Load(InpNewsFilterFile, InpNewsMinutesBefore, InpNewsMinutesAfter);
   g_scoring.ConfigureNewsAwareness(GetPointer(g_newsFilter), InpNewsWarnMinutesBefore,
                                    InpNewsWarnMinutesAfter, InpNewsWarnMultiplier);
   g_recovery.Init(&g_store, &g_orders, InpMagicNumber, _Symbol);
   int restoredCount = g_recovery.Recover();
   if(restoredCount > 0)
      PrintFormat("MedisTouch EA: recovery restored %d live trade(s) from a prior session.", restoredCount);
   TradeDecisionRecord priorDecisions[];
   int priorCount = g_store.LoadAll(priorDecisions);
   long maxId = 0;
   for(int i = 0; i < priorCount; i++)
      if(priorDecisions[i].decision_id > maxId) maxId = priorDecisions[i].decision_id;
   if(maxId > 0) g_router.SeedNextId(maxId + 1);
   if(!InpEnableExecution && !InpEnableSignals)
      Print("MedisTouch EA: both InpEnableExecution and InpEnableSignals are OFF. Analysis and logging still run, but nothing will be executed or published.");
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(StringLen(InpConfigSyncEndpoint) > 0)
      EventKillTimer();
   g_publisher.Deinit();
   g_subscribers.Deinit();
   g_store.Deinit();
  }

void OnTimer()
  {
   g_configSync.Poll();
  }

void CheckSignalLifecycle(double currentAtr)
  {
   if(g_lifecycleDecisionId == 0) return;
   bool filled; double fillPrice; datetime fillTime; int barsToFill;
   bool haveState = g_tracker.GetFillState(g_lifecycleCreationTime, filled, fillPrice, fillTime, barsToFill);
   if(!haveState) { g_lifecycleDecisionId = 0; return; }
   if(filled)
     {
      g_lifecycleDecisionId = 0;
      return;
     }
   bool isBuy = (g_lifecycleSetup.type == ORDER_TYPE_BUY);
   int barsSinceCreation = iBarShift(_Symbol, InpFVGTF, g_lifecycleCreationTime, false);
   if(barsSinceCreation >= InpSignalExpiryBars)
     {
      if(g_lifecycleStatus != "expired")
        {
         g_publisher.PublishStatusUpdate(g_lifecycleDecisionId, "expired",
                                         StringFormat("Unfilled for %d bars (max %d) — setup abandoned", barsSinceCreation, InpSignalExpiryBars));
         g_lifecycleStatus = "expired";
        }
      g_lifecycleDecisionId = 0;
      return;
     }
   double oppositeConfidence = g_scoring.CalculateConfidence(!isBuy);
   if(oppositeConfidence >= InpInvalidateOpposingConfidence)
     {
      if(g_lifecycleStatus != "invalidated")
        {
         g_publisher.PublishStatusUpdate(g_lifecycleDecisionId, "invalidated",
                                         StringFormat("Opposing setup confidence reached %.0f — original read contradicted", oppositeConfidence));
         g_lifecycleStatus = "invalidated";
        }
      g_lifecycleDecisionId = 0;
      return;
     }
   if(currentAtr > 0)
     {
      double entry = ResolveExecutionEntry(g_lifecycleSetup);
      double price = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double driftATR = MathAbs(price - entry) / currentAtr;
      bool wentWrongWay = isBuy ? (price > entry) : (price < entry);
      if(wentWrongWay && driftATR >= InpSignalStaleChaseATR)
        {
         if(g_lifecycleStatus != "stale")
           {
            g_publisher.PublishStatusUpdate(g_lifecycleDecisionId, "stale",
                                            StringFormat("Price drifted %.2f ATR past the entry zone, unfilled", driftATR));
            g_lifecycleStatus = "stale";
           }
        }
      else if(g_lifecycleStatus == "stale" && driftATR < InpSignalStaleChaseATR * 0.5)
        {
         g_publisher.PublishStatusUpdate(g_lifecycleDecisionId, "valid", "Price returned toward the entry zone");
         g_lifecycleStatus = "valid";
        }
     }
  }

void OnTick()
  {
   g_monitor.OnTickCheck();
   g_pool.DetectAll();
   if(g_chartCtx == NULL || !g_chartCtx.candles.IsReady()) return;
   double currentAtr = g_fvgCtx.candles.GetATR(0);
   g_positions.OnTick(currentAtr);
   g_orders.Prune();
   g_riskGuard.OnTick();
   if(InpPublishLifecycleUpdates)
      CheckSignalLifecycle(currentAtr);
   string haltReason;
   if(g_riskGuard.IsHardHalted(haltReason))
     {
      static datetime lastHaltLog = 0;
      if(TimeCurrent() - lastHaltLog > 3600) { PrintFormat("MedisTouch EA: no new trades — %s", haltReason); lastHaltLog = TimeCurrent(); }
      return;
     }
   if(g_riskGuard.IsDailyLossLimitHit(haltReason))
     {
      static datetime lastDailyLog = 0;
      if(TimeCurrent() - lastDailyLog > 3600) { PrintFormat("MedisTouch EA: no new trades — %s", haltReason); lastDailyLog = TimeCurrent(); }
      return;
     }
   string newsReason;
   if(InpUseNewsFilter && g_newsFilter.IsLocked(newsReason))
     {
      static datetime lastNewsLog = 0;
      if(TimeCurrent() - lastNewsLog > 300) { PrintFormat("MedisTouch EA: no new trades — %s", newsReason); lastNewsLog = TimeCurrent(); }
      return;
     }
   datetime barTime = iTime(_Symbol, _Period, 0);
   bool isNewBar = (barTime != g_lastBarTime);
   g_lastBarTime = barTime;
   if(!isNewBar) return;
   TradeSetup buySetup = g_decision.GenerateBuySetup();
   TradeSetup sellSetup = g_decision.GenerateSellSetup();
   TradeSetup chosen;
   ZeroMemory(chosen);
   double confDelta = buySetup.confidence - sellSetup.confidence;
   if(buySetup.active && sellSetup.active)
     {
      if(confDelta >= InpMinDirectionalAdvantage)
        {
         if(g_risk.ValidateSetup(buySetup, InpMinRiskReward, InpMaxSLDistanceATR, currentAtr))
            chosen = buySetup;
        }
      else if(-confDelta >= InpMinDirectionalAdvantage)
        {
         if(g_risk.ValidateSetup(sellSetup, InpMinRiskReward, InpMaxSLDistanceATR, currentAtr))
            chosen = sellSetup;
        }
     }
   else if(buySetup.active)
     {
      if(g_risk.ValidateSetup(buySetup, InpMinRiskReward, InpMaxSLDistanceATR, currentAtr))
         chosen = buySetup;
     }
   else if(sellSetup.active)
     {
      if(g_risk.ValidateSetup(sellSetup, InpMinRiskReward, InpMaxSLDistanceATR, currentAtr))
         chosen = sellSetup;
     }
   if(!chosen.active) return;
   if(chosen.creation_time == g_lastLoggedTime) return;
   g_lastLoggedTime = chosen.creation_time;
   chosen.calibrated_probability = g_tracker.GetCalibratedProbability(chosen.confidence,
                                                                       chosen.calibration_sample,
                                                                       chosen.calibration_has_enough_data);
   if(InpLogSignals)
     {
      ENUM_TREND_STATE t = g_trendCtx.trend.GetCurrentTrend();
      g_logger.LogSetup(chosen, _Symbol, InpFVGTF, EnumToString(t));
     }
   TradeDecisionRecord decision = g_router.Decide(chosen);
   if(InpTrackOutcomes)
      g_tracker.AddSetup(chosen, decision.decision_id);
   g_tracker.Update(g_fvgCtx);
   if(!decision.valid || decision.action == POLICY_IGNORE) return;
   g_store.Save(decision);
   if(decision.action == POLICY_EXECUTE_ONLY || decision.action == POLICY_EXECUTE_AND_SIGNAL)
     {
      double entry = ResolveExecutionEntry(chosen);
      bool exceededRiskBudget = false;
      double lots = g_risk.CalculateLotSize(_Symbol, InpRiskPercentPerTrade, entry, chosen.stop_loss,
                                            decision.reduce_risk, InpAllowMinLotOverride, exceededRiskBudget,
                                            g_riskGuard.SizeMultiplier());
      if(lots <= 0)
         PrintFormat("MedisTouch EA: decision #%d skipped — %.2f%% risk at this stop distance is below the broker's minimum lot for %s.",
                     decision.decision_id, InpRiskPercentPerTrade, _Symbol);
      else
        {
         if(exceededRiskBudget)
            PrintFormat("MedisTouch EA: decision #%d executing at broker-minimum lot (%.2f) — actual risk exceeds InpRiskPercentPerTrade (%.2f%%).",
                        decision.decision_id, lots, InpRiskPercentPerTrade);
         double proposedRisk = g_risk.RiskAmountForLots(_Symbol, lots, entry, chosen.stop_loss);
         string blockReason;
         if(!g_portfolio.AllowNewTrade(_Symbol, proposedRisk, blockReason))
            PrintFormat("MedisTouch EA: decision #%d blocked by Portfolio Manager — %s", decision.decision_id, blockReason);
         else
           {
            ulong ticketOut = 0;
            double maxDeviation = InpMaxEntryDeviationATR * currentAtr;
            if(g_orders.Submit(decision, lots, InpUseMarketOrders, maxDeviation, ticketOut))
               g_store.SaveExecution(decision.decision_id, lots, ticketOut);
            else
               g_monitor.NotifyBrokerReject();
           }
        }
     }
   if(decision.action == POLICY_SIGNAL_ONLY || decision.action == POLICY_EXECUTE_AND_SIGNAL)
     {
      g_publisher.Publish(decision);
      g_lifecycleDecisionId = decision.decision_id;
      g_lifecycleCreationTime = chosen.creation_time;
      g_lifecycleSetup = chosen;
      g_lifecycleStatus = "valid";
     }
  }

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal, DEAL_ENTRY) != DEAL_ENTRY_IN) return;
   if((ulong)HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagicNumber) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   ulong orderTicket    = (ulong)HistoryDealGetInteger(trans.deal, DEAL_ORDER);
   ulong positionTicket = (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   if(orderTicket == 0 || positionTicket == 0) return;
   double fillPrice = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   if(g_orders.MarkFilledFromPending(orderTicket, positionTicket, fillPrice))
      PrintFormat("MedisTouch EA: pending order #%d filled as position #%d at %.5f — caught live via OnTradeTransaction.",
                  orderTicket, positionTicket, fillPrice);
  }
//+------------------------------------------------------------------+
