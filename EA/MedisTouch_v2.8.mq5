#property copyright "Medis Touch"
#property version   "2.81"
#property strict

#include "includes/Core/Config.mqh"
#include "includes/Core/CandleData.mqh"
#include "includes/Core/SessionFilter.mqh" // direct dependency for operator-initiated session gating
#include "includes/Core/SignalLogger.mqh"
#include "includes/Analysis/TFContext.mqh"
#include "includes/Analysis/OrderFlowDiagnostics.mqh"
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
#include "includes/Portfolio/AccountRiskProfilePolicy.mqh"
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
input group "Order-Flow Diagnostics (diagnostic-only; disabled by default; adds I/O when enabled)"
input bool InpEnableOrderFlowDiagnostics=false;
input int InpOrderFlowMinTicks=8;
input double InpOrderFlowPressureThreshold=0.60;
input double InpOrderFlowSmallProgressATR=0.15;
input int InpOrderFlowMaxTickAgeSeconds=30;
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
input group "Account Risk Profile"
input ENUM_ACCOUNT_RISK_PROFILE InpAccountRiskProfile=ACCOUNT_RISK_PROFILE_LEGACY_INPUTS; // default preserves historical EA input behavior

input group "Execution — Legacy Risk Inputs"
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

// These profiles intentionally start at the preserved legacy values. Configure the
// small-account profile from validated small-account evidence, and the prop-firm
// profile from the exact firm's published limits before selecting either one.
input group "Risk Profile — Small Account (independently configurable)"
input double InpSmallRiskPercentPerTrade=0.5;
input int    InpSmallMaxOpenTrades=3;
input double InpSmallMaxDailyLossPercent=3.0;
input double InpSmallMaxDrawdownPercent=10.0;
input double InpSmallDeriskStartPercent=5.0;
input double InpSmallDeriskFloor=0.25;
input double InpSmallMaxPortfolioRiskPercent=3.0;
input int    InpSmallMaxPositionsPerSymbol=3;
input int    InpSmallMaxPositionsPerGroup=3;
input bool   InpSmallAccountProfileConfigured=false; // Set true only after reviewing these limits for the intended small account

input group "Risk Profile — Prop Firm (configure exact firm rules)"
input double InpPropRiskPercentPerTrade=0.5;
input int    InpPropMaxOpenTrades=3;
input double InpPropMaxDailyLossPercent=3.0;
input double InpPropMaxDrawdownPercent=10.0;
input double InpPropDeriskStartPercent=5.0;
input double InpPropDeriskFloor=0.25;
input double InpPropMaxPortfolioRiskPercent=3.0;
input int    InpPropMaxPositionsPerSymbol=3;
input int    InpPropMaxPositionsPerGroup=3;
input bool   InpPropFirmProfileConfigured=false; // Set true only after entering and checking the exact firm's rules above

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
input string InpExecutionLedgerBaseUrl=""; // HTTPS root for the durable broker execution ledger
input bool InpRequireExecutionLedger=true; // Fail closed until broker/database reconciliation succeeds
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
input double InpMinimumQualifiedTradeR=0.25; // Count only fully closed net winners of at least this realized R.
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

COrderFlowDiagnostics g_orderFlowDiagnostics; datetime g_lastOrderFlowBarTime=0; datetime g_lastOrderFlowEventBarEnd=0; string g_lastOrderFlowEventKey=""; CTFContextPool g_pool;CScoringEngine g_scoring;CSessionFilter g_operatorSessionFilter;CTradeDecision g_decision;CRiskEngine g_risk;CSignalLogger g_logger;COutcomeTrackerLive g_tracker;CEnvironmentStrategyMemory g_environmentMemory;CDecisionEngine g_router;CBrokerAdapter g_broker;COrderManager g_orders;CPositionManager g_positions;CRecoveryEngine g_recovery;CPortfolioManager g_portfolio;CMultiTradeEngine g_multiTrade;CRiskGuard g_riskGuard;CNewsFilter g_newsFilter;CSubscriberPlatform g_subscribers;CSignalPublisher g_publisher;CDailyTradeTarget g_dailyTradeTarget;CConfigSync g_configSync;CProductionMonitor g_monitor;CTradeControlPanel g_controlPanel;CExecutionAudit g_execAudit;bool g_emergencyStop=false;datetime g_lastSessionBlockLog=0;CTFContext* g_chartCtx=NULL;CTFContext* g_trendCtx=NULL;CTFContext* g_bosCtx=NULL;CTFContext* g_liqCtx=NULL;CTFContext* g_fvgCtx=NULL;CTFContext* g_htfObCtx=NULL;
AccountRiskLimits g_activeRiskLimits;
CExecutionLedgerClient g_executionLedger; bool g_executionLedgerHealthy=false; datetime g_lastLedgerReconcileAttempt=0; datetime g_lastConfigSyncPoll=0;
datetime g_lastLoggedTime=0,g_lastBarTime=0;long g_lifecycleDecisionId=0;datetime g_lifecycleCreationTime=0;TradeSetup g_lifecycleSetup;string g_lifecycleStatus="valid";bool g_panelInitialized=false;

string EmergencyStopGlobalKey();
bool IsConfiguredSessionAllowed();
bool IsNettingOrExchangeAccount();
bool HasAnyChartSymbolExposure();
void RefreshTradeControlPanel();
bool RiskRFromMoney(double riskMoney,double &riskR);
bool ReconcileBrokerStateSnapshot();
bool SyncHistoricalClosedPositions();
bool SyncHistoricalDealEvents();
bool SendLedgerDealEvent(const ulong dealTicket,const ulong positionIdentifier);
bool IsPositionIdentifierOpen(const ulong positionIdentifier);
bool ParseManagedOrderComment(const string comment,long &decisionId,int &legIndex);
bool PrepareLedgerForSubmit(const TradeDecisionRecord &decision,const int legIndex,const double riskMoney,const double volatility,string &requestId);
void MarkLedgerSubmissionAccepted(const string requestId);
void MarkLedgerSubmissionAmbiguous(const string requestId);
bool UpdateLedgerRiskForPosition(const ulong positionIdentifier,const string direction,const double volatility,const string evidenceRef);
bool IsOrderBuyDirection(const ENUM_ORDER_TYPE orderType);

void ConfigureAccountRiskLimits(AccountRiskLimits &limits,
                                 ENUM_ACCOUNT_RISK_PROFILE profile,
                                 string profileName,double riskPercent,int maxOpenTrades,
                                 double maxDailyLoss,double maxDrawdown,double deriskStart,
                                 double deriskFloor,double portfolioRisk,
                                 int maxPerSymbol,int maxPerGroup)
  {
   limits.profile=profile;
   limits.profileName=profileName;
   limits.riskPercentPerTrade=riskPercent;
   limits.maxOpenTrades=maxOpenTrades;
   limits.maxDailyLossPercent=maxDailyLoss;
   limits.maxDrawdownPercent=maxDrawdown;
   limits.deriskStartPercent=deriskStart;
   limits.deriskFloor=deriskFloor;
   limits.maxPortfolioRiskPercent=portfolioRisk;
   limits.maxPositionsPerSymbol=maxPerSymbol;
   limits.maxPositionsPerGroup=maxPerGroup;
  }

bool RiskRFromMoney(double riskMoney,double &riskR)
  {
   riskR=0.0;
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double baseRiskUnit=equity*g_activeRiskLimits.riskPercentPerTrade/100.0;
   if(equity<=0.0 || baseRiskUnit<=0.0 || riskMoney<=0.0 ||
      !MathIsValidNumber(riskMoney) || !MathIsValidNumber(baseRiskUnit))
      return false;
   riskR=riskMoney/baseRiskUnit;
   return (riskR>0.0 && MathIsValidNumber(riskR));
  }

bool ParseManagedOrderComment(const string comment,long &decisionId,int &legIndex)
  {
   decisionId=0;
   legIndex=0;
   int marker=StringFind(comment,"MT#");
   if(marker<0) return false;
   string tail=StringSubstr(comment,marker+3);
   int legMarker=StringFind(tail,":L");
   string idText=(legMarker>=0)?StringSubstr(tail,0,legMarker):tail;
   decisionId=StringToInteger(idText);
   if(legMarker>=0)
      legIndex=(int)StringToInteger(StringSubstr(tail,legMarker+2));
   return (decisionId>0 && legIndex>=0);
  }

bool IsOrderBuyDirection(const ENUM_ORDER_TYPE orderType)
  {
   return (orderType==ORDER_TYPE_BUY || orderType==ORDER_TYPE_BUY_LIMIT ||
           orderType==ORDER_TYPE_BUY_STOP || orderType==ORDER_TYPE_BUY_STOP_LIMIT);
  }

bool IsPositionIdentifierOpen(const ulong positionIdentifier)
  {
   if(positionIdentifier==0) return false;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if((ulong)PositionGetInteger(POSITION_IDENTIFIER)==positionIdentifier)
         return true;
     }
   return false;
  }

bool PrepareLedgerForSubmit(const TradeDecisionRecord &decision,const int legIndex,
                            const double riskMoney,const double volatility,string &requestId)
  {
   requestId="";
   if(!g_executionLedger.Ready())
      return !InpRequireExecutionLedger;

   double riskR=0.0;
   if(!RiskRFromMoney(riskMoney,riskR))
     {
      g_execAudit.Log("EXECUTION_LEDGER_RISK_INVALID",
                      "risk could not be normalized to the configured base risk unit",
                      decision.decision_id);
      return false;
     }
   string direction=(decision.setup.type==ORDER_TYPE_BUY)?"BUY":"SELL";
   string signalId="MT#"+IntegerToString(decision.decision_id);
   if(!g_executionLedger.Reserve(decision.decision_id,legIndex,signalId,_Symbol,direction,
                                 riskR,MathMax(0.0,volatility),requestId))
     {
      g_execAudit.Log("EXECUTION_LEDGER_RESERVATION_BLOCKED",
                      "bridge did not confirm an idempotent portfolio-risk reservation",
                      decision.decision_id,0,0.0,0.0,0.0,0.0);
      return false;
     }
   // Write-ahead intent: persist SENT before the broker call. If MT5 crashes
   // after this point, recovery treats the outcome as ambiguous rather than
   // releasing the reservation and risking a duplicate order.
   if(!g_executionLedger.Transition(requestId,"CHECKED","{}"))
     {
      g_executionLedgerHealthy=false;
      g_execAudit.Log("EXECUTION_LEDGER_CHECKED_FAILED",
                      "risk reserved but CHECKED transition was not acknowledged; broker call suppressed",
                      decision.decision_id);
      return false;
     }
   if(!g_executionLedger.Transition(requestId,"SENT","{\"ea_send_intent\":true}"))
     {
      g_executionLedgerHealthy=false;
      g_execAudit.Log("EXECUTION_LEDGER_SENT_FAILED",
                      "risk reserved but SENT transition was not acknowledged; broker call suppressed",
                      decision.decision_id);
      return false;
     }
   return true;
  }

void MarkLedgerSubmissionAccepted(const string requestId)
  {
   if(StringLen(requestId)==0 || !g_executionLedger.Ready()) return;
   ulong orderId=g_broker.LastBrokerOrderId();
   ulong dealId=g_broker.LastBrokerDealId();
   ulong positionId=g_broker.LastBrokerPositionId();

   if(orderId>0)
     {
      string ack=StringFormat("{\"broker_acknowledged\":true,\"broker_order_id\":\"%I64u\"",orderId);
      if(dealId>0) ack+=StringFormat(",\"broker_deal_id\":\"%I64u\"",dealId);
      if(positionId>0) ack+=StringFormat(",\"broker_position_id\":\"%I64u\"",positionId);
      ack+="}";
      if(!g_executionLedger.Transition(requestId,"ACKED",ack))
        {
         g_executionLedgerHealthy=false;
         PrintFormat("Midas: broker accepted order #%I64u but ACKED persistence failed; startup reconciliation required.",orderId);
         return;
        }
     }

   if(dealId>0 && positionId>0)
     {
      string fill=StringFormat(
         "{\"broker_confirmed_fill\":true,\"broker_order_id\":\"%I64u\",\"broker_deal_id\":\"%I64u\",\"broker_position_id\":\"%I64u\",\"evidence_ref\":\"mt5-deal:%I64u\"}",
         orderId,dealId,positionId,dealId);
      if(!g_executionLedger.Transition(requestId,"FILLED",fill))
        {
         g_executionLedgerHealthy=false;
         PrintFormat("Midas: broker fill #%I64u could not be durably marked; risk reservation must remain in recovery.",dealId);
        }
     }
   else if(orderId==0)
     {
      MarkLedgerSubmissionAmbiguous(requestId);
     }
  }

void MarkLedgerSubmissionAmbiguous(const string requestId)
  {
   if(StringLen(requestId)==0 || !g_executionLedger.Ready()) return;
   if(!g_executionLedger.Transition(requestId,"RECOVERING",
                                    "{\"submission_result\":\"ambiguous\",\"evidence_ref\":\"ea-submit-result\"}"))
     {
      g_executionLedgerHealthy=false;
      Print("Midas: submission result could not be reconciled with the bridge; new entries are blocked until recovery.");
     }
  }

bool UpdateLedgerRiskForPosition(const ulong positionIdentifier,const string direction,
                                 const double volatility,const string evidenceRef)
  {
   if(!g_executionLedger.Ready()) return !InpRequireExecutionLedger;
   ulong ticket=g_broker.PositionTicketForIdentifier(_Symbol,positionIdentifier);
   if(ticket==0 || !PositionSelectByTicket(ticket)) return false;
   double sl=PositionGetDouble(POSITION_SL);
   double entry=PositionGetDouble(POSITION_PRICE_OPEN);
   double volume=PositionGetDouble(POSITION_VOLUME);
   if(sl<=0.0 || entry<=0.0 || volume<=0.0) return false;
   double riskMoney=g_risk.RiskAmountForLots(_Symbol,volume,entry,sl);
   double riskR=0.0;
   if(!RiskRFromMoney(riskMoney,riskR)) return false;
   return g_executionLedger.UpdatePositionRisk(positionIdentifier,direction,riskR,
                                                MathMax(0.0,volatility),evidenceRef);
  }

bool ReconcileBrokerStateSnapshot()
  {
   g_lastLedgerReconcileAttempt=TimeCurrent();
   if(!g_executionLedger.Ready()) return false;
   bool allOk=true;
   if(!g_executionLedger.RecoverExpired())
     {
      g_execAudit.Log("LEDGER_RECOVERY_API_FAILED","could not request expired execution lease recovery");
      allOk=false;
     }

   double baseRiskUnit=AccountInfoDouble(ACCOUNT_EQUITY)*g_activeRiskLimits.riskPercentPerTrade/100.0;
   if(baseRiskUnit<=0.0)
     {
      g_execAudit.Log("LEDGER_STARTUP_BLOCKED","base risk unit is non-positive; existing exposure cannot be normalized");
      return false;
     }

   // Import every live position for this strategy magic, across symbols.
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=InpMagicNumber) continue;

      string symbol=PositionGetString(POSITION_SYMBOL);
      ulong positionId=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      double volume=PositionGetDouble(POSITION_VOLUME);
      double entry=PositionGetDouble(POSITION_PRICE_OPEN);
      double sl=PositionGetDouble(POSITION_SL);
      if(positionId==0 || sl<=0.0 || entry<=0.0 || volume<=0.0)
        {
         g_execAudit.Log("LEDGER_POSITION_RISK_UNKNOWN",
                         "startup reconciliation found an EA position without computable stop risk",
                         0,ticket,volume,entry,sl,0.0);
         allOk=false;
         continue;
        }
      double riskMoney=g_risk.RiskAmountForLots(symbol,volume,entry,sl);
      double riskR=0.0;
      if(!RiskRFromMoney(riskMoney,riskR))
        {
         allOk=false;
         continue;
        }

      ulong openingOrder=0;
      ulong openingDeal=0;
      long commentDecisionId=0;
      int commentLegIndex=0;
      string requestIdOverride="";
      if(HistorySelectByPosition(positionId))
        {
         for(int d=0;d<HistoryDealsTotal();d++)
           {
            ulong deal=HistoryDealGetTicket(d);
            if(deal==0) continue;
            if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY)!=DEAL_ENTRY_IN) continue;
            if((ulong)HistoryDealGetInteger(deal,DEAL_MAGIC)!=InpMagicNumber) continue;
            openingOrder=(ulong)HistoryDealGetInteger(deal,DEAL_ORDER);
            openingDeal=deal;
            break;
           }
        }
      if(openingOrder>0 && HistoryOrderSelect(openingOrder))
        {
         string comment=HistoryOrderGetString(openingOrder,ORDER_COMMENT);
         if(ParseManagedOrderComment(comment,commentDecisionId,commentLegIndex))
            requestIdOverride=g_executionLedger.RequestIdForDecision(commentDecisionId,commentLegIndex);
        }

      string direction=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY)?"BUY":"SELL";
      string evidence=StringFormat("mt5-oninit-position:%I64u:%I64u",positionId,TimeCurrent());
      if(!g_executionLedger.SyncPosition(positionId,openingOrder,openingDeal,symbol,direction,
                                         riskR,0.0,evidence,requestIdOverride))
        {
         g_execAudit.Log("LEDGER_POSITION_SYNC_FAILED",
                         "live broker position could not be imported into the persistent portfolio risk book",
                         commentDecisionId,ticket,volume,entry,sl,0.0);
         allOk=false;
        }
     }

   // Import live pending orders too: their risk remains reserved even if no
   // position has filled yet. Unknown SL risk fails closed rather than guessed.
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong orderTicket=OrderGetTicket(i);
      if(orderTicket==0 || !OrderSelect(orderTicket)) continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC)!=InpMagicNumber) continue;
      ENUM_ORDER_TYPE orderType=(ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if(orderType!=ORDER_TYPE_BUY_LIMIT && orderType!=ORDER_TYPE_SELL_LIMIT &&
         orderType!=ORDER_TYPE_BUY_STOP && orderType!=ORDER_TYPE_SELL_STOP &&
         orderType!=ORDER_TYPE_BUY_STOP_LIMIT && orderType!=ORDER_TYPE_SELL_STOP_LIMIT)
         continue;

      string symbol=OrderGetString(ORDER_SYMBOL);
      double volume=OrderGetDouble(ORDER_VOLUME_CURRENT);
      if(volume<=0.0) volume=OrderGetDouble(ORDER_VOLUME_INITIAL);
      double entry=OrderGetDouble(ORDER_PRICE_OPEN);
      double sl=OrderGetDouble(ORDER_SL);
      if(sl<=0.0 || entry<=0.0 || volume<=0.0)
        {
         g_execAudit.Log("LEDGER_PENDING_RISK_UNKNOWN",
                         "startup found a pending EA order without computable stop risk",
                         0,orderTicket,volume,entry,sl,0.0);
         allOk=false;
         continue;
        }
      double riskMoney=g_risk.RiskAmountForLots(symbol,volume,entry,sl);
      double riskR=0.0;
      if(!RiskRFromMoney(riskMoney,riskR))
        {
         allOk=false;
         continue;
        }
      long decisionId=0;
      int legIndex=0;
      string requestIdOverride="";
      if(ParseManagedOrderComment(OrderGetString(ORDER_COMMENT),decisionId,legIndex))
         requestIdOverride=g_executionLedger.RequestIdForDecision(decisionId,legIndex);
      string direction=IsOrderBuyDirection(orderType)?"BUY":"SELL";
      string evidence=StringFormat("mt5-oninit-order:%I64u:%I64u",orderTicket,TimeCurrent());
      if(!g_executionLedger.SyncPendingOrder(orderTicket,symbol,direction,riskR,0.0,evidence,requestIdOverride))
        {
         g_execAudit.Log("LEDGER_ORDER_SYNC_FAILED",
                         "live broker pending order could not be imported into portfolio risk book",
                         decisionId,orderTicket,volume,entry,sl,0.0);
         allOk=false;
        }
     }

   // Replay broker deal history before declaring the ledger healthy. This repairs
   // missed callbacks after terminal restarts and is idempotent by broker deal ID.
   if(!SyncHistoricalDealEvents())
      allOk=false;
   if(!SyncHistoricalClosedPositions())
      allOk=false;
   return allOk;
  }

bool SyncHistoricalDealEvents()
  {
   if(!g_executionLedger.Ready()) return !InpRequireExecutionLedger;
   if(!HistorySelect(0,TimeCurrent())) return false;
   ulong deals[];
   int total=HistoryDealsTotal();
   ArrayResize(deals,total);
   for(int i=0;i<total;i++) deals[i]=HistoryDealGetTicket(i);

   bool allOk=true;
   for(int i=0;i<ArraySize(deals);i++)
     {
      ulong deal=deals[i];
      if(deal==0 || !HistoryDealSelect(deal)) { allOk=false; continue; }
      if((ulong)HistoryDealGetInteger(deal,DEAL_MAGIC)!=InpMagicNumber) continue;
      ENUM_DEAL_TYPE type=(ENUM_DEAL_TYPE)HistoryDealGetInteger(deal,DEAL_TYPE);
      if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
      ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY);
      if(entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_OUT &&
         entry!=DEAL_ENTRY_OUT_BY && entry!=DEAL_ENTRY_INOUT) continue;
      ulong positionId=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
      if(positionId==0) { allOk=false; continue; }
      if(!SendLedgerDealEvent(deal,positionId))
        {
         g_execAudit.Log("LEDGER_HISTORY_DEAL_REPLAY_FAILED",
                         "historical broker deal could not be durably replayed",
                         0,positionId,HistoryDealGetDouble(deal,DEAL_VOLUME),
                         HistoryDealGetDouble(deal,DEAL_PRICE));
         allOk=false;
        }
     }
   return allOk;
  }

bool SyncHistoricalClosedPositions()
  {
   if(!g_executionLedger.Ready()) return !InpRequireExecutionLedger;
   // A netting reversal can reuse the same position identity for a new side;
   // never infer terminal closure from volume arithmetic in that mode.
   if(IsNettingOrExchangeAccount()) return true;
   if(!HistorySelect(0,TimeCurrent())) return false;

   ulong candidateIds[];
   for(int i=0;i<HistoryDealsTotal();i++)
     {
      ulong deal=HistoryDealGetTicket(i);
      if(deal==0) continue;
      ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY);
      if(entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY) continue;
      ulong positionId=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
      if(positionId==0 || IsPositionIdentifierOpen(positionId)) continue;
      bool known=false;
      for(int j=0;j<ArraySize(candidateIds);j++)
         if(candidateIds[j]==positionId) { known=true; break; }
      if(!known)
        {
         int size=ArraySize(candidateIds);
         ArrayResize(candidateIds,size+1);
         candidateIds[size]=positionId;
        }
     }

   bool allOk=true;
   for(int p=0;p<ArraySize(candidateIds);p++)
     {
      ulong positionId=candidateIds[p];
      if(IsPositionIdentifierOpen(positionId) || !HistorySelectByPosition(positionId)) continue;
      double openedVolume=0.0;
      double closedVolume=0.0;
      bool hasManagedEntry=false;
      bool foreignEntry=false;
      bool ambiguous=false;
      ulong lastCloseDeal=0;
      ulong openingOrder=0;
      long decisionId=0;
      int legIndex=0;

      for(int d=0;d<HistoryDealsTotal();d++)
        {
         ulong deal=HistoryDealGetTicket(d);
         if(deal==0) continue;
         if((ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID)!=positionId) continue;
         ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY);
         double volume=HistoryDealGetDouble(deal,DEAL_VOLUME);
         ulong dealMagic=(ulong)HistoryDealGetInteger(deal,DEAL_MAGIC);
         if(entry==DEAL_ENTRY_IN)
           {
            if(dealMagic==InpMagicNumber)
              {
               hasManagedEntry=true;
               openedVolume+=volume;
               if(openingOrder==0)
                  openingOrder=(ulong)HistoryDealGetInteger(deal,DEAL_ORDER);
              }
            else foreignEntry=true;
           }
         else if(entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY)
           {
            closedVolume+=volume;
            lastCloseDeal=deal;
           }
         else if(entry==DEAL_ENTRY_INOUT) ambiguous=true;
        }

      double tolerance=MathMax(1e-6,openedVolume*1e-5);
      if(!hasManagedEntry || foreignEntry || ambiguous || lastCloseDeal==0 ||
         openedVolume<=0.0 || closedVolume+tolerance<openedVolume)
         continue;

      string requestIdOverride="";
      if(openingOrder>0 && HistoryOrderSelect(openingOrder))
        {
         string comment=HistoryOrderGetString(openingOrder,ORDER_COMMENT);
         if(ParseManagedOrderComment(comment,decisionId,legIndex))
            requestIdOverride=g_executionLedger.RequestIdForDecision(decisionId,legIndex);
        }
      string evidence=StringFormat("mt5-oninit-closed-history:%I64u:%I64u",positionId,lastCloseDeal);
      if(!g_executionLedger.SyncClosedPosition(positionId,lastCloseDeal,evidence,requestIdOverride))
        {
         g_execAudit.Log("LEDGER_CLOSED_HISTORY_SYNC_FAILED",
                         "closed position history could not be replayed into persistent execution state",
                         decisionId,positionId,0.0,0.0,0.0,0.0);
         allOk=false;
        }
     }
   return allOk;
  }


bool ResolveSelectedAccountRiskProfile()
  {
   AccountRiskLimits legacy,smallAccount,propFirm;
   ConfigureAccountRiskLimits(legacy,ACCOUNT_RISK_PROFILE_LEGACY_INPUTS,"legacy_inputs",
      InpRiskPercentPerTrade,InpMaxOpenTrades,InpMaxDailyLossPercent,InpMaxDrawdownPercent,
      InpDeriskStartPercent,InpDeriskFloor,InpMaxPortfolioRiskPercent,
      InpMaxPositionsPerSymbol,InpMaxPositionsPerGroup);
   ConfigureAccountRiskLimits(smallAccount,ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT,"small_account",
      InpSmallRiskPercentPerTrade,InpSmallMaxOpenTrades,InpSmallMaxDailyLossPercent,
      InpSmallMaxDrawdownPercent,InpSmallDeriskStartPercent,InpSmallDeriskFloor,
      InpSmallMaxPortfolioRiskPercent,InpSmallMaxPositionsPerSymbol,InpSmallMaxPositionsPerGroup);
   ConfigureAccountRiskLimits(propFirm,ACCOUNT_RISK_PROFILE_PROP_FIRM,"prop_firm",
      InpPropRiskPercentPerTrade,InpPropMaxOpenTrades,InpPropMaxDailyLossPercent,
      InpPropMaxDrawdownPercent,InpPropDeriskStartPercent,InpPropDeriskFloor,
      InpPropMaxPortfolioRiskPercent,InpPropMaxPositionsPerSymbol,InpPropMaxPositionsPerGroup);

   string reason="";
   if(!ResolveConfiguredAccountRiskLimits(InpAccountRiskProfile,legacy,smallAccount,propFirm,
                                            InpSmallAccountProfileConfigured,InpPropFirmProfileConfigured,
                                            g_activeRiskLimits,reason))
     {
      PrintFormat("MedisTouch: invalid account risk profile (%s): %s",
                  EnumToString(InpAccountRiskProfile),reason);
      return false;
     }
   PrintFormat("MedisTouch: active risk profile=%s risk/trade=%.3f%% max-open=%d daily-cap=%.2f%% hard-DD=%.2f%% portfolio-open-risk=%.2f%% per-symbol=%d per-group=%d",
               g_activeRiskLimits.profileName,g_activeRiskLimits.riskPercentPerTrade,
               g_activeRiskLimits.maxOpenTrades,g_activeRiskLimits.maxDailyLossPercent,
               g_activeRiskLimits.maxDrawdownPercent,g_activeRiskLimits.maxPortfolioRiskPercent,
               g_activeRiskLimits.maxPositionsPerSymbol,g_activeRiskLimits.maxPositionsPerGroup);
   return true;
  }

int OnInit()
  {
   if(!ResolveSelectedAccountRiskProfile()) return INIT_PARAMETERS_INCORRECT;
   if(StringLen(InpExecutionLedgerBaseUrl)>0 && StringLen(InpBridgeApiKey)>0)
      g_executionLedger.Init(InpExecutionLedgerBaseUrl,InpBridgeApiKey,InpMagicNumber,InpWebRequestTimeoutMs);
   else
      Print("Midas execution ledger: configure InpExecutionLedgerBaseUrl and InpBridgeApiKey before enabling ledger-enforced entries.");
   g_executionLedgerHealthy=(!InpEnableExecution || !InpRequireExecutionLedger);
   g_pool.Configure(_Symbol,InpMaxHistoryBars,InpSwingStrength,InpFVGMinSizeATR,InpInternalLiqThresholdATR,InpRVOLLookback,InpVALookbackBars,InpVANumBins,InpVAPercent/100.0,InpOBDisplacementATRMult,InpOBMinBodyRatio);g_chartCtx=g_pool.Get(_Period);g_trendCtx=g_pool.Get(InpTrendTF);g_bosCtx=g_pool.Get(InpBOSTF);g_liqCtx=g_pool.Get(InpLiquidityTF);g_fvgCtx=g_pool.Get(InpFVGTF);g_htfObCtx=g_pool.Get(InpHtfObTF);if(g_chartCtx==NULL||g_trendCtx==NULL||g_bosCtx==NULL||g_liqCtx==NULL||g_fvgCtx==NULL||g_htfObCtx==NULL)return INIT_FAILED;
   g_scoring.Init(g_trendCtx,g_bosCtx,g_liqCtx,g_fvgCtx,g_chartCtx,&g_chartCtx.candles);g_scoring.ConfigureInducement(InpImpulseLookbackBars,InpImpulseATRMult,InpImpulseBodyRatio,InpEqualTolATR,InpMaxLegExtend,InpRequirePremiumDiscount,InpRequireDistributionPhase,InpPhaseRangeLookback,InpPhaseCompressionATRMult);g_scoring.ConfigureVolumeFibonacci(InpRequireVolumeConfirmation,InpRVOLThreshold,InpRequireFibonacciZone,InpFibZoneMinPct,InpFibZoneMaxPct);g_scoring.ConfigureValueArea(InpRequireValueAreaLocation,InpBlockValueAreaContradictions);g_scoring.ConfigureHtfOrderBlock(g_htfObCtx,InpRequireHtfOB,InpOBDistATRMax);g_scoring.ConfigureVolatilityRegime(InpBlockLowVolRegime,InpVolRegimeLookback,InpVolRegimeLowPct,InpVolRegimeHighPct);g_scoring.ConfigureSessionFilter(InpUseSessionFilter,InpAllowTokyoSession,InpAllowLondonSession,InpAllowNewYorkSession,InpAllowLondonNYOverlap);g_operatorSessionFilter.Configure(InpUseSessionFilter,InpAllowTokyoSession,InpAllowLondonSession,InpAllowNewYorkSession,InpAllowLondonNYOverlap);g_scoring.ConfigureSweepQuality(InpRequireMinSweepGrade,(ENUM_SWEEP_GRADE)InpMinSweepGrade,InpRequireFreshSetup,InpMaxBarsSinceBOS);g_scoring.ConfigureChaseFilter(InpRequireChaseFilter,InpMaxChaseDistATR);g_scoring.ConfigureFVGProximity(InpFVGMaxDistATR);g_scoring.ConfigureLearnedDiagnostics(InpDiagContradictionWeight,InpDiagEnvWeight,InpDiagExecWeight);g_scoring.ConfigureStrategyDiagnostics(InpMomentumBreakoutRecencyBars,InpBreakoutLiqOverlapBars,InpBreakoutExtensionLookbackBars,InpBreakoutExhaustionATRMult,InpMomentumLookbackBars);g_scoring.ConfigureMeanReversionDiagnostics(InpReversionMinStretchATR,InpReversionSRZoneATRTolerance,InpReversionWickRejectionRatio,InpReversionLiqRecencyBars,InpReversionTrendConflictRecencyBars,InpReversionTrendConflictMinStrength);g_scoring.ConfigureKeyLevelDiagnostics(InpKeyLevelLookbackBars,InpKeyLevelSearchATRMax,InpKeyLevelTouchToleranceATRMult,InpKeyLevelAbsorptionMinTouches,InpKeyLevelWickRejectionRatio,InpKeyLevelRoundStep);g_scoring.ConfigureStrategySelection(InpMinSelectionScore);
   g_environmentMemory.Init(_Symbol,InpEnvironmentMemoryMinSample,InpEnvironmentMemoryBonus,InpEnvironmentMemoryPenalty);g_decision.Init(&g_chartCtx.candles,g_fvgCtx,g_liqCtx,&g_scoring,InpSLBufferATR,InpMinStopSpreadMult,InpFVGMaxDistATR,InpMinSelectionScore,g_chartCtx,g_bosCtx,GetPointer(g_environmentMemory));g_logger.Init(_Symbol,InpSessionGMTOffsetOverride);g_tracker.Init(&g_logger,_Symbol,_Period,InpMaxTrackingBars,InpFillPolicy,InpReplayTF);g_tracker.ConfigureEnvironmentMemory(GetPointer(g_environmentMemory));g_tracker.ConfigureSimulation(g_activeRiskLimits.riskPercentPerTrade,InpAllowMinLotOverride,InpBreakEvenAtR,InpPartialAtR,InpPartialFraction,InpTrailATRMult,InpSimCommissionPerLot,InpSimSpreadPoints,InpSimSlippagePoints);g_tracker.ConfigureCalibration(InpTrackOutcomes,InpCalibrationMinSample);g_tracker.ConfigureConfidenceDecay(InpDiagDecayHalfLifeBars);g_router.Init(_Symbol,InpEnableExecution,InpEnableSignals,InpMinConfidenceExecute,InpMinConfidenceSignal,InpFullRiskConfidence,InpMaxSpreadPoints);g_multiTrade.Init(InpEnableMultiTrade,InpMultiTradeDualProbability,InpMultiTradeTripleProbability,InpMultiTradeMinRawConfidence,InpMultiTradeMinCalibrationSample,InpMultiTradeDualLeg0RiskFraction,InpMultiTradeDualLeg1RiskFraction,InpMultiTradeTripleLeg0RiskFraction,InpMultiTradeTripleLeg1RiskFraction,InpMultiTradeTripleLeg2RiskFraction,InpRequireHedgingForMultiTrade);g_broker.Init(InpMagicNumber);g_monitor.Init(_Symbol,InpHeartbeatIntervalSec,InpMaxDrawdownAlertPercent);g_orders.Init(&g_broker,g_activeRiskLimits.maxOpenTrades,&g_monitor);g_positions.Init(&g_orders,&g_broker,InpBreakEvenAtR,InpPartialAtR,InpPartialFraction,InpTrailATRMult,0,0.0,0.0,5,&g_chartCtx.swings);g_store.Init(_Symbol);g_execAudit.Init(_Symbol,InpMagicNumber);g_emergencyStop=(GlobalVariableCheck(EmergencyStopGlobalKey()) && GlobalVariableGet(EmergencyStopGlobalKey())>0.5);if(InpShowTradeControlPanel || g_emergencyStop){g_panelInitialized=g_controlPanel.Init(ChartID(),_Symbol,InpMagicNumber);if(!g_panelInitialized)Print("MedisTouch: trade control panel could not create every chart object.");}g_execAudit.Log("INIT",StringFormat("version=2.81 magic=%I64u risk_profile=%s risk_per_trade=%.3f max_open=%d emergency_latched=%s account_margin_mode=%d",InpMagicNumber,g_activeRiskLimits.profileName,g_activeRiskLimits.riskPercentPerTrade,g_activeRiskLimits.maxOpenTrades,g_emergencyStop?"true":"false",(int)AccountInfoInteger(ACCOUNT_MARGIN_MODE)));if((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING){g_execAudit.Log("ACCOUNT_MODE_WARNING","MT5 netting/exchange mode aggregates same-symbol exposure; isolate manual/other-EA activity before using close-all");Print("MedisTouch: WARNING — netting/exchange account may aggregate this symbol with other trade sources.");}bool qualifiedTradeTrackingSupported=InpTrackOutcomes && InpEnableExecution && ((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);g_dailyTradeTarget.Init(qualifiedTradeTrackingSupported?InpMinimumQualifiedTradesPerDay:0,InpMinimumQualifiedTradeR,InpMagicNumber);if(InpMinimumQualifiedTradesPerDay>0 && !qualifiedTradeTrackingSupported)Print("Midas Touch: weekday qualified-trade counter disabled; requires outcome tracking, execution, and a retail-hedging account.");g_subscribers.Init();g_publisher.Init(_Symbol,&g_subscribers,InpWebRequestTimeoutMs,InpBridgeApiKey);g_publisher.SetWeightVersion(InpWeightSetVersion);
   if(StringLen(InpConfigSyncEndpoint)>0){g_configSync.Init(_Symbol,InpConfigSyncEndpoint,InpBridgeApiKey,InpWeightSetVersion,InpWebRequestTimeoutMs);EventSetTimer(MathMax(60,InpConfigSyncPollMinutes*60));}g_tracker.ConfigurePublishing(&g_publisher,InpWeightSetVersion);g_portfolio.Init(g_activeRiskLimits.maxPortfolioRiskPercent,g_activeRiskLimits.maxPositionsPerSymbol,g_activeRiskLimits.maxPositionsPerGroup,InpMagicNumber,&g_risk);g_riskGuard.Init(_Symbol,g_activeRiskLimits.maxDailyLossPercent,g_activeRiskLimits.maxDrawdownPercent,g_activeRiskLimits.deriskStartPercent,g_activeRiskLimits.deriskFloor);if(InpUseNewsFilter)g_newsFilter.Load(InpNewsFilterFile,InpNewsMinutesBefore,InpNewsMinutesAfter);g_scoring.ConfigureNewsAwareness(GetPointer(g_newsFilter),InpNewsWarnMinutesBefore,InpNewsWarnMinutesAfter,InpNewsWarnMultiplier);g_recovery.Init(&g_store,&g_orders,InpMagicNumber,_Symbol);int restored=g_recovery.Recover();if(restored>0)PrintFormat("MedisTouch EA: recovery restored %d live trade(s).",restored);TradeDecisionRecord prior[];int n=g_store.LoadAll(prior);long maxId=0;for(int i=0;i<n;i++)if(prior[i].decision_id>maxId)maxId=prior[i].decision_id;if(maxId>0)g_router.SeedNextId(maxId+1);
   if(InpEnableExecution && g_executionLedger.Ready())
     {
      g_executionLedgerHealthy=ReconcileBrokerStateSnapshot();
      if(!g_executionLedgerHealthy)
         g_execAudit.Log("EXECUTION_LEDGER_NOT_READY","broker/database startup reconciliation incomplete; existing positions remain managed, but new EA entries are blocked");
      else
         g_execAudit.Log("EXECUTION_LEDGER_READY","startup positions, pending orders and complete closed-history evidence reconciled");
     }
   else if(InpEnableExecution && InpRequireExecutionLedger)
     {
      g_executionLedgerHealthy=false;
      g_execAudit.Log("EXECUTION_LEDGER_CONFIGURATION_MISSING","new automated and manual entries remain blocked until bridge URL and API key are configured");
     }
   else g_executionLedgerHealthy=true;
   if(StringLen(InpConfigSyncEndpoint)>0 || (InpEnableExecution && InpRequireExecutionLedger))
      EventSetTimer(MathMax(10,InpExecutionLedgerRetrySeconds));
   return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason){EventKillTimer();if(StringLen(InpConfigSyncEndpoint)>0)EventKillTimer();g_execAudit.Log("DEINIT",StringFormat("reason=%d",reason));if(g_panelInitialized)g_controlPanel.Destroy();g_publisher.Deinit();g_subscribers.Deinit();g_store.Deinit();}
void OnTimer()
  {
   datetime now=TimeCurrent();
   if(InpEnableExecution && InpRequireExecutionLedger && !g_executionLedgerHealthy &&
      now-g_lastLedgerReconcileAttempt>=MathMax(10,InpExecutionLedgerRetrySeconds))
     {
      g_executionLedgerHealthy=ReconcileBrokerStateSnapshot();
      if(g_executionLedgerHealthy)
         g_execAudit.Log("EXECUTION_LEDGER_RECOVERED","broker snapshot and restart history reconciliation succeeded; new entries re-enabled");
     }
   if(StringLen(InpConfigSyncEndpoint)>0 &&
      now-g_lastConfigSyncPoll>=MathMax(60,InpConfigSyncPollMinutes*60))
     {
      g_configSync.Poll();
      g_lastConfigSyncPoll=now;
     }
  }
void CheckSignalLifecycle(double atr){if(g_lifecycleDecisionId==0)return;bool filled;double fillPrice;datetime fillTime;int barsToFill;if(!g_tracker.GetFillState(g_lifecycleCreationTime,g_lifecycleDecisionId,filled,fillPrice,fillTime,barsToFill)){g_lifecycleDecisionId=0;return;}if(filled){g_lifecycleDecisionId=0;return;}bool buy=g_lifecycleSetup.type==ORDER_TYPE_BUY;int barsSince=iBarShift(_Symbol,_Period,g_lifecycleCreationTime,false);if(barsSince>=InpSignalExpiryBars){if(g_lifecycleStatus!="expired"){g_publisher.PublishStatusUpdate(g_lifecycleDecisionId,"expired",StringFormat("Unfilled for %d execution bars",barsSince));g_lifecycleStatus="expired";}g_lifecycleDecisionId=0;return;}double opposite=g_scoring.CalculateConfidence(!buy);if(opposite>=InpInvalidateOpposingConfidence){if(g_lifecycleStatus!="invalidated"){g_publisher.PublishStatusUpdate(g_lifecycleDecisionId,"invalidated",StringFormat("Opposing confidence %.0f",opposite));g_lifecycleStatus="invalidated";}g_lifecycleDecisionId=0;return;}if(atr>0){double entry=ResolveExecutionEntry(g_lifecycleSetup);double price=buy?SymbolInfoDouble(_Symbol,SYMBOL_ASK):SymbolInfoDouble(_Symbol,SYMBOL_BID);double drift=MathAbs(price-entry)/atr;bool wrong=buy?(price>entry):(price<entry);if(wrong&&drift>=InpSignalStaleChaseATR){if(g_lifecycleStatus!="stale"){g_publisher.PublishStatusUpdate(g_lifecycleDecisionId,"stale",StringFormat("Price drifted %.2f ATR past entry",drift));g_lifecycleStatus="stale";}}else if(g_lifecycleStatus=="stale"&&drift<InpSignalStaleChaseATR*0.5){g_publisher.PublishStatusUpdate(g_lifecycleDecisionId,"valid","Price returned toward entry");g_lifecycleStatus="valid";}}}
bool AppendOrderFlowEvidence(datetime barStart,datetime barEnd,
                           double priorHigh,double priorLow,
                           double barHigh,double barLow,double barClose,double atr,
                           string diagnosticStatus,OrderFlowSnapshot &of)
  {
   string filename="MedisTouch_OrderFlowEvidence_v3_"+_Symbol+"_"+EnumToString(InpFVGTF)+".csv";
   int flags=FILE_CSV|FILE_READ|FILE_WRITE|FILE_SHARE_READ|FILE_ANSI;
   ResetLastError();
   int handle=FileOpen(filename,flags,',');
   if(handle==INVALID_HANDLE)
     {
      PrintFormat("OF_DIAG evidence file open failed: %s error=%d",filename,GetLastError());
      return false;
     }

   bool headerOK=true;
   if(FileSize(handle)==0)
     {
      uint headerBytes=FileWrite(handle,"schema_version","event_key","symbol","timeframe",
                                 "bar_start_epoch","bar_end_epoch","prior_high","prior_low",
                                 "bar_high","bar_low","bar_close","atr","tick_count","data_quality",
                                 "pressure_ratio","signed_tick_pressure","positive_tick_count",
                                 "negative_tick_count","price_progress","bullish_sweep_reclaim",
                                 "bearish_sweep_reclaim","absorption_proxy","exhaustion_proxy",
                                 "data_stale","first_tick_time_msc","last_tick_time_msc",
                                 "pressure_progress_divergence","continuation_hypothesis","reversal_hypothesis",
                                 "auction_context_available","value_area_poc","value_area_vah","value_area_val",
                                 "value_area_source_quality","value_area_source","auction_location","diagnostic_status");
      headerOK=(headerBytes>0);
     }

   FileSeek(handle,0,SEEK_END);
   string eventKey=_Symbol+"|"+EnumToString(InpFVGTF)+"|"+IntegerToString((long)barStart);
   uint rowBytes=FileWrite(handle,"order-flow-evidence-v3",eventKey,_Symbol,EnumToString(InpFVGTF),
                           IntegerToString((long)barStart),IntegerToString((long)barEnd),
                           DoubleToString(priorHigh,_Digits),DoubleToString(priorLow,_Digits),
                           DoubleToString(barHigh,_Digits),DoubleToString(barLow,_Digits),
                           DoubleToString(barClose,_Digits),DoubleToString(atr,_Digits),
                           IntegerToString(of.tick_count),IntegerToString((int)of.quality),
                           DoubleToString(of.pressure_ratio,6),DoubleToString(of.signed_tick_pressure,0),
                           IntegerToString(of.positive_tick_count),IntegerToString(of.negative_tick_count),
                           DoubleToString(of.price_progress,_Digits),
                           of.bullish_sweep_reclaim?"true":"false",
                           of.bearish_sweep_reclaim?"true":"false",
                           of.absorption_proxy?"true":"false",
                           of.exhaustion_proxy?"true":"false",
                           of.data_stale?"true":"false",
                           IntegerToString(of.first_tick_time_msc),IntegerToString(of.last_tick_time_msc),
                           of.pressure_progress_divergence?"true":"false",
                           IntegerToString(of.continuation_hypothesis),IntegerToString(of.reversal_hypothesis),
                           of.auction_context_available?"true":"false",
                           DoubleToString(of.value_area_poc,_Digits),DoubleToString(of.value_area_vah,_Digits),
                           DoubleToString(of.value_area_val,_Digits),DoubleToString(of.value_area_source_quality,4),
                           IntegerToString(of.value_area_source),IntegerToString(of.auction_location),diagnosticStatus);
   FileFlush(handle);
   bool ok=(headerOK && rowBytes>0 && GetLastError()==0);
   FileClose(handle);
   g_lastOrderFlowEventKey=(ok && diagnosticStatus=="OK_PROXY" ? eventKey : "");
   g_lastOrderFlowEventBarEnd=(StringLen(g_lastOrderFlowEventKey)>0 ? barEnd : 0);
   return ok;
  }

void AttachOrderFlowAuctionContext(double barClose,OrderFlowSnapshot &of)
  {
   if(g_fvgCtx==NULL)
      return;
   g_orderFlowDiagnostics.AttachAuctionContext(g_fvgCtx.valueArea.POC(),
                                                g_fvgCtx.valueArea.VAH(),
                                                g_fvgCtx.valueArea.VAL(),
                                                g_fvgCtx.valueArea.SourceQuality(),
                                                (int)g_fvgCtx.valueArea.Source(),
                                                barClose,of);
  }

void LogOrderFlowDiagnostics()
  {
   if(!InpEnableOrderFlowDiagnostics || g_fvgCtx==NULL)
      return;
   datetime diagnosticBarTime=iTime(_Symbol,InpFVGTF,0);
   if(diagnosticBarTime<=0 || diagnosticBarTime==g_lastOrderFlowBarTime)
      return;
   g_lastOrderFlowEventKey="";
   datetime barStart=iTime(_Symbol,InpFVGTF,1);
   datetime barEnd=diagnosticBarTime;
   if(barStart<=0 || barEnd<=barStart)
      return;
   // Mark this timeframe's bar boundary immediately: even missing history
   // must be logged at most once for this closed-bar window.
   g_lastOrderFlowBarTime=diagnosticBarTime;

   g_orderFlowDiagnostics.Configure(InpOrderFlowMinTicks,
                                    InpOrderFlowPressureThreshold,
                                    InpOrderFlowSmallProgressATR,
                                    InpOrderFlowMaxTickAgeSeconds);
   OrderFlowSnapshot of;
   MqlTick emptyTicks[];

   int hiShift=iHighest(_Symbol,InpFVGTF,MODE_HIGH,20,2);
   int loShift=iLowest(_Symbol,InpFVGTF,MODE_LOW,20,2);
   if(hiShift<0 || loShift<0)
     {
      g_orderFlowDiagnostics.Analyze(emptyTicks,0,0.0,0.0,0.0,0.0,0.0,0.0,of);
      AppendOrderFlowEvidence(barStart,barEnd,0.0,0.0,0.0,0.0,0.0,0.0,
                              "BAR_HISTORY_UNAVAILABLE",of);
      Print("OF_DIAG unavailable: bar history/levels missing");
      return;
     }

   double priorHigh=iHigh(_Symbol,InpFVGTF,hiShift);
   double priorLow=iLow(_Symbol,InpFVGTF,loShift);
   double barHigh=iHigh(_Symbol,InpFVGTF,1);
   double barLow=iLow(_Symbol,InpFVGTF,1);
   double barClose=iClose(_Symbol,InpFVGTF,1);
   double atr=g_fvgCtx.candles.GetATR(1);
   if(atr<=0.0 || priorHigh<=priorLow || barHigh<=0.0 || barLow<=0.0 || barClose<=0.0)
     {
      g_orderFlowDiagnostics.Analyze(emptyTicks,0,priorHigh,priorLow,
                                     barHigh,barLow,barClose,atr,of);
      AppendOrderFlowEvidence(barStart,barEnd,priorHigh,priorLow,
                              barHigh,barLow,barClose,atr,"BAR_CONTEXT_UNAVAILABLE",of);
      PrintFormat("OF_DIAG unavailable: ATR/bar context invalid (atr=%.5f)",atr);
      return;
     }

   MqlTick ticks[];
   long fromMsc=(long)barStart*1000;
   long toMsc=(long)barEnd*1000-1;
   ResetLastError();
   int copied=CopyTicksRange(_Symbol,ticks,COPY_TICKS_INFO,fromMsc,toMsc);
   int copyError=GetLastError();
   if(copied<=0)
     {
      g_orderFlowDiagnostics.Analyze(emptyTicks,0,priorHigh,priorLow,
                                     barHigh,barLow,barClose,atr,of);
      string missingStatus=(copied<0 ? "TICK_HISTORY_ERROR" : "NO_TICKS");
      AttachOrderFlowAuctionContext(barClose,of);
      AppendOrderFlowEvidence(barStart,barEnd,priorHigh,priorLow,
                              barHigh,barLow,barClose,atr,missingStatus,of);
      PrintFormat("OF_DIAG unavailable: status=%s copied=%d error=%d; no trade-policy effect",
                  missingStatus,copied,copyError);
      return;
     }

   if(!g_orderFlowDiagnostics.Analyze(ticks,copied,priorHigh,priorLow,
                                      barHigh,barLow,barClose,atr,of))
     {
      AttachOrderFlowAuctionContext(barClose,of);
      AppendOrderFlowEvidence(barStart,barEnd,priorHigh,priorLow,
                              barHigh,barLow,barClose,atr,"INVALID_OR_INSUFFICIENT_TICKS",of);
      PrintFormat("OF_DIAG rejected: insufficient/unordered data, ticks=%d",copied);
      return;
     }
   AttachOrderFlowAuctionContext(barClose,of);
   string diagnosticStatus=(of.data_stale ? "STALE_PROXY" : "OK_PROXY");
   AppendOrderFlowEvidence(barStart,barEnd,priorHigh,priorLow,
                           barHigh,barLow,barClose,atr,diagnosticStatus,of);
   PrintFormat("OF_DIAG symbol=%s tf=%s ticks=%d quality=%d pressure=%.3f progress=%.5f bull_reclaim=%s bear_reclaim=%s absorption_proxy=%s exhaustion_proxy=%s stale=%s (diagnostic only)",
               _Symbol,EnumToString(InpFVGTF),of.tick_count,(int)of.quality,
               of.pressure_ratio,of.price_progress,
               of.bullish_sweep_reclaim?"true":"false",
               of.bearish_sweep_reclaim?"true":"false",
               of.absorption_proxy?"true":"false",
               of.exhaustion_proxy?"true":"false",
               of.data_stale?"true":"false");
  }


bool AppendOrderFlowSignalAttribution(TradeSetup &setup)
  {
   string filename="MedisTouch_OrderFlowAttribution_v1_"+_Symbol+"_"+EnumToString(InpFVGTF)+".csv";
   int flags=FILE_CSV|FILE_READ|FILE_WRITE|FILE_SHARE_READ|FILE_ANSI;
   ResetLastError();
   int handle=FileOpen(filename,flags,',');
   if(handle==INVALID_HANDLE)
     {
      PrintFormat("OF_DIAG attribution file open failed: %s error=%d",filename,GetLastError());
      return false;
     }

   bool headerOK=true;
   if(FileSize(handle)==0)
     {
      uint headerBytes=FileWrite(handle,"schema_version","signal_id","event_key","symbol",
                                 "timeframe","direction","signal_epoch","attribution_status");
      headerOK=(headerBytes>0);
     }
   FileSeek(handle,0,SEEK_END);
   string direction=(setup.type==ORDER_TYPE_BUY ? "BUY" : "SELL");
   string signalId=StringFormat("%s_%s_%d",_Symbol,direction,(long)setup.creation_time);
   int maxEventAgeSeconds=PeriodSeconds(InpFVGTF);
   bool eventFresh=(StringLen(g_lastOrderFlowEventKey)>0 &&
                    g_lastOrderFlowEventBarEnd>0 && maxEventAgeSeconds>0 &&
                    setup.creation_time>=g_lastOrderFlowEventBarEnd &&
                    (setup.creation_time-g_lastOrderFlowEventBarEnd)<=maxEventAgeSeconds);
   string eventKey=(eventFresh ? g_lastOrderFlowEventKey : "");
   string status=(eventFresh ? "MATCHED" : "NO_USABLE_EVENT");
   uint rowBytes=FileWrite(handle,"order-flow-attribution-v1",signalId,eventKey,
                           _Symbol,EnumToString(InpFVGTF),direction,
                           IntegerToString((long)setup.creation_time),status);
   FileFlush(handle);
   bool ok=(headerOK && rowBytes>0 && GetLastError()==0);
   FileClose(handle);
   if(!ok)
      PrintFormat("OF_DIAG attribution row write failed for signal=%s error=%d",signalId,GetLastError());
   return ok;
}

void OnTick(){g_monitor.OnTickCheck();g_dailyTradeTarget.OnTick();g_pool.DetectAll();if(g_chartCtx==NULL||!g_chartCtx.candles.IsReady())return;double atr=g_chartCtx.candles.GetATR(0);g_positions.OnTick(atr);g_orders.Prune();g_riskGuard.OnTick();RefreshTradeControlPanel();if(g_emergencyStop)return;if(InpPublishLifecycleUpdates)CheckSignalLifecycle(atr);datetime barTime=iTime(_Symbol,_Period,0);bool isNewBar=(barTime!=g_lastBarTime);g_lastBarTime=barTime;if(InpEnableOrderFlowDiagnostics)LogOrderFlowDiagnostics();if(!isNewBar)return;if(InpTrackOutcomes)g_tracker.Update(g_chartCtx);string haltReason;if(g_riskGuard.IsHardHalted(haltReason))return;if(g_riskGuard.IsDailyLossLimitHit(haltReason))return;string newsReason;if(InpUseNewsFilter&&g_newsFilter.IsLocked(newsReason))return;if(!IsConfiguredSessionAllowed()){if(TimeCurrent()-g_lastSessionBlockLog>=900){g_execAudit.Log("SESSION_BLOCK","new automated entries suppressed outside configured session windows");g_lastSessionBlockLog=TimeCurrent();}return;}TradeSetup buySetup=g_decision.GenerateBuySetup();TradeSetup sellSetup=g_decision.GenerateSellSetup();TradeSetup chosen;ZeroMemory(chosen);double delta=buySetup.confidence-sellSetup.confidence;if(buySetup.active&&sellSetup.active){if(delta>=InpMinDirectionalAdvantage){if(g_risk.ValidateSetup(buySetup,InpMinRiskReward,InpMaxSLDistanceATR,atr))chosen=buySetup;}else if(-delta>=InpMinDirectionalAdvantage){if(g_risk.ValidateSetup(sellSetup,InpMinRiskReward,InpMaxSLDistanceATR,atr))chosen=sellSetup;}}else if(buySetup.active){if(g_risk.ValidateSetup(buySetup,InpMinRiskReward,InpMaxSLDistanceATR,atr))chosen=buySetup;}else if(sellSetup.active){if(g_risk.ValidateSetup(sellSetup,InpMinRiskReward,InpMaxSLDistanceATR,atr))chosen=sellSetup;}if(!chosen.active||chosen.creation_time==g_lastLoggedTime)return;g_lastLoggedTime=chosen.creation_time;chosen.calibrated_probability=g_tracker.GetCalibratedProbability(chosen.confidence,chosen.calibration_sample,chosen.calibration_has_enough_data);if(InpLogSignals){ENUM_TREND_STATE t=g_trendCtx.trend.GetCurrentTrend();bool signalLogged=g_logger.LogSetup(chosen,_Symbol,InpFVGTF,EnumToString(t));if(InpEnableOrderFlowDiagnostics && signalLogged)AppendOrderFlowSignalAttribution(chosen);}TradeDecisionRecord decision=g_router.Decide(chosen);g_execAudit.Log("DECISION",StringFormat("automated candidate action=%s confidence=%.1f reason=%s",TradePolicyToString(decision.action),decision.confidence,decision.reason),decision.decision_id,0,0.0,ResolveExecutionEntry(chosen),chosen.stop_loss,chosen.final_tp);decision.timeframe=_Period;decision.decision_schema_version=InpDecisionSchemaVersion;decision.strategy_version=InpStrategyVersion;decision.model_version=InpModelVersion;decision.calibration_version=InpCalibrationVersion;decision.feature_schema_version=InpFeatureSchemaVersion;decision.environment_schema_version=InpEnvironmentSchemaVersion;decision.weight_version=InpWeightSetVersion;decision.environment_key=g_environmentMemory.Key(chosen.reasons);decision.spread_points=chosen.reasons.spread_points;decision.decision_fingerprint=DecisionFingerprintFor(decision);if(InpTrackOutcomes)g_tracker.AddSetup(chosen,decision.decision_id,decision.decision_fingerprint);if(!decision.valid||decision.action==POLICY_IGNORE)return;if(!g_store.Save(decision)){PrintFormat("MedisTouch EA: decision #%I64d rejected — durable DecisionStore write failed.",decision.decision_id);return;}if(decision.action==POLICY_EXECUTE_ONLY||decision.action==POLICY_EXECUTE_AND_SIGNAL){if((InpRequireExecutionLedger && !g_executionLedger.Ready()) || (g_executionLedger.Ready() && !g_executionLedgerHealthy)){g_execAudit.Log("EXECUTION_LEDGER_NOT_READY","automated trade blocked until bridge admission and broker reconciliation are healthy",decision.decision_id);}else if(IsNettingOrExchangeAccount() && HasAnyChartSymbolExposure()){g_execAudit.Log("AUTOMATED_BLOCKED_NETTING_EXPOSURE",StringFormat("decision #%I64d suppressed: same-symbol position or pending order already exists on netting/exchange account",decision.decision_id),decision.decision_id);}else{int availableSlots=g_activeRiskLimits.maxOpenTrades-g_orders.OpenCount();if(availableSlots<0)availableSlots=0;MultiTradePlan plan;bool planOk=g_multiTrade.Build(decision.setup,availableSlots,plan);if(!planOk){PrintFormat("MedisTouch EA: decision #%I64d rejected — multi-trade plan construction failed.",decision.decision_id);return;}double entry=ResolveExecutionEntry(chosen);double legLots[3];double legRisk[3];for(int leg=0;leg<3;leg++){legLots[leg]=0.0;legRisk[leg]=0.0;}bool sizingOk=true;for(int leg=0;leg<plan.legCount;leg++){double fraction=plan.riskFraction[leg];bool exceeded=false;legLots[leg]=g_risk.CalculateLotSize(_Symbol,g_activeRiskLimits.riskPercentPerTrade*fraction,entry,chosen.stop_loss,decision.reduce_risk,InpAllowMinLotOverride,exceeded,g_riskGuard.SizeMultiplier());if(legLots[leg]<=0.0){sizingOk=false;break;}legRisk[leg]=g_risk.RiskAmountForLots(_Symbol,legLots[leg],entry,chosen.stop_loss);}if(!sizingOk){PrintFormat("MedisTouch EA: decision #%I64d skipped — one or more execution legs cannot satisfy broker lot/risk constraints.",decision.decision_id);return;}double totalProposedRisk=0.0;for(int leg=0;leg<plan.legCount;leg++)totalProposedRisk+=legRisk[leg];string block;if(!g_portfolio.AllowNewTradeBatch(_Symbol,totalProposedRisk,plan.legCount,block)){PrintFormat("MedisTouch EA: decision #%I64d blocked — %s",decision.decision_id,block);return;}ulong tickets[3];bool submittedAny=false;double maxDeviation=InpMaxEntryDeviationATR*atr;for(int leg=0;leg<plan.legCount;leg++){TradeDecisionRecord legDecision=decision;legDecision.setup.final_tp=plan.target[leg];legDecision.reason+=StringFormat("; multi-trade leg %d/%d (%s)",leg+1,plan.legCount,plan.label[leg]);string ledgerRequestId="";if(!PrepareLedgerForSubmit(legDecision,leg,legRisk[leg],atr,ledgerRequestId)){g_execAudit.Log("AUTOMATED_LEDGER_BLOCKED","bridge did not acknowledge pre-send reservation; this leg was not sent",decision.decision_id,0,legLots[leg],entry,chosen.stop_loss,plan.target[leg]);continue;}ulong ticket=0;if(g_orders.Submit(legDecision,legLots[leg],InpUseMarketOrders,maxDeviation,ticket,leg)){submittedAny=true;tickets[leg]=ticket;if(StringLen(ledgerRequestId)>0)MarkLedgerSubmissionAccepted(ledgerRequestId);if(!g_store.SaveExecution(decision.decision_id,legLots[leg],ticket,leg,plan.target[leg])){PrintFormat("CRITICAL: decision #%I64d leg %d executed but execution record was not durably persisted.",decision.decision_id,leg);g_execAudit.Log("CRITICAL_EXECUTION_RECORD_FAILURE","automated order submitted but execution persistence failed",decision.decision_id,ticket,legLots[leg],entry,chosen.stop_loss,plan.target[leg]);}else g_execAudit.Log("ORDER_SUBMITTED",StringFormat("automated leg %d/%d",leg+1,plan.legCount),decision.decision_id,ticket,legLots[leg],entry,chosen.stop_loss,plan.target[leg]);}else{if(StringLen(ledgerRequestId)>0)MarkLedgerSubmissionAmbiguous(ledgerRequestId);g_monitor.NotifyBrokerReject();g_execAudit.Log("ORDER_REJECTED","automated broker/order-manager submission failed; ledger reservation retained for broker reconciliation",decision.decision_id,0,legLots[leg],entry,chosen.stop_loss,plan.target[leg]);}}if(!submittedAny)PrintFormat("MedisTouch EA: decision #%I64d rejected by broker on every requested execution leg.",decision.decision_id);}}if(decision.action==POLICY_SIGNAL_ONLY||decision.action==POLICY_EXECUTE_AND_SIGNAL){g_publisher.Publish(decision);g_lifecycleDecisionId=decision.decision_id;g_lifecycleCreationTime=chosen.creation_time;g_lifecycleSetup=chosen;g_lifecycleStatus="valid";}}
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
   if(g_orders.OpenCount()>=g_activeRiskLimits.maxOpenTrades)
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
   double lots=g_risk.CalculateLotSize(_Symbol,g_activeRiskLimits.riskPercentPerTrade,entry,setup.stop_loss,
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

   string ledgerRequestId="";
   if(!PrepareLedgerForSubmit(decision,0,proposedRisk,atr,ledgerRequestId))
     { g_execAudit.Log("MANUAL_BLOCKED",side+" rejected: bridge reservation or SENT state was not acknowledged",decision.decision_id,0,lots,entry,setup.stop_loss,setup.final_tp); return; }
   ulong ticket=0;
   double maxDeviation=InpMaxEntryDeviationATR*atr;
   if(!g_orders.Submit(decision,lots,true,maxDeviation,ticket,0))
     {
      if(StringLen(ledgerRequestId)>0) MarkLedgerSubmissionAmbiguous(ledgerRequestId);
      g_monitor.NotifyBrokerReject();
      g_execAudit.Log("MANUAL_REJECTED",side+" market request rejected by execution layer",decision.decision_id,0,lots,entry,setup.stop_loss,setup.final_tp);
      return;
     }
   if(StringLen(ledgerRequestId)>0) MarkLedgerSubmissionAccepted(ledgerRequestId);
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

bool SendLedgerDealEvent(const ulong dealTicket,const ulong positionIdentifier)
  {
   if(!g_executionLedger.Ready()) return !InpRequireExecutionLedger;
   if(dealTicket==0 || positionIdentifier==0 || !HistoryDealSelect(dealTicket)) return false;

   string symbol=HistoryDealGetString(dealTicket,DEAL_SYMBOL);
   if(symbol=="") return false;
   ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket,DEAL_ENTRY);
   ENUM_DEAL_TYPE dealType=(ENUM_DEAL_TYPE)HistoryDealGetInteger(dealTicket,DEAL_TYPE);
   string entryType="IN";
   if(entry==DEAL_ENTRY_OUT) entryType="OUT";
   else if(entry==DEAL_ENTRY_OUT_BY) entryType="OUT_BY";
   else if(entry==DEAL_ENTRY_INOUT) entryType="INOUT";
   string dealSide=(dealType==DEAL_TYPE_BUY)?"BUY":"SELL";

   bool positionOpen=IsPositionIdentifierOpen(positionIdentifier);
   double remainingVolume=0.0;
   double riskR=0.0;
   string positionDirection=(entry==DEAL_ENTRY_IN)?dealSide:((dealSide=="BUY")?"SELL":"BUY");
   if(entry==DEAL_ENTRY_INOUT) positionDirection=dealSide;
   if(positionOpen)
     {
      ulong positionTicket=g_broker.PositionTicketForIdentifier(symbol,positionIdentifier);
      if(positionTicket==0 || !PositionSelectByTicket(positionTicket)) return false;
      long positionType=PositionGetInteger(POSITION_TYPE);
      positionDirection=(positionType==POSITION_TYPE_BUY)?"BUY":"SELL";
      remainingVolume=PositionGetDouble(POSITION_VOLUME);
      double stop=PositionGetDouble(POSITION_SL);
      double openPrice=PositionGetDouble(POSITION_PRICE_OPEN);
      if(stop<=0.0 || openPrice<=0.0 || remainingVolume<=0.0) return false;
      double riskMoney=g_risk.RiskAmountForLots(symbol,remainingVolume,openPrice,stop);
      if(!RiskRFromMoney(riskMoney,riskR)) return false;
     }

   double volume=HistoryDealGetDouble(dealTicket,DEAL_VOLUME);
   double price=HistoryDealGetDouble(dealTicket,DEAL_PRICE);
   double profit=HistoryDealGetDouble(dealTicket,DEAL_PROFIT);
   double commission=HistoryDealGetDouble(dealTicket,DEAL_COMMISSION);
   double swap=HistoryDealGetDouble(dealTicket,DEAL_SWAP);
   double fee=HistoryDealGetDouble(dealTicket,DEAL_FEE);
   ulong orderId=(ulong)HistoryDealGetInteger(dealTicket,DEAL_ORDER);
   string evidence=StringFormat("mt5-deal:%I64u",dealTicket);
   string requestId=g_executionLedger.RequestIdForPosition(positionIdentifier);
   return g_executionLedger.DealEvent(requestId,dealTicket,orderId,positionIdentifier,
                                      symbol,entryType,dealSide,positionDirection,
                                      volume,price,profit,commission,swap,fee,true,
                                      positionOpen,remainingVolume,riskR,0.0,evidence);
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
   // Persist each immutable broker deal before local tracking can return.
   // Failed writes keep new entries blocked until restart/history reconciliation repairs the ledger.
   if(g_executionLedger.Ready() && !SendLedgerDealEvent(trans.deal,positionIdentifier))
     {
      g_executionLedgerHealthy=false;
      g_execAudit.Log("LEDGER_DEAL_EVENT_FAILED","broker deal evidence could not be persisted; execution admission remains blocked",
                      0,positionIdentifier,HistoryDealGetDouble(trans.deal,DEAL_VOLUME),
                      HistoryDealGetDouble(trans.deal,DEAL_PRICE));
     }

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
      bool tracked=g_tracker.MarkClosed(decisionId,price,dealTime,net,commission,swap,fee,stillOpen,
                                        outcome,trans.deal,volume,true);
      if(tracked && !stillOpen && g_tracker.LastFinalizedQualified())
         g_dailyTradeTarget.OnQualifiedClose(dealTime,g_tracker.LastFinalizedR(),positionIdentifier);
      g_execAudit.Log("FILL_OUT",
                      StringFormat("outcome=%s net=%.2f commission=%.2f swap=%.2f fee=%.2f still_open=%s deal=%I64u position_id=%I64u",
                                   outcome,net,commission,swap,fee,stillOpen?"true":"false",trans.deal,positionIdentifier),
                      decisionId,positionTicket,volume,price);
     }
  }
//+------------------------------------------------------------------+
