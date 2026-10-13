#property copyright "Medis Touch"
#property version   "2.81"
#property strict

#include "includes/Core/Config.mqh"
#include "includes/Core/CandleData.mqh"
#include "includes/Core/SessionFilter.mqh" // direct dependency for operator-initiated session gating
#include "includes/Core/SignalLogger.mqh"
#include "includes/Analysis/TFContext.mqh"
#include "includes/Analysis/Scoring.mqh"
#include "includes/Trading/StrategyTradeZone.mqh"
#include "includes/Trading/EnvironmentStrategyMemory.mqh"
#include "includes/Trading/RiskEngine.mqh"
#include "includes/Trading/OutcomeTrackerLive.mqh"
#include "includes/Trading/DailyTradeTarget.mqh"
#include "includes/Decision/DecisionFingerprint.mqh"
#include "includes/Decision/DecisionEngine.mqh"
#include "includes/Decision/DecisionStore.mqh"
#include "includes/Execution/BrokerAdapter.mqh"
#include "includes/Execution/OrderManager.mqh"
#include "includes/Portfolio/MultiTradeEngine.mqh"
#include "includes/Execution/PositionManager.mqh"
#include "includes/Recovery/RecoveryEngine.mqh"
#include "includes/Portfolio/PortfolioManager.mqh"
#include "includes/Portfolio/RiskGuard.mqh"
#include "includes/Core/NewsFilter.mqh"
#include "includes/Signals/SubscriberPlatform.mqh"
#include "includes/Signals/SignalPublisher.mqh"
#include "includes/Signals/ConfigSync.mqh"
#include "includes/Monitoring/ProductionMonitor.mqh"
#include "includes/Execution/ExecutionAudit.mqh"
#include "includes/Execution/ExecutionLedgerClient.mqh"
#include "includes/UI/TradeControlPanel.mqh"

input group "General"
input int InpMaxHistoryBars=500;
input group "Structure"
input int InpSwingStrength=3;
input group "Per-Concept Timeframes"
input ENUM_TIMEFRAMES InpTrendTF=PERIOD_D1;
input ENUM_TIMEFRAMES InpBOSTF=PERIOD_H4;
input ENUM_TIMEFRAMES InpLiquidityTF=PERIOD_M15;
input ENUM_TIMEFRAMES InpFVGTF=PERIOD_M15;
input group "Fair Value Gaps"
input double InpFVGMinSizeATR=0.1;
input group "Liquidity"
input double InpInternalLiqThresholdATR=0.2;
input group "Risk (setup validation)"
input double InpMinRiskReward=1.5;
input double InpMaxSLDistanceATR=1.5;
input double InpSLBufferATR=0.25;
input double InpMinStopSpreadMult=3.0;
input double InpMaxEntryDeviationATR=0.15;
input group "Inducement Engine"
input int InpImpulseLookbackBars=40;
input double InpImpulseATRMult=1.2;
input double InpImpulseBodyRatio=0.6;
input double InpEqualTolATR=0.2;
input int InpMaxLegExtend=10;
input bool InpRequirePremiumDiscount=true;
input bool InpRequireDistributionPhase=false;
input int InpPhaseRangeLookback=20;
input double InpPhaseCompressionATRMult=2.5;
input group "Volume Engine (v2.6)"
input bool InpRequireVolumeConfirmation=true;
input double InpRVOLThreshold=1.5;
input int InpRVOLLookback=20;
input group "Fibonacci Engine (v2.6)"
input bool InpRequireFibonacciZone=true;
input double InpFibZoneMinPct=50.0;
input double InpFibZoneMaxPct=61.8;
input group "Value Area Engine (v2.6)"
input bool InpRequireValueAreaLocation=false;
input bool InpBlockValueAreaContradictions=true;
input int InpVALookbackBars=100;
input int InpVANumBins=24;
input double InpVAPercent=70.0;
input group "HTF Order Block Engine (v2.8)"
input ENUM_TIMEFRAMES InpHtfObTF=PERIOD_H4;
input bool InpRequireHtfOB=false;
input double InpOBDisplacementATRMult=1.5;
input double InpOBMinBodyRatio=0.5;
input double InpOBDistATRMax=2.0;
input group "Volatility Regime (v2.8)"
input bool InpBlockLowVolRegime=false;
input int InpVolRegimeLookback=100;
input double InpVolRegimeLowPct=0.25;
input double InpVolRegimeHighPct=0.75;
input group "Session Filter (v2.8)"
input bool InpUseSessionFilter=false; // OFF by default: London/NY is a liquidity policy, not a universal exchange calendar
input bool InpAllowTokyoSession=false;
input bool InpAllowLondonSession=true;
input bool InpAllowNewYorkSession=true;
input bool InpAllowLondonNYOverlap=true;
input group "Sweep Quality / Chase Filter / FVG Proximity (v2.9)"
input bool InpRequireMinSweepGrade=false;
input int InpMinSweepGrade=2;
input bool InpRequireFreshSetup=false;
input int InpMaxBarsSinceBOS=5;
input bool InpRequireChaseFilter=false;
input double InpMaxChaseDistATR=0.75;
input double InpFVGMaxDistATR=1.25;
input double InpMinDirectionalAdvantage=0.0;
input group "Signal Lifecycle (v2.9)"
input bool InpPublishLifecycleUpdates=false;
input int InpSignalExpiryBars=12;
input double InpSignalStaleChaseATR=1.0;
input double InpInvalidateOpposingConfidence=70.0;
input group "Confidence Diagnostics (v2.10) - measured, NOT acted on"
input double InpDiagContradictionWeight=0.25;
input double InpDiagEnvWeight=1.0;
input double InpDiagExecWeight=1.0;
input double InpDiagDecayHalfLifeBars=12.0;
input group "Strategy Diagnostics (v2.12) - measured, NOT acted on"
input int InpMomentumBreakoutRecencyBars=10;
input int InpBreakoutLiqOverlapBars=2;
input int InpBreakoutExtensionLookbackBars=15;
input double InpBreakoutExhaustionATRMult=3.0;
input int InpMomentumLookbackBars=10;
input group "Mean Reversion Diagnostics (v2.13) - measured, NOT acted on"
input double InpReversionMinStretchATR=1.0;
input double InpReversionSRZoneATRTolerance=0.25;
input double InpReversionWickRejectionRatio=0.55;
input int InpReversionLiqRecencyBars=10;
input int InpReversionTrendConflictRecencyBars=10;
input double InpReversionTrendConflictMinStrength=0.5;
input group "Key-Level Reaction Diagnostics (v2.14) - measured, NOT acted on"
input int InpKeyLevelLookbackBars=5;
input double InpKeyLevelSearchATRMax=3.0;
input double InpKeyLevelTouchToleranceATRMult=0.15;
input int InpKeyLevelAbsorptionMinTouches=3;
input double InpKeyLevelWickRejectionRatio=0.55;
input double InpKeyLevelRoundStep=0.0; // 0 = disabled; set explicitly per instrument when a psychological price grid is appropriate
input group "Strategy Selection (v2.15) - measured, NOT acted on"
input double InpMinSelectionScore=60.0;
input group "Adaptive Environment Memory"
input int InpEnvironmentMemoryMinSample=30;
input double InpEnvironmentMemoryBonus=2.0;
input double InpEnvironmentMemoryPenalty=2.0;
input group "Logging"
input bool InpLogSignals=true;
input bool InpTrackOutcomes=true;
input int InpMaxTrackingBars=100;
input int InpCalibrationMinSample=30;
input int InpSessionGMTOffsetOverride=999;
input ENUM_FILL_POLICY InpFillPolicy=FILL_CONSERVATIVE;
input ENUM_TIMEFRAMES InpReplayTF=PERIOD_M1;
input group "Policy — what this account does with a validated setup"
input bool InpEnableExecution=true;
input bool InpEnableSignals=true;
input double InpMinConfidenceExecute=68.0;
input double InpMinConfidenceSignal=58.0;
input double InpFullRiskConfidence=85.0;
input int InpMaxSpreadPoints=0;
input group "Execution"
input bool InpUseMarketOrders=true;
input double InpRiskPercentPerTrade=0.5;
input int InpMaxOpenTrades=3;
input ulong InpMagicNumber=987654321;
input bool InpAllowMinLotOverride=false;
input double InpMaxDailyLossPercent=3.0;
input double InpMaxDrawdownPercent=10.0;
input double InpDeriskStartPercent=5.0;
input double InpDeriskFloor=0.25;
input bool InpUseNewsFilter=false;
input string InpNewsFilterFile="MedisTouch_News.csv";
input int InpNewsMinutesBefore=15;
input int InpNewsMinutesAfter=5;
input int InpNewsWarnMinutesBefore=60;
input int InpNewsWarnMinutesAfter=30;
input double InpNewsWarnMultiplier=0.85;
input group "Position Management"
input double InpBreakEvenAtR=1.0;
input double InpPartialAtR=2.0;
input double InpPartialFraction=0.5;
input double InpTrailATRMult=1.5;
input group "Trade Simulator costs (v2.7)"
input double InpSimCommissionPerLot=7.0;
input double InpSimSpreadPoints=10.0;
input double InpSimSlippagePoints=2.0;
input group "Portfolio (account-wide, across every symbol this magic number trades)"
input double InpMaxPortfolioRiskPercent=3.0;
input int InpMaxPositionsPerSymbol=3;
input int InpMaxPositionsPerGroup=3;
input group "Portfolio — High-Probability Multi-Trade"
input bool InpEnableMultiTrade=true;
input double InpMultiTradeDualProbability=90.0;
input double InpMultiTradeTripleProbability=95.0;
input double InpMultiTradeMinRawConfidence=85.0;
input int InpMultiTradeMinCalibrationSample=30;
input bool InpRequireHedgingForMultiTrade=true;
input double InpMultiTradeDualLeg0RiskFraction=0.60;
input double InpMultiTradeDualLeg1RiskFraction=0.40;
input double InpMultiTradeTripleLeg0RiskFraction=0.50;
input double InpMultiTradeTripleLeg1RiskFraction=0.30;
input double InpMultiTradeTripleLeg2RiskFraction=0.20;
input group "Signal Transport"
input int InpWebRequestTimeoutMs=5000;
input string InpBridgeApiKey="";
input string InpExecutionLedgerBaseUrl=""; // Bridge root URL, e.g. https://your-service.onrender.com
input bool InpRequireExecutionLedger=true; // Fail closed for new EA entries until the broker-side ledger is reachable
input int InpExecutionLedgerRetrySeconds=30;
input string InpWeightSetVersion="v2.10-baseline";
input group "Decision Lineage"
input string InpDecisionSchemaVersion="decision-v1";
input string InpStrategyVersion="strategy-v1-integrated";
input string InpModelVersion="model-v1";
input string InpCalibrationVersion="calibration-v1";
input string InpFeatureSchemaVersion="feature-v1";
input string InpEnvironmentSchemaVersion="environment-v1";
input int InpMinimumQualifiedTradesPerDay=3;
input string InpConfigSyncEndpoint="";
input int InpConfigSyncPollMinutes=15;
input group "Production Monitoring"
input int InpHeartbeatIntervalSec=60;
input double InpMaxDrawdownAlertPercent=10.0;

input group "On-chart Trade Control"
input bool InpShowTradeControlPanel=true;
input double InpManualStopATR=1.25;          // ATR distance used by BUY/SELL buttons
input double InpManualRiskReward=2.0;       // Final TP R multiple; keep at least 0.3R above InpMinRiskReward
input bool InpUseCustomTradingSessions=false; // optional extra gate based on broker-server time
input bool InpSession1Enabled=true;
input string InpSession1Start="07:00";
input string InpSession1End="12:00";
input bool InpSession2Enabled=true;
input string InpSession2Start="13:00";
input string InpSession2End="17:00";
input bool InpSession3Enabled=false;
input string InpSession3Start="19:00";
input string InpSession3End="22:00";

CTFContextPool g_pool;CScoringEngine g_scoring;CSessionFilter g_operatorSessionFilter;CTradeDecision g_decision;CRiskEngine g_risk;CSignalLogger g_logger;COutcomeTrackerLive g_tracker;CEnvironmentStrategyMemory g_environmentMemory;CDecisionEngine g_router;CBrokerAdapter g_broker;COrderManager g_orders;CPositionManager g_positions;CRecoveryEngine g_recovery;CPortfolioManager g_portfolio;CMultiTradeEngine g_multiTrade;CRiskGuard g_riskGuard;CNewsFilter g_newsFilter;CSubscriberPlatform g_subscribers;CSignalPublisher g_publisher;CDailyTradeTarget g_dailyTradeTarget;CConfigSync g_configSync;CExecutionLedgerClient g_executionLedger;CProductionMonitor g_monitor;CTradeControlPanel g_controlPanel;CExecutionAudit g_execAudit;bool g_emergencyStop=false;bool g_executionLedgerHealthy=false;datetime g_lastLedgerReconcileAttempt=0;datetime g_lastConfigSyncPoll=0;datetime g_lastSessionBlockLog=0;CTFContext* g_chartCtx=NULL;CTFContext* g_trendCtx=NULL;CTFContext* g_bosCtx=NULL;CTFContext* g_liqCtx=NULL;CTFContext* g_fvgCtx=NULL;CTFContext* g_htfObCtx=NULL;
datetime g_lastLoggedTime=0,g_lastBarTime=0;long g_lifecycleDecisionId=0;datetime g_lifecycleCreationTime=0;TradeSetup g_lifecycleSetup;string g_lifecycleStatus="valid";bool g_panelInitialized=false;

string EmergencyStopGlobalKey();
bool IsConfiguredSessionAllowed();
bool IsNettingOrExchangeAccount();
bool HasAnyChartSymbolExposure();
void RefreshTradeControlPanel();
bool RiskRFromMoney(double riskMoney,double &riskR);
bool ReconcileBrokerStateSnapshot();
bool SyncHistoricalClosedPositions();
bool IsPositionIdentifierOpen(const ulong positionIdentifier);
bool ParseManagedOrderComment(const string comment,long &decisionId,int &legIndex);
bool PrepareLedgerForSubmit(const TradeDecisionRecord &decision,const int legIndex,const double riskMoney,const double volatility,string &requestId);
void MarkLedgerSubmissionAccepted(const string requestId);
void MarkLedgerSubmissionAmbiguous(const string requestId);
bool UpdateLedgerRiskForPosition(const ulong positionIdentifier,const string direction,const double volatility,const string evidenceRef);
bool IsOrderBuyDirection(const ENUM_ORDER_TYPE orderType);

int OnInit()
  {
   g_pool.Configure(_Symbol,InpMaxHistoryBars,InpSwingStrength,InpFVGMinSizeATR,InpInternalLiqThresholdATR,InpRVOLLookback,InpVALookbackBars,InpVANumBins,InpVAPercent/100.0,InpOBDisplacementATRMult,InpOBMinBodyRatio);g_chartCtx=g_pool.Get(_Period);g_trendCtx=g_pool.Get(InpTrendTF);g_bosCtx=g_pool.Get(InpBOSTF);g_liqCtx=g_pool.Get(InpLiquidityTF);g_fvgCtx=g_pool.Get(InpFVGTF);g_htfObCtx=g_pool.Get(InpHtfObTF);if(g_chartCtx==NULL||g_trendCtx==NULL||g_bosCtx==NULL||g_liqCtx==NULL||g_fvgCtx==NULL||g_htfObCtx==NULL)return INIT_FAILED;
   g_scoring.Init(g_trendCtx,g_bosCtx,g_liqCtx,g_fvgCtx,g_chartCtx,&g_chartCtx.candles);g_scoring.ConfigureInducement(InpImpulseLookbackBars,InpImpulseATRMult,InpImpulseBodyRatio,InpEqualTolATR,InpMaxLegExtend,InpRequirePremiumDiscount,InpRequireDistributionPhase,InpPhaseRangeLookback,InpPhaseCompressionATRMult);g_scoring.ConfigureVolumeFibonacci(InpRequireVolumeConfirmation,InpRVOLThreshold,InpRequireFibonacciZone,InpFibZoneMinPct,InpFibZoneMaxPct);g_scoring.ConfigureValueArea(InpRequireValueAreaLocation,InpBlockValueAreaContradictions);g_scoring.ConfigureHtfOrderBlock(g_htfObCtx,InpRequireHtfOB,InpOBDistATRMax);g_scoring.ConfigureVolatilityRegime(InpBlockLowVolRegime,InpVolRegimeLookback,InpVolRegimeLowPct,InpVolRegimeHighPct);g_scoring.ConfigureSessionFilter(InpUseSessionFilter,InpAllowTokyoSession,InpAllowLondonSession,InpAllowNewYorkSession,InpAllowLondonNYOverlap);g_operatorSessionFilter.Configure(InpUseSessionFilter,InpAllowTokyoSession,InpAllowLondonSession,InpAllowNewYorkSession,InpAllowLondonNYOverlap);g_scoring.ConfigureSweepQuality(InpRequireMinSweepGrade,(ENUM_SWEEP_GRADE)InpMinSweepGrade,InpRequireFreshSetup,InpMaxBarsSinceBOS);g_scoring.ConfigureChaseFilter(InpRequireChaseFilter,InpMaxChaseDistATR);g_scoring.ConfigureFVGProximity(InpFVGMaxDistATR);g_scoring.ConfigureLearnedDiagnostics(InpDiagContradictionWeight,InpDiagEnvWeight,InpDiagExecWeight);g_scoring.ConfigureStrategyDiagnostics(InpMomentumBreakoutRecencyBars,InpBreakoutLiqOverlapBars,InpBreakoutExtensionLookbackBars,InpBreakoutExhaustionATRMult,InpMomentumLookbackBars);g_scoring.ConfigureMeanReversionDiagnostics(InpReversionMinStretchATR,InpReversionSRZoneATRTolerance,InpReversionWickRejectionRatio,InpReversionLiqRecencyBars,InpReversionTrendConflictRecencyBars,InpReversionTrendConflictMinStrength);g_scoring.ConfigureKeyLevelDiagnostics(InpKeyLevelLookbackBars,InpKeyLevelSearchATRMax,InpKeyLevelTouchToleranceATRMult,InpKeyLevelAbsorptionMinTouches,InpKeyLevelWickRejectionRatio,InpKeyLevelRoundStep);g_scoring.ConfigureStrategySelection(InpMinSelectionScore);
   g_environmentMemory.Init(_Symbol,InpEnvironmentMemoryMinSample,InpEnvironmentMemoryBonus,InpEnvironmentMemoryPenalty);g_decision.Init(&g_chartCtx.candles,g_fvgCtx,g_liqCtx,&g_scoring,InpSLBufferATR,InpMinStopSpreadMult,InpFVGMaxDistATR,InpMinSelectionScore,g_chartCtx,g_bosCtx,GetPointer(g_environmentMemory));g_logger.Init(_Symbol,InpSessionGMTOffsetOverride);g_tracker.Init(&g_logger,_Symbol,_Period,InpMaxTrackingBars,InpFillPolicy,InpReplayTF);g_tracker.ConfigureEnvironmentMemory(GetPointer(g_environmentMemory));g_tracker.ConfigureSimulation(InpRiskPercentPerTrade,InpAllowMinLotOverride,InpBreakEvenAtR,InpPartialAtR,InpPartialFraction,InpTrailATRMult,InpSimCommissionPerLot,InpSimSpreadPoints,InpSimSlippagePoints);g_tracker.ConfigureCalibration(InpTrackOutcomes,InpCalibrationMinSample);g_tracker.ConfigureConfidenceDecay(InpDiagDecayHalfLifeBars);g_router.Init(_Symbol,InpEnableExecution,InpEnableSignals,InpMinConfidenceExecute,InpMinConfidenceSignal,InpFullRiskConfidence,InpMaxSpreadPoints);g_multiTrade.Init(InpEnableMultiTrade,InpMultiTradeDualProbability,InpMultiTradeTripleProbability,InpMultiTradeMinRawConfidence,InpMultiTradeMinCalibrationSample,InpMultiTradeDualLeg0RiskFraction,InpMultiTradeDualLeg1RiskFraction,InpMultiTradeTripleLeg0RiskFraction,InpMultiTradeTripleLeg1RiskFraction,InpMultiTradeTripleLeg2RiskFraction,InpRequireHedgingForMultiTrade);g_broker.Init(InpMagicNumber);g_monitor.Init(_Symbol,InpHeartbeatIntervalSec,InpMaxDrawdownAlertPercent);g_orders.Init(&g_broker,InpMaxOpenTrades,&g_monitor);g_positions.Init(&g_orders,&g_broker,InpBreakEvenAtR,InpPartialAtR,InpPartialFraction,InpTrailATRMult,0,0.0,0.0,5,&g_chartCtx.swings);g_store.Init(_Symbol);g_execAudit.Init(_Symbol,InpMagicNumber);g_emergencyStop=(GlobalVariableCheck(EmergencyStopGlobalKey()) && GlobalVariableGet(EmergencyStopGlobalKey())>0.5);if(InpShowTradeControlPanel || g_emergencyStop){g_panelInitialized=g_controlPanel.Init(ChartID(),_Symbol,InpMagicNumber);if(!g_panelInitialized)Print("MedisTouch: trade control panel could not create every chart object.");}g_execAudit.Log("INIT",StringFormat("version=2.81 magic=%I64u emergency_latched=%s account_margin_mode=%d",InpMagicNumber,g_emergencyStop?"true":"false",(int)AccountInfoInteger(ACCOUNT_MARGIN_MODE)));if((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING){g_execAudit.Log("ACCOUNT_MODE_WARNING","MT5 netting/exchange mode aggregates same-symbol exposure; isolate manual/other-EA activity before using close-all");Print("MedisTouch: WARNING — netting/exchange account may aggregate this symbol with other trade sources.");}g_dailyTradeTarget.Init(InpMinimumQualifiedTradesPerDay);g_subscribers.Init();g_publisher.Init(_Symbol,&g_subscribers,InpWebRequestTimeoutMs,InpBridgeApiKey);g_publisher.SetWeightVersion(InpWeightSetVersion);
   if(StringLen(InpConfigSyncEndpoint)>0){g_configSync.Init(_Symbol,InpConfigSyncEndpoint,InpBridgeApiKey,InpWeightSetVersion,InpWebRequestTimeoutMs);EventSetTimer(MathMax(60,InpConfigSyncPollMinutes*60));}g_tracker.ConfigurePublishing(&g_publisher,InpWeightSetVersion);g_portfolio.Init(InpMaxPortfolioRiskPercent,InpMaxPositionsPerSymbol,InpMaxPositionsPerGroup,InpMagicNumber,&g_risk);g_riskGuard.Init(_Symbol,InpMaxDailyLossPercent,InpMaxDrawdownPercent,InpDeriskStartPercent,InpDeriskFloor);if(InpUseNewsFilter)g_newsFilter.Load(InpNewsFilterFile,InpNewsMinutesBefore,InpNewsMinutesAfter);g_scoring.ConfigureNewsAwareness(GetPointer(g_newsFilter),InpNewsWarnMinutesBefore,InpNewsWarnMinutesAfter,InpNewsWarnMultiplier);g_recovery.Init(&g_store,&g_orders,InpMagicNumber,_Symbol);int restored=g_recovery.Recover();if(restored>0)PrintFormat("MedisTouch EA: recovery restored %d live trade(s).",restored);TradeDecisionRecord prior[];int n=g_store.LoadAll(prior);long maxId=0;for(int i=0;i<n;i++)if(prior[i].decision_id>maxId)maxId=prior[i].decision_id;if(maxId>0)g_router.SeedNextId(maxId+1);return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason){if(StringLen(InpConfigSyncEndpoint)>0)EventKillTimer();g_execAudit.Log("DEINIT",StringFormat("reason=%d",reason));if(g_panelInitialized)g_controlPanel.Destroy();g_publisher.Deinit();g_subscribers.Deinit();g_store.Deinit();}
void OnTimer(){if(StringLen(InpConfigSyncEndpoint)>0)g_configSync.Poll();}
void CheckSignalLifecycle(double atr){if(g_lifecycleDecisionId==0)return;bool filled;double fillPrice;datetime fillTime;int barsToFill;if(!g_tracker.GetFillState(g_lifecycleCreationTime,g_lifecycleDecisionId,filled,fillPrice,fillTime,barsToFill)){g_lifecycleDecisionId=0;return;}if(filled){g_lifecycleDecisionId=0;return;}bool buy=g_lifecycleSetup.type==ORDER_TYPE_BUY;int barsSince=iBarShift(_Symbol,_Period,g_lifecycleCreationTime,false);if(barsSince>=InpSignalExpiryBars){if(g_lifecycleStatus!="expired"){g_publisher.PublishStatusUpdate(g_lifecycleDecisionId,"expired",StringFormat("Unfilled for %d execution bars",barsSince));g_lifecycleStatus="expired";}g_lifecycleDecisionId=0;return;}double opposite=g_scoring.CalculateConfidence(!buy);if(opposite>=InpInvalidateOpposingConfidence){if(g_lifecycleStatus!="invalidated"){g_publisher.PublishStatusUpdate(g_lifecycleDecisionId,"invalidated",StringFormat("Opposing confidence %.0f",opposite));g_lifecycleStatus="invalidated";}g_lifecycleDecisionId=0;return;}if(atr>0){double entry=ResolveExecutionEntry(g_lifecycleSetup);double price=buy?SymbolInfoDouble(_Symbol,SYMBOL_ASK):SymbolInfoDouble(_Symbol,SYMBOL_BID);double drift=MathAbs(price-entry)/atr;bool wrong=buy?(price>entry):(price<entry);if(wrong&&drift>=InpSignalStaleChaseATR){if(g_lifecycleStatus!="stale"){g_publisher.PublishStatusUpdate(g_lifecycleDecisionId,"stale",StringFormat("Price drifted %.2f ATR past entry",drift));g_lifecycleStatus="stale";}}else if(g_lifecycleStatus=="stale"&&drift<InpSignalStaleChaseATR*0.5){g_publisher.PublishStatusUpdate(g_lifecycleDecisionId,"valid","Price returned toward entry");g_lifecycleStatus="valid";}}}
void OnTick(){g_monitor.OnTickCheck();g_dailyTradeTarget.OnTick();g_pool.DetectAll();if(g_chartCtx==NULL||!g_chartCtx.candles.IsReady())return;double atr=g_chartCtx.candles.GetATR(0);g_positions.OnTick(atr);g_orders.Prune();g_riskGuard.OnTick();RefreshTradeControlPanel();if(g_emergencyStop)return;if(InpPublishLifecycleUpdates)CheckSignalLifecycle(atr);datetime barTime=iTime(_Symbol,_Period,0);bool isNewBar=(barTime!=g_lastBarTime);g_lastBarTime=barTime;if(!isNewBar)return;if(InpTrackOutcomes)g_tracker.Update(g_chartCtx);string haltReason;if(g_riskGuard.IsHardHalted(haltReason))return;if(g_riskGuard.IsDailyLossLimitHit(haltReason))return;string newsReason;if(InpUseNewsFilter&&g_newsFilter.IsLocked(newsReason))return;if(!IsConfiguredSessionAllowed()){if(TimeCurrent()-g_lastSessionBlockLog>=900){g_execAudit.Log("SESSION_BLOCK","new automated entries suppressed outside configured session windows");g_lastSessionBlockLog=TimeCurrent();}return;}TradeSetup buySetup=g_decision.GenerateBuySetup();TradeSetup sellSetup=g_decision.GenerateSellSetup();TradeSetup chosen;ZeroMemory(chosen);double delta=buySetup.confidence-sellSetup.confidence;if(buySetup.active&&sellSetup.active){if(delta>=InpMinDirectionalAdvantage){if(g_risk.ValidateSetup(buySetup,InpMinRiskReward,InpMaxSLDistanceATR,atr))chosen=buySetup;}else if(-delta>=InpMinDirectionalAdvantage){if(g_risk.ValidateSetup(sellSetup,InpMinRiskReward,InpMaxSLDistanceATR,atr))chosen=sellSetup;}}else if(buySetup.active){if(g_risk.ValidateSetup(buySetup,InpMinRiskReward,InpMaxSLDistanceATR,atr))chosen=buySetup;}else if(sellSetup.active){if(g_risk.ValidateSetup(sellSetup,InpMinRiskReward,InpMaxSLDistanceATR,atr))chosen=sellSetup;}if(!chosen.active||chosen.creation_time==g_lastLoggedTime)return;g_lastLoggedTime=chosen.creation_time;chosen.calibrated_probability=g_tracker.GetCalibratedProbability(chosen.confidence,chosen.calibration_sample,chosen.calibration_has_enough_data);if(InpLogSignals){ENUM_TREND_STATE t=g_trendCtx.trend.GetCurrentTrend();g_logger.LogSetup(chosen,_Symbol,InpFVGTF,EnumToString(t));}TradeDecisionRecord decision=g_router.Decide(chosen);g_execAudit.Log("DECISION",StringFormat("automated candidate action=%s confidence=%.1f reason=%s",TradePolicyToString(decision.action),decision.confidence,decision.reason),decision.decision_id,0,0.0,ResolveExecutionEntry(chosen),chosen.stop_loss,chosen.final_tp);decision.timeframe=_Period;decision.decision_schema_version=InpDecisionSchemaVersion;decision.strategy_version=InpStrategyVersion;decision.model_version=InpModelVersion;decision.calibration_version=InpCalibrationVersion;decision.feature_schema_version=InpFeatureSchemaVersion;decision.environment_schema_version=InpEnvironmentSchemaVersion;decision.weight_version=InpWeightSetVersion;decision.environment_key=g_environmentMemory.Key(chosen.reasons);decision.spread_points=chosen.reasons.spread_points;decision.decision_fingerprint=DecisionFingerprintFor(decision);if(InpTrackOutcomes)g_tracker.AddSetup(chosen,decision.decision_id,decision.decision_fingerprint);if(!decision.valid||decision.action==POLICY_IGNORE)return;if(!g_store.Save(decision)){PrintFormat("MedisTouch EA: decision #%I64d rejected — durable DecisionStore write failed.",decision.decision_id);return;}if(decision.action==POLICY_EXECUTE_ONLY||decision.action==POLICY_EXECUTE_AND_SIGNAL){if(IsNettingOrExchangeAccount() && HasAnyChartSymbolExposure()){g_execAudit.Log("AUTOMATED_BLOCKED_NETTING_EXPOSURE",StringFormat("decision #%I64d suppressed: same-symbol position or pending order already exists on netting/exchange account",decision.decision_id),decision.decision_id);}else{int availableSlots=InpMaxOpenTrades-g_orders.OpenCount();if(availableSlots<0)availableSlots=0;MultiTradePlan plan;bool planOk=g_multiTrade.Build(decision.setup,availableSlots,plan);if(!planOk){PrintFormat("MedisTouch EA: decision #%I64d rejected — multi-trade plan construction failed.",decision.decision_id);return;}double entry=ResolveExecutionEntry(chosen);double legLots[3];double legRisk[3];for(int leg=0;leg<3;leg++){legLots[leg]=0.0;legRisk[leg]=0.0;}bool sizingOk=true;for(int leg=0;leg<plan.legCount;leg++){double fraction=plan.riskFraction[leg];bool exceeded=false;legLots[leg]=g_risk.CalculateLotSize(_Symbol,InpRiskPercentPerTrade*fraction,entry,chosen.stop_loss,decision.reduce_risk,InpAllowMinLotOverride,exceeded,g_riskGuard.SizeMultiplier());if(legLots[leg]<=0.0){sizingOk=false;break;}legRisk[leg]=g_risk.RiskAmountForLots(_Symbol,legLots[leg],entry,chosen.stop_loss);}if(!sizingOk){PrintFormat("MedisTouch EA: decision #%I64d skipped — one or more execution legs cannot satisfy broker lot/risk constraints.",decision.decision_id);return;}double totalProposedRisk=0.0;for(int leg=0;leg<plan.legCount;leg++)totalProposedRisk+=legRisk[leg];string block;if(!g_portfolio.AllowNewTradeBatch(_Symbol,totalProposedRisk,plan.legCount,block)){PrintFormat("MedisTouch EA: decision #%I64d blocked — %s",decision.decision_id,block);return;}ulong tickets[3];bool submittedAny=false;double maxDeviation=InpMaxEntryDeviationATR*atr;for(int leg=0;leg<plan.legCount;leg++){TradeDecisionRecord legDecision=decision;legDecision.setup.final_tp=plan.target[leg];legDecision.reason+=StringFormat("; multi-trade leg %d/%d (%s)",leg+1,plan.legCount,plan.label[leg]);ulong ticket=0;if(g_orders.Submit(legDecision,legLots[leg],InpUseMarketOrders,maxDeviation,ticket,leg)){submittedAny=true;tickets[leg]=ticket;if(!g_store.SaveExecution(decision.decision_id,legLots[leg],ticket,leg,plan.target[leg])){PrintFormat("CRITICAL: decision #%I64d leg %d executed but execution record was not durably persisted.",decision.decision_id,leg);g_execAudit.Log("CRITICAL_EXECUTION_RECORD_FAILURE","automated order submitted but execution persistence failed",decision.decision_id,ticket,legLots[leg],entry,chosen.stop_loss,plan.target[leg]);}else g_execAudit.Log("ORDER_SUBMITTED",StringFormat("automated leg %d/%d",leg+1,plan.legCount),decision.decision_id,ticket,legLots[leg],entry,chosen.stop_loss,plan.target[leg]);}else{g_monitor.NotifyBrokerReject();g_execAudit.Log("ORDER_REJECTED","automated broker/order-manager submission failed",decision.decision_id,0,legLots[leg],entry,chosen.stop_loss,plan.target[leg]);}}if(!submittedAny)PrintFormat("MedisTouch EA: decision #%I64d rejected by broker on every requested execution leg.",decision.decision_id);}}if(decision.action==POLICY_SIGNAL_ONLY||decision.action==POLICY_EXECUTE_AND_SIGNAL){g_publisher.Publish(decision);g_lifecycleDecisionId=decision.decision_id;g_lifecycleCreationTime=chosen.creation_time;g_lifecycleSetup=chosen;g_lifecycleStatus="valid";}}
// Persistent per-symbol/per-magic emergency latch. A normal terminal restart
// does not silently re-enable order entry after the operator presses STOP.
string EmergencyStopGlobalKey()
  {
   string key="MIDAS_STOP_"+_Symbol+"_"+IntegerToString((long)InpMagicNumber);
   StringReplace(key,".","_");
   StringReplace(key,"#","_");
   if(StringLen(key)>63) key=StringSubstr(key,0,63);
   return key;
  }

int ParseSessionMinute(const string value)
  {
   string fields[];
   ushort colon=StringGetCharacter(":",0);
   if(StringSplit(value,colon,fields)!=2) return -1;
   int hour=(int)StringToInteger(fields[0]);
   int minute=(int)StringToInteger(fields[1]);
   if(hour<0 || hour>23 || minute<0 || minute>59) return -1;
   return hour*60+minute;
  }

bool SessionWindowContains(int nowMinute,int startMinute,int endMinute)
  {
   if(startMinute<0 || endMinute<0 || startMinute==endMinute) return false;
   if(startMinute<endMinute) return (nowMinute>=startMinute && nowMinute<endMinute);
   // A window such as 22:00-02:00 crosses midnight.
   return (nowMinute>=startMinute || nowMinute<endMinute);
  }

bool IsConfiguredSessionAllowed()
  {
   if(!InpUseCustomTradingSessions) return true;
   datetime now=TimeTradeServer();
   if(now<=0) now=TimeCurrent();
   MqlDateTime parts;
   TimeToStruct(now,parts);
   int minuteOfDay=parts.hour*60+parts.min;
   if(InpSession1Enabled)
     {
      int start=ParseSessionMinute(InpSession1Start),finish=ParseSessionMinute(InpSession1End);
      if(SessionWindowContains(minuteOfDay,start,finish)) return true;
     }
   if(InpSession2Enabled)
     {
      int start=ParseSessionMinute(InpSession2Start),finish=ParseSessionMinute(InpSession2End);
      if(SessionWindowContains(minuteOfDay,start,finish)) return true;
     }
   if(InpSession3Enabled)
     {
      int start=ParseSessionMinute(InpSession3Start),finish=ParseSessionMinute(InpSession3End);
      if(SessionWindowContains(minuteOfDay,start,finish)) return true;
     }
   // Fail closed if enabled session definitions are invalid or no valid
   // windows exist. Existing DST-aware session policy is unchanged when off.
   return false;
  }

string ControlPanelSessionStatus()
  {
   bool customAllowed=IsConfiguredSessionAllowed();
   bool dstAllowed=g_operatorSessionFilter.IsAllowed();
   if(InpUseCustomTradingSessions && InpUseSessionFilter)
      return (customAllowed && dstAllowed) ? "CUSTOM + DST OPEN" : "SESSION BLOCKED";
   if(InpUseCustomTradingSessions)
      return customAllowed ? "CUSTOM OPEN" : "CUSTOM CLOSED";
   if(InpUseSessionFilter)
      return dstAllowed ? "DST SESSION OPEN" : "DST SESSION CLOSED";
   return "ALL HOURS";
  }

void RefreshTradeControlPanel()
  {
   if(!g_panelInitialized) return;
   int count=0;
   double floating=0.0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=InpMagicNumber) continue;
      count++;
      floating+=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
     }
   g_controlPanel.Refresh(count,floating,InpEnableDynamicStop,g_emergencyStop,ControlPanelSessionStatus());
  }

void CloseAllManagedExposure(const string reason)
  {
   int cancelled=0,closed=0,failed=0;
   // Cancel orders represented in the state machine first.
   for(int i=g_orders.Total()-1;i>=0;i--)
     {
      ENUM_TRADE_STATE state=g_orders.StateAt(i);
      if(state!=TS_PENDING && state!=TS_WAITING) continue;
      ulong ticket=g_orders.TicketAt(i);
      if(ticket>0 && g_orders.CancelPendingAt(i))
        {
         cancelled++;
         g_execAudit.Log("PENDING_CANCEL",reason,g_orders.DecisionAt(i).decision_id,ticket);
        }
     }
   // Include matching broker pending orders not present in the local store.
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong order=OrderGetTicket(i);
      if(order==0) continue;
      if(OrderGetString(ORDER_SYMBOL)!=_Symbol) continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC)!=InpMagicNumber) continue;
      if(g_broker.CancelOrder(order))
        {
         cancelled++;
         g_execAudit.Log("PENDING_CANCEL",reason,0,order);
        }
      else failed++;
     }
   // Scope is deliberately this chart symbol + this EA's magic number.
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=InpMagicNumber) continue;
      double volume=PositionGetDouble(POSITION_VOLUME);
      double price=PositionGetDouble(POSITION_PRICE_CURRENT);
      if(g_broker.CloseFull(ticket))
        {
         closed++;
         g_execAudit.Log("POSITION_CLOSE",reason,g_orders.DecisionIdForTicket(ticket),ticket,volume,price);
        }
      else
        {
         failed++;
         g_execAudit.Log("POSITION_CLOSE_FAILED",reason,g_orders.DecisionIdForTicket(ticket),ticket,volume,price);
        }
     }
   g_execAudit.Log("CLOSE_ALL_SUMMARY",StringFormat("reason=%s closed=%d cancelled=%d failed=%d",reason,closed,cancelled,failed));
   RefreshTradeControlPanel();
  }

void EmergencyStop()
  {
   g_emergencyStop=true;
   GlobalVariableSet(EmergencyStopGlobalKey(),1.0);
   g_execAudit.Log("EMERGENCY_STOP","latched; new entries blocked and managed exposure is being flattened");
   CloseAllManagedExposure("emergency-stop");
  }

bool HasManagedExposure()
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol &&
         (ulong)PositionGetInteger(POSITION_MAGIC)==InpMagicNumber) return true;
     }
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong ticket=OrderGetTicket(i);
      if(ticket==0) continue;
      if(OrderGetString(ORDER_SYMBOL)==_Symbol &&
         (ulong)OrderGetInteger(ORDER_MAGIC)==InpMagicNumber) return true;
     }
   return false;
  }

void ResumeTrading()
  {
   if(HasManagedExposure())
     {
      g_execAudit.Log("EMERGENCY_RESUME_BLOCKED","managed positions or pending orders remain open; stop latch retained");
      Print("MedisTouch: RESUME refused — close/verify all positions and pending orders for this symbol/magic first.");
      return;
     }
   GlobalVariableDel(EmergencyStopGlobalKey());
   g_emergencyStop=false;
   g_execAudit.Log("EMERGENCY_RESUME","operator cleared persistent emergency latch after exposure check");
   if(!InpShowTradeControlPanel && g_panelInitialized)
     {
      g_controlPanel.Destroy();
      g_panelInitialized=false;
     }
   RefreshTradeControlPanel();
  }

bool IsNettingOrExchangeAccount()
  {
   return (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING;
  }

// Netting/exchange accounts aggregate all activity for a symbol into one position.
// Manual BUY/SELL must not accidentally net, reverse, or inherit another trade's identity.
bool HasAnyChartSymbolExposure()
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol) return true;
     }
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong ticket=OrderGetTicket(i);
      if(ticket==0) continue;
      if(OrderGetString(ORDER_SYMBOL)==_Symbol) return true;
     }
   return false;
  }

void ManualMarketEntry(bool isBuy)
  {
   string side=isBuy ? "BUY" : "SELL";
   if(g_emergencyStop) { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected: emergency stop is latched"); return; }
   if(!InpEnableExecution) { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected: InpEnableExecution=false"); return; }
   if(IsNettingOrExchangeAccount() && HasAnyChartSymbolExposure())
     { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected: netting/exchange account already has same-symbol position or pending order; resolve it before another manual entry"); return; }
   if(!g_operatorSessionFilter.IsAllowed()) { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected: outside DST-aware trading sessions"); return; }
   if(!IsConfiguredSessionAllowed()) { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected: outside configured server-time sessions"); return; }
   string haltReason;
   if(g_riskGuard.IsHardHalted(haltReason) || g_riskGuard.IsDailyLossLimitHit(haltReason))
     { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected by risk guard: "+haltReason); return; }
   string newsReason;
   if(InpUseNewsFilter && g_newsFilter.IsLocked(newsReason))
     { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected by news filter: "+newsReason); return; }
   if(g_orders.OpenCount()>=InpMaxOpenTrades)
     { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected: maximum open trade count reached"); return; }

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick)) { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected: no current tick"); return; }
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   double atr=(g_chartCtx!=NULL ? g_chartCtx.candles.GetATR(0) : 0.0);
   if(point<=0.0 || atr<=0.0 || InpManualStopATR<=0.0 || InpManualRiskReward<InpMinRiskReward+0.3)
     { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected: invalid point/ATR/manual risk parameters"); return; }
   double entry=isBuy ? tick.ask : tick.bid;
   double spreadPoints=(tick.ask-tick.bid)/point;
   if(InpMaxSpreadPoints>0 && spreadPoints>InpMaxSpreadPoints)
     { g_execAudit.Log("MANUAL_BLOCKED",StringFormat("%s spread %.1f exceeds limit %d",side,spreadPoints,InpMaxSpreadPoints)); return; }

   double riskDistance=MathMax(atr*InpManualStopATR,spreadPoints*point*MathMax(1.0,InpMinStopSpreadMult));
   double stop=isBuy ? entry-riskDistance : entry+riskDistance;
   double buffer=MathMin(riskDistance*0.20,MathMax(point*2.0,riskDistance*0.05));
   TradeSetup setup;
   ZeroMemory(setup);
   setup.type=isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   setup.entry_top=entry;
   setup.entry_bottom=entry;
   setup.stop_loss=NormalizeDouble(stop,_Digits);
   setup.invalidation=NormalizeDouble(isBuy ? stop+buffer : stop-buffer,_Digits);
   double risk=MathAbs(entry-setup.stop_loss);
   double tp1R=InpMinRiskReward+0.1; // CRiskEngine validates R:R against TP1, not final_tp.
   double tp2R=(tp1R+InpManualRiskReward)*0.5;
   setup.tp1=NormalizeDouble(isBuy ? entry+risk*tp1R : entry-risk*tp1R,_Digits);
   setup.tp2=NormalizeDouble(isBuy ? entry+risk*tp2R : entry-risk*tp2R,_Digits);
   setup.final_tp=NormalizeDouble(isBuy ? entry+risk*InpManualRiskReward : entry-risk*InpManualRiskReward,_Digits);
   setup.confidence=100.0;
   setup.creation_time=TimeCurrent();
   setup.active=true;
   setup.reasons.selected_strategy=STRATEGY_NONE;
   setup.reasons.session_ok=true;
   if(!g_risk.ValidateSetup(setup,InpMinRiskReward,InpMaxSLDistanceATR,atr))
     { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected by stop/target validation",0,0,0.0,entry,setup.stop_loss,setup.final_tp); return; }

   TradeDecisionRecord decision;
   ZeroMemory(decision);
   decision.decision_id=g_router.AllocateId();
   decision.symbol=_Symbol;
   decision.setup=setup;
   decision.action=POLICY_EXECUTE_ONLY;
   decision.valid=true;
   decision.confidence=setup.confidence;
   decision.spread_points=spreadPoints;
   decision.decided_time=TimeCurrent();
   decision.reason="operator chart control";
   decision.timeframe=_Period;
   decision.decision_schema_version=InpDecisionSchemaVersion;
   decision.strategy_version=InpStrategyVersion;
   decision.model_version=InpModelVersion;
   decision.calibration_version=InpCalibrationVersion;
   decision.feature_schema_version=InpFeatureSchemaVersion;
   decision.environment_schema_version=InpEnvironmentSchemaVersion;
   decision.weight_version=InpWeightSetVersion;
   decision.environment_key="manual_operator";
   decision.decision_fingerprint=DecisionFingerprintFor(decision);

   bool exceededMinLot=false;
   double lots=g_risk.CalculateLotSize(_Symbol,InpRiskPercentPerTrade,entry,setup.stop_loss,
                                      decision.reduce_risk,InpAllowMinLotOverride,exceededMinLot,
                                      g_riskGuard.SizeMultiplier());
   if(lots<=0.0)
     { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected: broker lot/risk sizing returned zero",decision.decision_id,0,0.0,entry,setup.stop_loss,setup.final_tp); return; }
   double proposedRisk=g_risk.RiskAmountForLots(_Symbol,lots,entry,setup.stop_loss);
   string portfolioReason;
   if(!g_portfolio.AllowNewTradeBatch(_Symbol,proposedRisk,1,portfolioReason))
     { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected by portfolio risk guard: "+portfolioReason,decision.decision_id,0,lots,entry,setup.stop_loss,setup.final_tp); return; }
   if(!g_store.Save(decision))
     { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected: durable decision write failed",decision.decision_id,0,lots,entry,setup.stop_loss,setup.final_tp); return; }
   // Deliberate operator entries are execution-audited but excluded from strategy calibration
   // and EnvironmentStrategyMemory, preventing manual discretion from contaminating model evidence.

   ulong ticket=0;
   double maxDeviation=InpMaxEntryDeviationATR*atr;
   if(!g_orders.Submit(decision,lots,true,maxDeviation,ticket,0))
     {
      g_monitor.NotifyBrokerReject();
      g_execAudit.Log("MANUAL_REJECTED",side+" market request rejected by execution layer",decision.decision_id,0,lots,entry,setup.stop_loss,setup.final_tp);
      return;
     }
   if(!g_store.SaveExecution(decision.decision_id,lots,ticket,0,setup.final_tp))
      g_execAudit.Log("CRITICAL_EXECUTION_RECORD_FAILURE","manual order submitted but execution persistence failed",decision.decision_id,ticket,lots,entry,setup.stop_loss,setup.final_tp);
   else
      g_execAudit.Log("MANUAL_ORDER_SUBMITTED",side+" chart button",decision.decision_id,ticket,lots,entry,setup.stop_loss,setup.final_tp);
  }

void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(!g_panelInitialized || id!=CHARTEVENT_OBJECT_CLICK) return;
   int command=g_controlPanel.CommandForClick(sparam);
   if(command==PANEL_ACTION_BUY) ManualMarketEntry(true);
   else if(command==PANEL_ACTION_SELL) ManualMarketEntry(false);
   else if(command==PANEL_ACTION_CLOSE_ALL) CloseAllManagedExposure("operator-close-all");
   else if(command==PANEL_ACTION_EMERGENCY_STOP) EmergencyStop();
   else if(command==PANEL_ACTION_RESUME) ResumeTrading();
   RefreshTradeControlPanel();
  }

void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
  {
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD || trans.deal==0) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal,DEAL_SYMBOL)!=_Symbol) return;
   if((ulong)HistoryDealGetInteger(trans.deal,DEAL_MAGIC)!=InpMagicNumber) return;

   ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal,DEAL_ENTRY);
   ulong positionIdentifier=(ulong)HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID);
   if(positionIdentifier==0) return;

   datetime dealTime=(datetime)HistoryDealGetInteger(trans.deal,DEAL_TIME);
   double price=HistoryDealGetDouble(trans.deal,DEAL_PRICE);
   double volume=HistoryDealGetDouble(trans.deal,DEAL_VOLUME);
   ulong positionTicket=g_broker.PositionTicketForIdentifier(_Symbol,positionIdentifier);
   // Preserve the stable identifier as a temporary token if a just-executed
   // position has not appeared in the terminal snapshot yet. The order manager
   // repairs the token to a selectable POSITION_TICKET on the next resolution.
   if(positionTicket==0) positionTicket=positionIdentifier;

   long decisionId=-1;
   if(entry==DEAL_ENTRY_IN)
     {
      g_dailyTradeTarget.OnExecution(dealTime);
      ulong orderTicket=(ulong)HistoryDealGetInteger(trans.deal,DEAL_ORDER);
      g_orders.MarkFilledFromPending(orderTicket,positionTicket,price);
      g_orders.BindPositionIdentity(orderTicket,positionIdentifier,positionTicket);
      decisionId=g_orders.DecisionIdForPositionIdentifier(positionIdentifier);
      if(decisionId<=0) decisionId=g_orders.DecisionIdForTicket(positionTicket);

      double entryCommission=HistoryDealGetDouble(trans.deal,DEAL_COMMISSION);
      double entrySwap=HistoryDealGetDouble(trans.deal,DEAL_SWAP);
      double entryFee=HistoryDealGetDouble(trans.deal,DEAL_FEE);
      if(decisionId>0)
         g_tracker.MarkExecuted(decisionId,price,dealTime,volume,trans.deal,entryCommission,entrySwap,entryFee,true);

      double loggedSL=0.0,loggedTP=0.0;
      if(g_broker.PositionTicketForIdentifier(_Symbol,positionIdentifier)>0 &&
         PositionSelectByTicket(g_broker.PositionTicketForIdentifier(_Symbol,positionIdentifier)))
        {
         loggedSL=PositionGetDouble(POSITION_SL);
         loggedTP=PositionGetDouble(POSITION_TP);
        }
      g_execAudit.Log("FILL_IN",
                      StringFormat("deal=%I64u position_id=%I64u",trans.deal,positionIdentifier),
                      decisionId,positionTicket,volume,price,loggedSL,loggedTP);
      return;
     }

   if(entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY || entry==DEAL_ENTRY_INOUT)
     {
      decisionId=g_orders.DecisionIdForPositionIdentifier(positionIdentifier);
      // Compatibility fallback for positions recovered by older builds before
      // stable position identifiers were retained by the order manager.
      if(decisionId<=0) decisionId=g_orders.DecisionIdForTicket(positionIdentifier);
      if(decisionId<=0) return;

      double profit=HistoryDealGetDouble(trans.deal,DEAL_PROFIT);
      double commission=HistoryDealGetDouble(trans.deal,DEAL_COMMISSION);
      double swap=HistoryDealGetDouble(trans.deal,DEAL_SWAP);
      double fee=HistoryDealGetDouble(trans.deal,DEAL_FEE);
      double net=profit+commission+swap+fee;
      bool samePositionStillOpen=(g_broker.PositionTicketForIdentifier(_Symbol,positionIdentifier)>0);
      g_orders.MarkPositionExitByIdentifier(positionIdentifier,samePositionStillOpen);
      bool stillOpen=g_orders.HasLiveTradeForDecision(decisionId);
      ENUM_DEAL_REASON reason=(ENUM_DEAL_REASON)HistoryDealGetInteger(trans.deal,DEAL_REASON);
      string outcome="closed";
      if(reason==DEAL_REASON_SL) outcome="SL_Hit";
      else if(reason==DEAL_REASON_TP) outcome="FinalTP_Hit";
      if(entry==DEAL_ENTRY_INOUT)
        {
         outcome="Ambiguous_NettingReversal";
         g_tracker.MarkHistoryIncomplete(decisionId);
        }
      g_tracker.MarkClosed(decisionId,price,dealTime,net,commission,swap,fee,stillOpen,
                           outcome,trans.deal,volume,true);
      g_execAudit.Log("FILL_OUT",
                      StringFormat("outcome=%s net=%.2f commission=%.2f swap=%.2f fee=%.2f still_open=%s deal=%I64u position_id=%I64u",
                                   outcome,net,commission,swap,fee,stillOpen?"true":"false",trans.deal,positionIdentifier),
                      decisionId,positionTicket,volume,price);
     }
  }
//+------------------------------------------------------------------+
