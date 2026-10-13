//+------------------------------------------------------------------+
//| Trading/OutcomeTrackerLive.mqh                                  |
//+------------------------------------------------------------------+
#ifndef OUTCOMETRACKERLIVE_MQH
#define OUTCOMETRACKERLIVE_MQH
#include "../Core/Config.mqh"
#include "../Core/SignalLogger.mqh"
#include "CalibrationEngine.mqh"
#include "../Signals/SignalPublisher.mqh"
#include "EnvironmentStrategyMemory.mqh"
class COutcomeTrackerLive;
COutcomeTrackerLive* g_activeOutcomeTracker=NULL;

struct OutcomeReplayDeal
  {
   ulong ticket;
   ulong positionId;
   long timeMsc;
   ENUM_DEAL_ENTRY entry;
   datetime time;
   double volume;
   double price;
   double profit;
   double commission;
   double swap;
   double fee;
  };

class COutcomeTrackerLive
  {
private:
   PendingSetup m_pending[]; int m_count; int m_maxBars; CSignalLogger* m_logger; CSignalPublisher* m_publisher; CCalibrationEngine m_calibration; CEnvironmentStrategyMemory* m_environmentMemory;
   bool m_calibrationEnabled; string m_symbol; ENUM_TIMEFRAMES m_entryTF; ENUM_FILL_POLICY m_fillPolicy; ENUM_TIMEFRAMES m_replayTF; OutcomeStats m_stats;
   double m_breakEvenAtR,m_partialAtR,m_partialFraction,m_trailATRMult,m_riskPercent; bool m_allowMinLotOverride,m_liveExecution;
   double m_commissionPerLot,m_spreadPoints,m_slippagePoints,m_decayHalfLifeBars; string m_weightVersion;
   double m_lastFinalizedR; bool m_lastFinalizedQualified;
   ulong m_seenDealTickets[];
   long m_rebuiltDecisionIds[];
   bool WasDecisionRebuilt(long decisionId)
     {
      for(int i=0;i<ArraySize(m_rebuiltDecisionIds);i++)
         if(m_rebuiltDecisionIds[i]==decisionId) return true;
      return false;
     }
   bool MarkDecisionRebuilt(long decisionId)
     {
      if(WasDecisionRebuilt(decisionId)) return true;
      int n=ArraySize(m_rebuiltDecisionIds);
      if(ArrayResize(m_rebuiltDecisionIds,n+1)!=n+1) return false;
      m_rebuiltDecisionIds[n]=decisionId;
      return true;
     }
   bool HistoryIdentityDigits(const string value)
     {
      int length=StringLen(value);
      if(length<=0) return false;
      for(int i=0;i<length;i++)
        {
         ushort ch=StringGetCharacter(value,i);
         if(ch<'0' || ch>'9') return false;
        }
      return true;
     }
   bool ParseHistoryDecisionComment(string comment,long &decisionId)
     {
      decisionId=0;
      int marker=StringFind(comment,"MT#");
      if(marker<0) return false;

      string payload=StringSubstr(comment,marker+3);
      int separator=StringFind(payload,":L");
      if(separator>=0)
        {
         string legPart=StringSubstr(payload,separator+2);
         payload=StringSubstr(payload,0,separator);
         if(!HistoryIdentityDigits(legPart)) return false;
         long leg=StringToInteger(legPart);
         // A valid broker comment must match the EA's canonical identity format.
         if(leg<0 || leg>2147483647 || IntegerToString(leg)!=legPart) return false;
        }
      else if(StringFind(payload,":")>=0)
        {
         // Reject malformed suffixes such as :Lx or :legacy instead of
         // truncating at the colon and attributing the deal to another setup.
         return false;
        }

      if(!HistoryIdentityDigits(payload)) return false;
      decisionId=(long)StringToInteger(payload);
      if(decisionId<=0 || IntegerToString(decisionId)!=payload) return false;
      return true;
     }
   bool HistoryDealDecisionId(ulong dealTicket,long &decisionId)
     {
      string dealComment=HistoryDealGetString(dealTicket,DEAL_COMMENT);
      if(ParseHistoryDecisionComment(dealComment,decisionId)) return true;
      ulong orderTicket=(ulong)HistoryDealGetInteger(dealTicket,DEAL_ORDER);
      if(orderTicket>0)
        {
         string orderComment=HistoryOrderGetString(orderTicket,ORDER_COMMENT);
         if(ParseHistoryDecisionComment(orderComment,decisionId)) return true;
        }
      decisionId=0;
      return false;
     }
   int ReplayPositionIndex(const ulong &positionIds[],ulong positionId)
     {
      for(int i=0;i<ArraySize(positionIds);i++)
         if(positionIds[i]==positionId) return i;
      return -1;
     }
   bool DealAlreadyProcessed(ulong dealTicket)
     {
      if(dealTicket==0) return false;
      for(int i=0;i<ArraySize(m_seenDealTickets);i++)
         if(m_seenDealTickets[i]==dealTicket) return true;
      return false;
     }
   void RememberDeal(ulong dealTicket)
     {
      if(dealTicket==0 || DealAlreadyProcessed(dealTicket)) return;
      int n=ArraySize(m_seenDealTickets);
      if(ArrayResize(m_seenDealTickets,n+1)!=n+1) return;
      m_seenDealTickets[n]=dealTicket;
     }
   int Find(long id){for(int i=0;i<m_count;i++)if(m_pending[i].decisionId==id)return i;return -1;}
   double RValue(const PendingSetup &p) const{double ts=SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_SIZE),tv=SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_VALUE);if(ts<=0.0||tv<=0.0)return 0.0;double riskLotsDistance=p.weightedRiskDistLots>0.0?p.weightedRiskDistLots:(p.mgmtRiskDist*p.lots);if(riskLotsDistance<=0.0)return 0.0;double oneR=riskLotsDistance*(tv/ts);return oneR>0.0?p.realizedPnL/oneR:0.0;}
   string EnvironmentJson(const PendingSetup &p) const{SetupReasons r=p.setup.reasons;string structure=EnumToString(r.sweep_grade)+"/"+IntegerToString((int)r.breakout_class)+"/"+IntegerToString((int)r.reversion_class)+"/"+IntegerToString((int)r.keylevel_reaction);return StringFormat("{\"regime\":\"%s\",\"volatility_state\":\"%s\",\"trend_strength\":%.3f,\"liquidity_score\":%.3f,\"liquidity_bucket\":%d,\"news_state\":\"%s\",\"session\":\"%s\",\"spread_points\":%.2f,\"point_size\":%.10f,\"atr_value\":%.10f,\"atr_regime\":\"%s\",\"htf_ob_aligned\":%s,\"htf_ob_state\":\"%s\",\"value_area_zone\":\"%s\",\"market_phase\":\"%s\",\"market_structure\":\"%s\",\"bos_strength\":%.3f,\"sweep_grade\":\"%s\"}",EnumToString(r.regime),EnumToString(r.vol_regime),r.trend_strength,r.liquidity_score,r.liquidity_bucket,EnumToString(r.news_risk),EnumToString(r.session),r.spread_points,r.point_size,r.atr_value,EnumToString(r.vol_regime),r.htf_ob_confluence?"true":"false",EnumToString(r.htf_ob_state),EnumToString(r.va_zone),EnumToString(r.phase),structure,r.bos_strength,EnumToString(r.sweep_grade));}
   void Finalize(int idx,string exitReason,double exitPrice,datetime outcomeTime){m_lastFinalizedR=0.0;m_lastFinalizedQualified=false;if(idx<0||idx>=m_count)return;PendingSetup p=m_pending[idx];datetime resolvedAt=outcomeTime;if(resolvedAt<=0)resolvedAt=TimeCurrent();double rr=RValue(p);bool sized=p.filled&&p.lots>0.0;string coarseOutcome="scratch";if(!p.filled)coarseOutcome="no_fill";else if(p.realizedPnL>0.0000001)coarseOutcome="win";else if(p.realizedPnL<-0.0000001)coarseOutcome="loss";if((!p.outcomeHistoryComplete||!p.cashflowsKnown)&&p.filled)coarseOutcome="ambiguous";if(exitReason=="Ambiguous_SLandBE"||exitReason=="Ambiguous_SLandPartial"||exitReason=="Ambiguous_SLandTP"||exitReason=="Ambiguous_NettingReversal")coarseOutcome="ambiguous";m_lastFinalizedR=rr;m_lastFinalizedQualified=(sized&&p.outcomeHistoryComplete&&p.cashflowsKnown&&coarseOutcome=="win"&&p.realizedPnL>0.0000001);if(sized&&coarseOutcome!="ambiguous"&&coarseOutcome!="no_fill"){if(coarseOutcome=="win")m_stats.wins++;else if(coarseOutcome=="loss")m_stats.losses++;else m_stats.scratches++;m_stats.resolvedCount++;m_stats.netPnL+=p.realizedPnL;if(p.realizedPnL>0)m_stats.grossProfit+=p.realizedPnL;if(p.realizedPnL<0)m_stats.grossLoss+=-p.realizedPnL;m_stats.totalCommission+=p.totalCommission;m_stats.totalSpreadCost+=p.totalSpreadCost;m_stats.totalSlippageCost+=p.totalSlippageCost;m_stats.sumRMultiple+=rr;if(m_calibrationEnabled)m_calibration.Record(p.confidenceAtSignal,p.realizedPnL);if(m_environmentMemory!=NULL&&p.excursionHistoryComplete){bool buy=p.setup.type==ORDER_TYPE_BUY;double mfeR=0.0,maeR=0.0;if(p.mgmtRiskDist>0.0){mfeR=buy?(p.mfePrice-p.entryRef)/p.mgmtRiskDist:(p.entryRef-p.maePrice)/p.mgmtRiskDist;maeR=buy?(p.entryRef-p.maePrice)/p.mgmtRiskDist:(p.maePrice-p.entryRef)/p.mgmtRiskDist;}m_environmentMemory.RecordOutcome(p.setup.reasons,p.setup.reasons.selected_strategy,rr,maeR,mfeR,p.barsElapsed,resolvedAt);}}else if(coarseOutcome=="ambiguous")m_stats.ambiguous++;if(m_logger!=NULL)m_logger.LogOutcome(p,m_symbol,m_entryTF,exitReason,exitPrice,m_fillPolicy,resolvedAt);if(m_publisher!=NULL&&p.decisionId>0){bool buy=p.setup.type==ORDER_TYPE_BUY;double mfeR=0.0,maeR=0.0;if(p.filled&&p.mgmtRiskDist>0){double mfe=buy?(p.mfePrice-p.entryRef):(p.entryRef-p.mfePrice);double mae=buy?(p.entryRef-p.maePrice):(p.maePrice-p.entryRef);mfeR=mfe/p.mgmtRiskDist;maeR=mae/p.mgmtRiskDist;}if(!p.excursionHistoryComplete){mfeR=0.0;maeR=0.0;}string signalId=m_publisher.SignalIdForDecision(p.decisionId);string strategy=EnumToString(p.setup.reasons.selected_strategy);string envKey="";if(m_environmentMemory!=NULL)envKey=m_environmentMemory.Key(p.setup.reasons);m_publisher.PublishOutcome(signalId,m_symbol,buy?"BUY":"SELL",coarseOutcome,exitReason,strategy,rr,mfeR,maeR,p.totalCommission,p.totalSpreadCost,p.totalSlippageCost,p.barsElapsed,p.barsToFill,p.filled,EnumToString(p.setup.reasons.regime),EnumToString(p.setup.reasons.session),EnumToString(p.setup.reasons.sweep_grade),p.setup.reasons.htf_ob_confluence,p.confidenceAtSignal,p.confidenceDecayed,p.decayBars,p.decision_fingerprint,p.setup.creation_time,p.fillTime,resolvedAt,p.excursionHistoryComplete,p.totalCommissionCashflow,p.totalSwapCashflow,p.totalBrokerFeeCashflow,p.cashflowsKnown,p.spreadCostKnown,p.slippageCostKnown,envKey,EnvironmentJson(p),p.outcomeHistoryComplete);}for(int j=idx;j<m_count-1;j++)m_pending[j]=m_pending[j+1];m_count--;ArrayResize(m_pending,m_count);}
   void SimFill(int i,double price,datetime t){if(i<0||i>=m_count||m_pending[i].filled)return;PendingSetup p=m_pending[i];p.filled=true;p.fillTime=t;p.barsToFill=0;p.entryRef=price;p.entryFillPrice=price;p.mfePrice=price;p.maePrice=price;p.riskDist=MathAbs(price-p.setup.stop_loss);p.mgmtRiskDist=p.riskDist;m_pending[i]=p;}
public:
   COutcomeTrackerLive():m_count(0),m_maxBars(100),m_logger(NULL),m_publisher(NULL),m_environmentMemory(NULL),m_calibrationEnabled(false),m_symbol(""),m_entryTF(PERIOD_CURRENT),m_fillPolicy(FILL_CONSERVATIVE),m_replayTF(PERIOD_M1),m_breakEvenAtR(1.0),m_partialAtR(2.0),m_partialFraction(0.5),m_trailATRMult(1.5),m_riskPercent(0.5),m_allowMinLotOverride(true),m_liveExecution(true),m_commissionPerLot(7.0),m_spreadPoints(10.0),m_slippagePoints(2.0),m_decayHalfLifeBars(12.0),m_weightVersion(""),m_lastFinalizedR(0.0),m_lastFinalizedQualified(false){ZeroMemory(m_stats);g_activeOutcomeTracker=GetPointer(this);}
   void Init(CSignalLogger* logger,string symbol,ENUM_TIMEFRAMES tf,int maxBars,ENUM_FILL_POLICY fp=FILL_CONSERVATIVE,ENUM_TIMEFRAMES replayTF=PERIOD_M1){m_logger=logger;m_symbol=symbol;m_entryTF=tf;m_maxBars=MathMax(5,maxBars);m_fillPolicy=fp;m_replayTF=replayTF;m_count=0;m_lastFinalizedR=0.0;m_lastFinalizedQualified=false;ArrayResize(m_pending,0);ArrayResize(m_seenDealTickets,0);ArrayResize(m_rebuiltDecisionIds,0);ZeroMemory(m_stats);}
   void ConfigureExecutionMode(bool live){m_liveExecution=live;}void ConfigureSimulation(double risk,bool allow,double be,double partial,double frac,double trail,double comm,double spread,double slip){m_riskPercent=risk;m_allowMinLotOverride=allow;m_breakEvenAtR=be;m_partialAtR=partial;m_partialFraction=MathMax(0.0,MathMin(1.0,frac));m_trailATRMult=trail;m_commissionPerLot=MathMax(0.0,comm);m_spreadPoints=MathMax(0.0,spread);m_slippagePoints=MathMax(0.0,slip);}void ConfigureCalibration(bool enabled,int minSample=30){m_calibrationEnabled=enabled;m_calibration.Init(m_symbol,minSample);}void ConfigureConfidenceDecay(double halfLife=12.0){m_decayHalfLifeBars=halfLife;}void ConfigurePublishing(CSignalPublisher* p,string version){m_publisher=p;m_weightVersion=version;}void ConfigureEnvironmentMemory(CEnvironmentStrategyMemory* memory){m_environmentMemory=memory;}
   int ActiveCount()const{return m_count;}double LastFinalizedR()const{return m_lastFinalizedR;}bool LastFinalizedQualified()const{return m_lastFinalizedQualified;}OutcomeStats GetStats()const{return m_stats;}double GetCalibratedProbability(double confidence,int &sample,bool &enough)const{return m_calibration.GetCalibratedProbability(confidence,sample,enough);}
   void AddSetup(TradeSetup &setup,long decisionId=-1,string decisionFingerprint=""){if(!setup.active||decisionId<=0||Find(decisionId)>=0)return;PendingSetup p;ZeroMemory(p);p.setup=setup;p.decisionId=decisionId;p.decision_fingerprint=decisionFingerprint;p.entryRef=ResolveExecutionEntry(setup);p.riskDist=MathAbs(p.entryRef-setup.stop_loss);p.sizingEntryPrice=p.entryRef;p.mgmtRiskDist=p.riskDist;p.weightedRiskDistLots=0.0;p.mfePrice=p.entryRef;p.maePrice=p.entryRef;p.currentSL=setup.stop_loss;p.confidenceAtSignal=setup.confidence;p.confidenceDecayed=setup.confidence;p.cashflowsKnown=true;p.outcomeHistoryComplete=true;p.excursionHistoryComplete=true;int n=m_count++;ArrayResize(m_pending,m_count);m_pending[n]=p;}
   // Rebuild only a currently-live decision from broker deal history. Completed
   // decisions are intentionally not replayed here: replaying them on every restart
   // would duplicate calibration samples and published outcomes. The method first
   // validates the entire candidate ledger against current broker exposure, then
   // mutates tracker state; if validation fails the caller uses an ambiguous snapshot.
   bool RebuildOpenDecisionFromHistory(TradeSetup &setup,long decisionId,ulong livePositionId,ulong magic)
     {
      if(decisionId<=0 || livePositionId==0 || magic==0) return false;
      if(WasDecisionRebuilt(decisionId)) return true;
      if(Find(decisionId)>=0) return false;

      datetime fromTime=setup.creation_time>0 ? setup.creation_time-1 : 0;
      datetime toTime=TimeCurrent();
      if(toTime<fromTime || !HistorySelect(fromTime,toTime)) return false;

      ulong positionIds[];
      if(ArrayResize(positionIds,1)!=1) return false;
      positionIds[0]=livePositionId;
      bool liveEntryConfirmed=false;
      int totalDeals=HistoryDealsTotal();

      // Pass 1: enumerate every position identifier tied to this decision using
      // entry deal identity or its originating order comment. We require the
      // live position's original entry to be provable before trusting its history.
      for(int i=0;i<totalDeals;i++)
        {
         ulong dealTicket=HistoryDealGetTicket(i);
         if(dealTicket==0) continue;
         if(HistoryDealGetString(dealTicket,DEAL_SYMBOL)!=m_symbol) continue;
         if((ulong)HistoryDealGetInteger(dealTicket,DEAL_MAGIC)!=magic) continue;
         ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket,DEAL_ENTRY);
         if(entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_INOUT) continue;
         long foundDecision=0;
         if(!HistoryDealDecisionId(dealTicket,foundDecision) || foundDecision!=decisionId) continue;
         ulong positionId=(ulong)HistoryDealGetInteger(dealTicket,DEAL_POSITION_ID);
         if(positionId==0) return false;
         if(positionId==livePositionId) liveEntryConfirmed=true;
         if(ReplayPositionIndex(positionIds,positionId)<0)
           {
            int n=ArraySize(positionIds);
            if(ArrayResize(positionIds,n+1)!=n+1) return false;
            positionIds[n]=positionId;
           }
        }
      if(!liveEntryConfirmed || ArraySize(positionIds)==0) return false;

      // Pass 2: materialize a deterministic per-deal ledger across every child
      // position in this decision. A netting reversal cannot be safely reduced to
      // ordinary close/open rows here, so it deliberately fails closed.
      OutcomeReplayDeal deals[];
      double expectedRemaining[];
      if(ArrayResize(expectedRemaining,ArraySize(positionIds))!=ArraySize(positionIds)) return false;
      ArrayInitialize(expectedRemaining,0.0);
      for(int i=0;i<totalDeals;i++)
        {
         ulong dealTicket=HistoryDealGetTicket(i);
         if(dealTicket==0) continue;
         if(HistoryDealGetString(dealTicket,DEAL_SYMBOL)!=m_symbol) continue;
         if((ulong)HistoryDealGetInteger(dealTicket,DEAL_MAGIC)!=magic) continue;
         ulong positionId=(ulong)HistoryDealGetInteger(dealTicket,DEAL_POSITION_ID);
         int pidx=ReplayPositionIndex(positionIds,positionId);
         if(pidx<0) continue;
         ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket,DEAL_ENTRY);
         if(entry==DEAL_ENTRY_INOUT) return false;
         if(entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY) continue;

         OutcomeReplayDeal row;
         row.ticket=dealTicket;
         row.positionId=positionId;
         row.timeMsc=(long)HistoryDealGetInteger(dealTicket,DEAL_TIME_MSC);
         row.time=(datetime)HistoryDealGetInteger(dealTicket,DEAL_TIME);
         row.entry=entry;
         row.volume=HistoryDealGetDouble(dealTicket,DEAL_VOLUME);
         row.price=HistoryDealGetDouble(dealTicket,DEAL_PRICE);
         row.profit=HistoryDealGetDouble(dealTicket,DEAL_PROFIT);
         row.commission=HistoryDealGetDouble(dealTicket,DEAL_COMMISSION);
         row.swap=HistoryDealGetDouble(dealTicket,DEAL_SWAP);
         row.fee=HistoryDealGetDouble(dealTicket,DEAL_FEE);
         if(row.volume<=0.0 || row.price<=0.0 || row.time<=0) return false;

         int n=ArraySize(deals);
         if(ArrayResize(deals,n+1)!=n+1) return false;
         deals[n]=row;
         if(entry==DEAL_ENTRY_IN)
            expectedRemaining[pidx]+=row.volume;
         else
           {
            expectedRemaining[pidx]-=row.volume;
            double step=SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_STEP);
            double tolerance=MathMax(1e-7,step*0.51);
            if(expectedRemaining[pidx]<-tolerance) return false;
            if(expectedRemaining[pidx]<0.0) expectedRemaining[pidx]=0.0;
           }
        }
      if(ArraySize(deals)==0) return false;

      // Broker open positions must match the volume reconstructed from all entries
      // and partial exits. This catches missing history rows, reversals and bad IDs.
      double actualRemaining[];
      if(ArrayResize(actualRemaining,ArraySize(positionIds))!=ArraySize(positionIds)) return false;
      ArrayInitialize(actualRemaining,0.0);
      for(int i=0;i<PositionsTotal();i++)
        {
         ulong ticket=PositionGetTicket(i);
         if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
         if(PositionGetString(POSITION_SYMBOL)!=m_symbol) continue;
         if((ulong)PositionGetInteger(POSITION_MAGIC)!=magic) continue;
         ulong positionId=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
         int pidx=ReplayPositionIndex(positionIds,positionId);
         if(pidx>=0) actualRemaining[pidx]+=PositionGetDouble(POSITION_VOLUME);
        }
      double volumeStep=SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_STEP);
      double volumeTolerance=MathMax(1e-7,volumeStep*0.51);
      for(int i=0;i<ArraySize(positionIds);i++)
         if(MathAbs(expectedRemaining[i]-actualRemaining[i])>volumeTolerance) return false;
      if(actualRemaining[ReplayPositionIndex(positionIds,livePositionId)]<=0.0) return false;

      // Sort deterministically by broker millisecond timestamp then unique deal ticket.
      for(int i=1;i<ArraySize(deals);i++)
        {
         OutcomeReplayDeal key=deals[i];
         int j=i-1;
         while(j>=0 && (deals[j].timeMsc>key.timeMsc ||
               (deals[j].timeMsc==key.timeMsc && deals[j].ticket>key.ticket)))
           {
            deals[j+1]=deals[j];
            j--;
           }
         deals[j+1]=key;
        }

      AddSetup(setup,decisionId);
      int trackerIndex=Find(decisionId);
      if(trackerIndex<0) return false;
      PendingSetup state=m_pending[trackerIndex];
      state.outcomeHistoryComplete=true;
      state.cashflowsKnown=true;
      state.excursionHistoryComplete=false;
      m_pending[trackerIndex]=state;

      // Replay historical partial closes but keep the parent decision active while
      // any part of it is currently open. Every deal ticket is remembered so the
      // terminal's subsequent transaction callback cannot double-count it.
      for(int i=0;i<ArraySize(deals);i++)
        {
         OutcomeReplayDeal row=deals[i];
         if(row.entry==DEAL_ENTRY_IN)
           {
            if(!MarkExecuted(decisionId,row.price,row.time,row.volume,row.ticket,row.commission,row.swap,row.fee,true))
              {
               MarkHistoryIncomplete(decisionId);
               return false;
              }
           }
         else
           {
            double net=row.profit+row.commission+row.swap+row.fee;
            if(!MarkClosed(decisionId,row.price,row.time,net,row.commission,row.swap,row.fee,
                           true,"Recovered_Partial",row.ticket,row.volume,true))
              {
               MarkHistoryIncomplete(decisionId);
               return false;
              }
           }
        }
      return MarkDecisionRebuilt(decisionId);
     }

   bool MarkExecuted(long id,double fill,datetime t,double volume,ulong dealTicket=0,double commission=0.0,double swap=0.0,double fee=0.0,bool cashflowsKnown=true)
     {
      m_lastFinalizedR=0.0;
      m_lastFinalizedQualified=false;
      if(DealAlreadyProcessed(dealTicket)) return true;
      int i=Find(id);
      if(i<0) return false;
      if(!MathIsValidNumber(fill) || !MathIsValidNumber(volume) || fill<=0.0 || volume<=0.0)
        {
         // Do not let NaN/Inf values poison the parent's P&L or volume state.
         // The real broker fill still requires reconciliation before learning.
         MarkHistoryIncomplete(id);
         return false;
        }

      bool costValuesValid=MathIsValidNumber(commission) &&
                           MathIsValidNumber(swap) &&
                           MathIsValidNumber(fee);
      bool timeValid=(t>0);
      if(!costValuesValid)
        {
         if(!MathIsValidNumber(commission)) commission=0.0;
         if(!MathIsValidNumber(swap)) swap=0.0;
         if(!MathIsValidNumber(fee)) fee=0.0;
        }
      if(!timeValid) t=TimeCurrent();

      PendingSetup p=m_pending[i];
      if(!timeValid || !costValuesValid)
        {
         p.outcomeHistoryComplete=false;
         p.excursionHistoryComplete=false;
        }
      double nextPnL=p.realizedPnL+commission+swap+fee;
      double nextCommissionCashflow=p.totalCommissionCashflow+commission;
      double nextSwapCashflow=p.totalSwapCashflow+swap;
      double nextFeeCashflow=p.totalBrokerFeeCashflow+fee;
      double nextCommission=p.totalCommission+MathMax(0.0,-commission);
      bool totalsValid=MathIsValidNumber(nextPnL) &&
                       MathIsValidNumber(nextCommissionCashflow) &&
                       MathIsValidNumber(nextSwapCashflow) &&
                       MathIsValidNumber(nextFeeCashflow) &&
                       MathIsValidNumber(nextCommission);
      if(totalsValid)
        {
         p.realizedPnL=nextPnL;
         p.totalCommissionCashflow=nextCommissionCashflow;
         p.totalSwapCashflow=nextSwapCashflow;
         p.totalBrokerFeeCashflow=nextFeeCashflow;
         p.totalCommission=nextCommission;
        }
      else
        {
         p.outcomeHistoryComplete=false;
         p.cashflowsKnown=false;
        }
      p.cashflowsKnown=p.cashflowsKnown && cashflowsKnown && costValuesValid && totalsValid;

      double stopLoss=p.setup.stop_loss;
      double riskIncrement=(MathIsValidNumber(stopLoss) && stopLoss>0.0)
                           ? MathAbs(fill-stopLoss)*volume : 0.0;
      if(!MathIsValidNumber(riskIncrement))
        {
         riskIncrement=0.0;
         p.outcomeHistoryComplete=false;
         p.excursionHistoryComplete=false;
        }

      if(p.filled)
        {
         // Multiple partial fills/target legs share a parent decision. Keep a
         // true volume-weighted fill price, but do not train MFE/MAE on a single
         // path when that parent contains fills at different prices/times.
         if(!MathIsValidNumber(p.lots) || p.lots<=0.0 ||
            !MathIsValidNumber(p.entryFillPrice) || p.entryFillPrice<=0.0)
           {
            p.outcomeHistoryComplete=false;
            p.excursionHistoryComplete=false;
            p.cashflowsKnown=false;
            m_pending[i]=p;
            return false;
           }
         double totalLots=p.lots+volume;
         double totalNotional=p.entryFillPrice*p.lots+fill*volume;
         double nextRemaining=p.remainingLots+volume;
         if(!MathIsValidNumber(totalLots) || totalLots<=p.lots ||
            !MathIsValidNumber(nextRemaining) || nextRemaining<=p.remainingLots)
           {
            p.outcomeHistoryComplete=false;
            p.excursionHistoryComplete=false;
            m_pending[i]=p;
            return false;
           }
         p.lots=totalLots;
         p.remainingLots=nextRemaining;
         if(MathIsValidNumber(totalNotional) && totalNotional>0.0)
           {
            double averageFill=totalNotional/totalLots;
            if(MathIsValidNumber(averageFill) && averageFill>0.0)
              {
               p.entryFillPrice=averageFill;
               p.entryRef=averageFill;
              }
            else
               p.outcomeHistoryComplete=false;
           }
         else
            p.outcomeHistoryComplete=false;

         double weightedRisk=p.weightedRiskDistLots+riskIncrement;
         if(MathIsValidNumber(weightedRisk) && weightedRisk>=0.0)
            p.weightedRiskDistLots=weightedRisk;
         else
            p.outcomeHistoryComplete=false;
         p.excursionHistoryComplete=false;
         p.mfePrice=0.0;
         p.maePrice=0.0;
         m_pending[i]=p;
         RememberDeal(dealTicket);
         return true;
        }

      p.filled=true;
      p.entryFillPrice=fill;
      p.entryRef=fill;
      p.fillTime=t;
      p.barsToFill=0;
      p.lots=volume;
      p.remainingLots=volume;
      p.riskDist=riskIncrement/volume;
      p.mgmtRiskDist=p.riskDist;
      p.weightedRiskDistLots=riskIncrement;
      p.mfePrice=fill;
      p.maePrice=fill;
      p.currentSL=(MathIsValidNumber(stopLoss) && stopLoss>0.0) ? stopLoss : 0.0;
      if(riskIncrement<=0.0)
        {
         p.outcomeHistoryComplete=false;
         p.excursionHistoryComplete=false;
        }
      m_pending[i]=p;
      RememberDeal(dealTicket);
      return true;
     }
   bool RestoreExecuted(TradeSetup &setup,long id,double fill,datetime t,double volume)
     {
      AddSetup(setup,id);
      if(!MarkExecuted(id,fill,t,volume,0,0.0,0.0,0.0,false)) return false;
      int i=Find(id);if(i<0)return false;
      PendingSetup p=m_pending[i];
      // A current-position snapshot contains remaining volume, not complete
      // entry/partial-exit deal history. Keep it out of calibration and learning
      // until broker history has been reconciled.
      p.cashflowsKnown=false;p.outcomeHistoryComplete=false;p.excursionHistoryComplete=false;
      m_pending[i]=p;
      return true;
     }
   void MarkHistoryIncomplete(long id)
     {
      int i=Find(id);if(i<0)return;
      PendingSetup p=m_pending[i];p.outcomeHistoryComplete=false;p.cashflowsKnown=false;p.excursionHistoryComplete=false;m_pending[i]=p;
     }
   bool MarkClosed(long id,double exitPrice,datetime t,double netPnl,double commission,double swap,double fee,bool stillOpen,string outcome,ulong dealTicket=0,double closedVolume=0.0,bool cashflowsKnown=true)
     {
      m_lastFinalizedR=0.0;
      m_lastFinalizedQualified=false;
      if(DealAlreadyProcessed(dealTicket)) return true;
      int i=Find(id);
      if(i<0) return false;
      PendingSetup p=m_pending[i];
      if(!p.filled) return false;

      bool timeValid=(t>0);
      bool exitPriceValid=MathIsValidNumber(exitPrice) && exitPrice>0.0;
      bool pnlValid=MathIsValidNumber(netPnl);
      bool volumeValid=MathIsValidNumber(closedVolume) && closedVolume>=0.0;
      bool costValuesValid=MathIsValidNumber(commission) &&
                           MathIsValidNumber(swap) &&
                           MathIsValidNumber(fee);
      if(!timeValid) t=TimeCurrent();
      if(!exitPriceValid) exitPrice=0.0;
      if(!pnlValid) netPnl=0.0;
      if(!costValuesValid)
        {
         if(!MathIsValidNumber(commission)) commission=0.0;
         if(!MathIsValidNumber(swap)) swap=0.0;
         if(!MathIsValidNumber(fee)) fee=0.0;
        }
      if(!volumeValid) closedVolume=0.0;

      // Incomplete broker values must never fall through into a scratch label
      // (NaN comparisons are false in MQL5). Continue tracking the close using
      // only finite values, but mark the outcome ineligible for calibration.
      if(!timeValid || !exitPriceValid || !pnlValid || !volumeValid)
        {
         p.outcomeHistoryComplete=false;
         p.excursionHistoryComplete=false;
        }
      if(!costValuesValid)
        {
         p.cashflowsKnown=false;
         p.outcomeHistoryComplete=false;
        }

      double nextPnL=p.realizedPnL+netPnl;
      double nextCommissionCashflow=p.totalCommissionCashflow+commission;
      double nextSwapCashflow=p.totalSwapCashflow+swap;
      double nextFeeCashflow=p.totalBrokerFeeCashflow+fee;
      double nextCommission=p.totalCommission+MathMax(0.0,-commission);
      bool totalsValid=MathIsValidNumber(nextPnL) &&
                       MathIsValidNumber(nextCommissionCashflow) &&
                       MathIsValidNumber(nextSwapCashflow) &&
                       MathIsValidNumber(nextFeeCashflow) &&
                       MathIsValidNumber(nextCommission);
      if(totalsValid)
        {
         p.realizedPnL=nextPnL;
         p.totalCommissionCashflow=nextCommissionCashflow;
         p.totalSwapCashflow=nextSwapCashflow;
         p.totalBrokerFeeCashflow=nextFeeCashflow;
         p.totalCommission=nextCommission;
        }
      else
        {
         p.cashflowsKnown=false;
         p.outcomeHistoryComplete=false;
        }
      p.cashflowsKnown=p.cashflowsKnown && cashflowsKnown &&
                       costValuesValid && pnlValid && totalsValid;

      if(closedVolume>0.0)
        {
         if(!MathIsValidNumber(p.remainingLots) || p.remainingLots<0.0 ||
            closedVolume>p.remainingLots+1e-8)
            p.outcomeHistoryComplete=false;
         double left=p.remainingLots-closedVolume;
         p.remainingLots=(MathIsValidNumber(left) ? MathMax(0.0,left) : 0.0);
        }
      if(!stillOpen && p.remainingLots>1e-8)
         p.outcomeHistoryComplete=false;

      // Swap and broker fees are not spread/slippage. Keep their signed values
      // separate, even for partial exits and manually resolved broker outcomes.
      RememberDeal(dealTicket);
      m_pending[i]=p;
      if(stillOpen) return true;
      Finalize(i,outcome,exitPrice,t);
      return true;
     }
   void Update(CTFContext* ctx){if(ctx==NULL||ctx.candles.Total()<3||ctx.candles.Timeframe()!=m_entryTF)return;CandleData bar=ctx.candles.GetCandle(1);if(bar.time<=0)return;for(int i=m_count-1;i>=0;i--){PendingSetup p=m_pending[i];bool buy=p.setup.type==ORDER_TYPE_BUY;int fshift=iBarShift(m_symbol,m_entryTF,p.fillTime,false);datetime creationBar=0;if(!p.filled){int shift=iBarShift(m_symbol,m_entryTF,p.setup.creation_time,false);creationBar=shift>=0?iTime(m_symbol,m_entryTF,shift):p.setup.creation_time;}if(!p.filled&&!m_liveExecution&&bar.time>creationBar){bool touched=buy?(bar.low<=p.entryRef):(bar.high>=p.entryRef);if(touched)SimFill(i,p.entryRef,bar.time);}if(!p.filled){p.barsElapsed++;p.lastBarTime=bar.time;m_pending[i]=p;if(p.barsElapsed>=m_maxBars)Finalize(i,"no_fill",bar.close,bar.time);continue;}if(fshift>=0){datetime fillBar=iTime(m_symbol,m_entryTF,fshift);if(bar.time<=fillBar)continue;}if(p.lastBarTime==bar.time)continue;p.barsElapsed++;p.lastBarTime=bar.time;if(buy){if(bar.high>p.mfePrice)p.mfePrice=bar.high;if(bar.low<p.maePrice)p.maePrice=bar.low;}else{if(bar.low<p.mfePrice)p.mfePrice=bar.low;if(bar.high>p.maePrice)p.maePrice=bar.high;}if(m_decayHalfLifeBars>0){p.decayBars=p.barsElapsed;p.confidenceDecayed=p.confidenceAtSignal*MathPow(0.5,(double)p.decayBars/m_decayHalfLifeBars);}m_pending[i]=p;if(p.barsElapsed>=m_maxBars)Finalize(i,"timeout",bar.close,bar.time);}}
   bool GetFillState(datetime creationTime,long id,bool &filled,double &fillPrice,datetime &fillTime,int &barsToFill){for(int i=0;i<m_count;i++)if(m_pending[i].setup.creation_time==creationTime&&(id<0||m_pending[i].decisionId==id)){filled=m_pending[i].filled;fillPrice=m_pending[i].entryFillPrice;fillTime=m_pending[i].fillTime;barsToFill=m_pending[i].barsToFill;return true;}return false;}
  };
#endif
//+------------------------------------------------------------------+
