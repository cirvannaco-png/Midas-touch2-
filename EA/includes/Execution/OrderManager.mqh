//+------------------------------------------------------------------+
//|                                        Execution/OrderManager.mqh |
//+------------------------------------------------------------------+
#ifndef ORDERMANAGER_MQH
#define ORDERMANAGER_MQH

#include "../Decision/TradeDecision.mqh"
#include "../Monitoring/ProductionMonitor.mqh"
#include "TradeStateMachine.mqh"
#include "BrokerAdapter.mqh"

struct ManagedTrade
  {
   TradeDecisionRecord  decision;
   CTradeStateMachine   fsm;
   double               volume;              // requested volume
   double               fillPrice;           // volume-weighted average actual fill
   double               filledVolume;        // cumulative authoritative entry fills
   double               fillNotional;        // sum(fill price * fill quantity)
   ulong                positionIdentifier;  // stable POSITION_IDENTIFIER / DEAL_POSITION_ID
   int                  legIndex;
  };

class COrderManager
  {
private:
   CBrokerAdapter*     m_broker;
   ManagedTrade        m_trades[];
   int                 m_maxOpen;
   CProductionMonitor* m_monitor;
   int                 FindByDecisionAndLeg(long id,int legIndex);
   int                 FindByTicket(ulong ticket);
   ulong               ResolveLivePositionTicket(ulong positionIdentifier);
   bool                FillDealSeen(ulong dealTicket);
   void                RememberFillDeal(ulong dealTicket);
   ulong               m_seenFillDeals[];

public:
   void              Init(CBrokerAdapter* broker,int maxOpenTrades,CProductionMonitor* monitor);
   bool              Submit(const TradeDecisionRecord &decision,double volume,bool useMarket,double maxEntryDeviation,double maxRiskCash,ulong &ticketOut,int legIndex=0);
   bool              RestoreTrade(const TradeDecisionRecord &decision,double volume,ulong ticket,ENUM_TRADE_STATE state,double fillPrice=0.0,int legIndex=0);
   int               OpenCount();
   int               Total() { return ArraySize(m_trades); }
   void              Prune();
   bool              CancelPendingAt(int idx);
   bool              MarkFilledFromPending(ulong orderTicket,ulong positionIdentifier,double fillPrice=0.0,double fillVolume=0.0,ulong dealTicket=0);
   long              DecisionIdForTicket(ulong ticket);
   double            FillPriceForDecision(long decisionId);
   ENUM_TRADE_STATE  StateAt(int idx) { return m_trades[idx].fsm.State(); }
   ulong             TicketAt(int idx);
   TradeDecisionRecord DecisionAt(int idx) { return m_trades[idx].decision; }
   double            VolumeAt(int idx) { return (idx>=0 && idx<ArraySize(m_trades)) ? m_trades[idx].volume : 0.0; }
   double            FilledVolumeAt(int idx) { return (idx>=0 && idx<ArraySize(m_trades)) ? m_trades[idx].filledVolume : 0.0; }
   bool              TransitionAt(int idx,ENUM_TRADE_STATE to) { return m_trades[idx].fsm.Transition(to); }
   bool              HasLiveTradeForDecision(long decisionId,ulong excludeTicket=0);
   int               LegIndexForTicket(ulong ticket);
   double            FillPriceAt(int idx)
     {
      if(m_trades[idx].fillPrice>0.0) return m_trades[idx].fillPrice;
      bool isBuy=(m_trades[idx].decision.setup.type==ORDER_TYPE_BUY);
      return isBuy ? m_trades[idx].decision.setup.entry_top : m_trades[idx].decision.setup.entry_bottom;
     }
  };
//+------------------------------------------------------------------+
void COrderManager::Init(CBrokerAdapter* broker,int maxOpenTrades,CProductionMonitor* monitor)
  {
   m_broker=broker;
   m_maxOpen=MathMax(1,maxOpenTrades);
   m_monitor=monitor;
   ArrayResize(m_trades,0);
   ArrayResize(m_seenFillDeals,0);
  }
//+------------------------------------------------------------------+
int COrderManager::FindByDecisionAndLeg(long id,int legIndex)
  {
   for(int i=0;i<ArraySize(m_trades);i++)
      if(m_trades[i].decision.decision_id==id && m_trades[i].legIndex==legIndex) return i;
   return -1;
  }
int COrderManager::FindByTicket(ulong ticket)
  {
   if(ticket==0) return -1;
   for(int i=0;i<ArraySize(m_trades);i++)
      if(m_trades[i].fsm.Ticket()==ticket || m_trades[i].positionIdentifier==ticket) return i;
   return -1;
}
//+------------------------------------------------------------------+
// DEAL_POSITION_ID is stable; PositionSelectByTicket requires POSITION_TICKET.
ulong COrderManager::ResolveLivePositionTicket(ulong positionIdentifier)
  {
   if(positionIdentifier==0) return 0;
   for(int i=0;i<PositionsTotal();i++)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if((ulong)PositionGetInteger(POSITION_IDENTIFIER)==positionIdentifier)
         return ticket;
     }
   return 0;
}
//+------------------------------------------------------------------+
ulong COrderManager::TicketAt(int idx)
  {
   if(idx<0 || idx>=ArraySize(m_trades)) return 0;
   ulong identifier=m_trades[idx].positionIdentifier;
   if(identifier>0)
     {
      ulong liveTicket=ResolveLivePositionTicket(identifier);
      if(liveTicket>0)
        {
         if(m_trades[idx].fsm.Ticket()!=liveTicket)
            m_trades[idx].fsm.SetTicket(liveTicket);
         return liveTicket;
        }
     }
   return m_trades[idx].fsm.Ticket();
}
//+------------------------------------------------------------------+
bool COrderManager::FillDealSeen(ulong dealTicket)
  {
   if(dealTicket==0) return false;
   for(int i=0;i<ArraySize(m_seenFillDeals);i++)
      if(m_seenFillDeals[i]==dealTicket) return true;
   return false;
}
//+------------------------------------------------------------------+
void COrderManager::RememberFillDeal(ulong dealTicket)
  {
   if(dealTicket==0 || FillDealSeen(dealTicket)) return;
   int n=ArraySize(m_seenFillDeals);
   if(ArrayResize(m_seenFillDeals,n+1)!=n+1) return;
   m_seenFillDeals[n]=dealTicket;
}
//+------------------------------------------------------------------+
int COrderManager::OpenCount()
  {
   int c=0;
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      ENUM_TRADE_STATE s=m_trades[i].fsm.State();
      if(s==TS_PENDING || s==TS_FILLED || s==TS_PROTECTED || s==TS_PARTIAL || s==TS_RUNNER) c++;
     }
   return c;
  }
//+------------------------------------------------------------------+
bool COrderManager::CancelPendingAt(int idx)
  {
   if(idx<0 || idx>=ArraySize(m_trades)) return false;
   ENUM_TRADE_STATE state=m_trades[idx].fsm.State();
   if(state!=TS_PENDING && state!=TS_WAITING) return false;
   ulong ticket=m_trades[idx].fsm.Ticket();
   if(ticket==0 || !m_broker.CancelOrder(ticket)) return false;
   bool transitioned=m_trades[idx].fsm.Transition(TS_CANCELLED);
   if(transitioned) PrintFormat("MedisTouch OrderManager: pending order %I64u cancelled by chart control.",ticket);
   return transitioned;
  }
//+------------------------------------------------------------------+
void COrderManager::Prune()
  {
   ManagedTrade kept[];
   int n=0;
   ArrayResize(kept,ArraySize(m_trades));
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      ENUM_TRADE_STATE s=m_trades[i].fsm.State();
      if(s==TS_ARCHIVED || s==TS_CANCELLED || s==TS_REJECTED) continue;
      kept[n++]=m_trades[i];
     }
   ArrayResize(kept,n);
   ArrayResize(m_trades,n);
   for(int i=0;i<n;i++) m_trades[i]=kept[i];
  }
//+------------------------------------------------------------------+
bool COrderManager::MarkFilledFromPending(ulong orderTicket,ulong positionIdentifier,double fillPrice,double fillVolume,ulong dealTicket)
  {
   if(positionIdentifier==0) return false;
   if(FillDealSeen(dealTicket)) return true;
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      bool orderMatch=(orderTicket>0 && m_trades[i].fsm.Ticket()==orderTicket);
      bool positionMatch=(m_trades[i].positionIdentifier==positionIdentifier);
      if(!orderMatch && !positionMatch) continue;

      ulong existingIdentifier=m_trades[i].positionIdentifier;
      if(existingIdentifier>0 && existingIdentifier!=positionIdentifier)
        {
         PrintFormat("MedisTouch OrderManager: refusing conflicting position identity for decision #%I64d (existing=%I64u observed=%I64u).",
                     m_trades[i].decision.decision_id,existingIdentifier,positionIdentifier);
         return false;
        }
      if(fillVolume>0.0)
        {
         if(!MathIsValidNumber(fillVolume) || !MathIsValidNumber(fillPrice) || fillPrice<=0.0) return false;
         double nextFilled=m_trades[i].filledVolume+fillVolume;
         double tolerance=MathMax(1e-8,m_trades[i].volume*1e-6);
         if(nextFilled>m_trades[i].volume+tolerance)
           {
            PrintFormat("MedisTouch OrderManager: cumulative fill %.8f exceeds requested volume %.8f for decision #%I64d; reconciliation required.",
                        nextFilled,m_trades[i].volume,m_trades[i].decision.decision_id);
            return false;
           }
         m_trades[i].filledVolume=nextFilled;
         m_trades[i].fillNotional+=fillPrice*fillVolume;
         m_trades[i].fillPrice=m_trades[i].fillNotional/m_trades[i].filledVolume;
         RememberFillDeal(dealTicket);
        }
      else if(fillPrice>0.0 && m_trades[i].filledVolume<=0.0)
         m_trades[i].fillPrice=fillPrice;

      m_trades[i].positionIdentifier=positionIdentifier;
      ulong liveTicket=ResolveLivePositionTicket(positionIdentifier);
      ENUM_TRADE_STATE state=m_trades[i].fsm.State();
      if(liveTicket>0)
         m_trades[i].fsm.SetTicket(liveTicket);
      else if(state==TS_PENDING || state==TS_WAITING)
         m_trades[i].fsm.SetTicket(positionIdentifier);

      bool filled=false;
      if(state==TS_PENDING)
         filled=m_trades[i].fsm.Transition(TS_FILLED);
      else if(state==TS_WAITING)
        {
         bool pending=m_trades[i].fsm.Transition(TS_PENDING);
         if(pending) filled=m_trades[i].fsm.Transition(TS_FILLED);
        }
      else if(state==TS_FILLED || state==TS_PROTECTED || state==TS_PARTIAL || state==TS_RUNNER)
         filled=true;

      if(filled && m_monitor!=NULL)
        {
         double totalMs=m_trades[i].fsm.TotalLatencyMs();
         if(totalMs>=0.0) m_monitor.NotifyTradeLatency(totalMs,0.0);
        }
      return filled;
     }
   return false;
  }
//+------------------------------------------------------------------+
long COrderManager::DecisionIdForTicket(ulong ticket)
  {
   int idx=FindByTicket(ticket);
   return idx<0 ? -1 : m_trades[idx].decision.decision_id;
}
//+------------------------------------------------------------------+
double COrderManager::FillPriceForDecision(long decisionId)
  {
   double notional=0.0,volume=0.0;
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      if(m_trades[i].decision.decision_id!=decisionId) continue;
      if(m_trades[i].filledVolume>0.0)
        {
         notional+=m_trades[i].fillNotional;
         volume+=m_trades[i].filledVolume;
        }
      else if(m_trades[i].fillPrice>0.0 && m_trades[i].volume>0.0)
        {
         notional+=m_trades[i].fillPrice*m_trades[i].volume;
         volume+=m_trades[i].volume;
        }
     }
   return volume>0.0 ? notional/volume : 0.0;
}
bool COrderManager::HasLiveTradeForDecision(long decisionId,ulong excludeTicket)
  {
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      if(m_trades[i].decision.decision_id!=decisionId) continue;
      if(excludeTicket!=0 && (m_trades[i].fsm.Ticket()==excludeTicket || m_trades[i].positionIdentifier==excludeTicket))
         continue;
      ENUM_TRADE_STATE s=m_trades[i].fsm.State();
      if(s==TS_PENDING || s==TS_WAITING) return true;
      if(s==TS_FILLED || s==TS_PROTECTED || s==TS_PARTIAL || s==TS_RUNNER)
        {
         ulong ticket=TicketAt(i);
         if(ticket!=0 && PositionSelectByTicket(ticket)) return true;
        }
     }
   return false;
  }
int COrderManager::LegIndexForTicket(ulong ticket)
  {
   int idx=FindByTicket(ticket);
   return idx<0 ? 0 : m_trades[idx].legIndex;
  }
//+------------------------------------------------------------------+
bool COrderManager::Submit(const TradeDecisionRecord &decision,double volume,bool useMarket,double maxEntryDeviation,double maxRiskCash,ulong &ticketOut,int legIndex)
  {
   ticketOut=0;
   if(decision.action!=POLICY_EXECUTE_ONLY && decision.action!=POLICY_EXECUTE_AND_SIGNAL) return false;
   if(!MathIsValidNumber(volume) || volume<=0.0 || !MathIsValidNumber(maxRiskCash) || maxRiskCash<=0.0) return false;
   if(OpenCount()>=m_maxOpen) return false;
   if(legIndex<0) return false;
   if(FindByDecisionAndLeg(decision.decision_id,legIndex)>=0) return false;

   double minVolume=SymbolInfoDouble(decision.symbol,SYMBOL_VOLUME_MIN);
   double maxVolume=SymbolInfoDouble(decision.symbol,SYMBOL_VOLUME_MAX);
   double volumeStep=SymbolInfoDouble(decision.symbol,SYMBOL_VOLUME_STEP);
   if(!MathIsValidNumber(minVolume) || !MathIsValidNumber(maxVolume) || !MathIsValidNumber(volumeStep) ||
      minVolume<=0.0 || maxVolume<minVolume || volumeStep<=0.0 ||
      volume<minVolume-1e-9 || volume>maxVolume+1e-9)
     {
      PrintFormat("MedisTouch OrderManager: rejecting decision #%I64d — requested volume %.8f violates broker volume bounds.",
                  decision.decision_id,volume);
      return false;
     }
   double stepCount=(volume-minVolume)/volumeStep;
   if(!MathIsValidNumber(stepCount) || MathAbs(stepCount-MathRound(stepCount))>1e-5)
     {
      PrintFormat("MedisTouch OrderManager: rejecting decision #%I64d — volume %.8f is not aligned to broker step %.8f.",
                  decision.decision_id,volume,volumeStep);
      return false;
     }

   double entry=ResolveExecutionEntry(decision.setup);
   if(!MathIsValidNumber(entry) || entry<=0.0 || !MathIsValidNumber(decision.setup.stop_loss) ||
      decision.setup.stop_loss<=0.0) return false;

   MqlTick tick;
   int brokerDeviationPoints=20;
   double riskEntry=entry;
   if(useMarket)
     {
      if(!SymbolInfoTick(decision.symbol,tick)) return false;
      double marketPrice=(decision.setup.type==ORDER_TYPE_BUY)?tick.ask:tick.bid;
      double point=SymbolInfoDouble(decision.symbol,SYMBOL_POINT);
      if(!MathIsValidNumber(marketPrice) || marketPrice<=0.0 || !MathIsValidNumber(point) || point<=0.0) return false;
      if(maxEntryDeviation>0.0)
        {
         bool adverse=(decision.setup.type==ORDER_TYPE_BUY)
                      ? marketPrice>entry+maxEntryDeviation : marketPrice<entry-maxEntryDeviation;
         if(adverse) return false;
         double worstAllowedFill=(decision.setup.type==ORDER_TYPE_BUY)
                                 ? entry+maxEntryDeviation : entry-maxEntryDeviation;
         double remainingPriceRoom=(decision.setup.type==ORDER_TYPE_BUY)
                                   ? worstAllowedFill-marketPrice : marketPrice-worstAllowedFill;
         if(!MathIsValidNumber(remainingPriceRoom) || remainingPriceRoom<0.0) return false;
         brokerDeviationPoints=(int)MathMax(0.0,MathFloor(remainingPriceRoom/point));
         riskEntry=worstAllowedFill;
        }
      else
         riskEntry=(decision.setup.type==ORDER_TYPE_BUY) ? marketPrice+20.0*point : marketPrice-20.0*point;
     }

   ENUM_ORDER_TYPE orderType=(decision.setup.type==ORDER_TYPE_BUY)?ORDER_TYPE_BUY:ORDER_TYPE_SELL;
   double estimatedAtStop=0.0;
   if(!OrderCalcProfit(orderType,decision.symbol,volume,riskEntry,decision.setup.stop_loss,estimatedAtStop) ||
      !MathIsValidNumber(estimatedAtStop) || estimatedAtStop>=0.0)
     {
      PrintFormat("MedisTouch OrderManager: rejecting decision #%I64d — cannot verify positive stop-loss risk.",
                  decision.decision_id);
      return false;
     }
   double estimatedRisk=-estimatedAtStop;
   double riskTolerance=MathMax(0.01,maxRiskCash*1e-6);
   if(!MathIsValidNumber(estimatedRisk) || estimatedRisk>maxRiskCash+riskTolerance)
     {
      PrintFormat("MedisTouch OrderManager: rejecting decision #%I64d — worst-case stop risk %.2f exceeds configured budget %.2f.",
                  decision.decision_id,estimatedRisk,maxRiskCash);
      return false;
     }

   int idx=ArraySize(m_trades);
   ArrayResize(m_trades,idx+1);
   m_trades[idx].decision=decision;
   m_trades[idx].volume=volume;
   m_trades[idx].fillPrice=0.0;
   m_trades[idx].filledVolume=0.0;
   m_trades[idx].fillNotional=0.0;
   m_trades[idx].positionIdentifier=0;
   m_trades[idx].legIndex=legIndex;
   m_trades[idx].fsm.Start(decision.decision_id);
   m_trades[idx].fsm.BindMonitor(m_monitor);
   m_trades[idx].fsm.Transition(TS_VALIDATED);

   double sl=decision.setup.stop_loss;
   double tp=decision.setup.final_tp;
   ulong ticket=0;
   double fillPrice=0.0;
   bool ok=false;
   if(useMarket)
     {
      m_trades[idx].fsm.Transition(TS_PENDING);
      string comment="MT#"+IntegerToString(decision.decision_id)+(legIndex>0?":L"+IntegerToString(legIndex):"");
      if(decision.setup.type==ORDER_TYPE_BUY)
        {
         ok=m_broker.MarketBuy(decision.symbol,volume,sl,tp,ticket,fillPrice,comment,brokerDeviationPoints);
        }
      else
        {
         ok=m_broker.MarketSell(decision.symbol,volume,sl,tp,ticket,fillPrice,comment,brokerDeviationPoints);
        }
      if(ok)
        {
         // BrokerAdapter returns DEAL_POSITION_ID, not necessarily POSITION_TICKET.
         m_trades[idx].positionIdentifier=ticket;
         m_trades[idx].fillPrice=fillPrice;
         ulong liveTicket=ResolveLivePositionTicket(ticket);
         if(liveTicket>0)
           {
            m_trades[idx].fsm.SetTicket(liveTicket);
            m_trades[idx].fsm.Transition(TS_FILLED);
            double totalMs=m_trades[idx].fsm.TotalLatencyMs();
            if(m_monitor!=NULL && totalMs>=0.0) m_monitor.NotifyTradeLatency(totalMs,m_broker.LastLatencyMs());
           }
         else
           {
            // Keep accepted-but-unresolved exposure counted as pending until
            // the deal event or explicit reconciliation confirms the position.
            m_trades[idx].fsm.SetTicket(ticket);
            PrintFormat("MedisTouch OrderManager: decision #%I64d accepted; stable position ID %I64u awaits live-ticket resolution.",
                        decision.decision_id,ticket);
           }
        }
      else m_trades[idx].fsm.Transition(TS_REJECTED);
     }
   else
     {
      m_trades[idx].fsm.Transition(TS_WAITING);
      m_trades[idx].fsm.Transition(TS_PENDING);
      ENUM_ORDER_TYPE limitType=(decision.setup.type==ORDER_TYPE_BUY)?ORDER_TYPE_BUY_LIMIT:ORDER_TYPE_SELL_LIMIT;
      string comment="MT#"+IntegerToString(decision.decision_id)+(legIndex>0?":L"+IntegerToString(legIndex):"");
      ok=m_broker.PlaceLimit(decision.symbol,limitType,volume,entry,sl,tp,ticket,comment);
      if(ok) m_trades[idx].fsm.SetTicket(ticket);
      else m_trades[idx].fsm.Transition(TS_REJECTED);
     }
   if(ok) ticketOut=ticket;
   return ok;
  }
//+------------------------------------------------------------------+
bool COrderManager::RestoreTrade(const TradeDecisionRecord &decision,double volume,ulong ticket,ENUM_TRADE_STATE state,double fillPrice,int legIndex)
  {
   if(volume<=0 || ticket==0) return false;
   if(FindByTicket(ticket)>=0) return false;
   if(legIndex<0) return false;
   int idx=ArraySize(m_trades);
   ArrayResize(m_trades,idx+1);
   m_trades[idx].decision=decision;
   m_trades[idx].volume=volume;
   m_trades[idx].fillPrice=fillPrice;
   m_trades[idx].filledVolume=0.0;
   m_trades[idx].fillNotional=0.0;
   m_trades[idx].positionIdentifier=0;
   if(state!=TS_PENDING && PositionSelectByTicket(ticket))
      m_trades[idx].positionIdentifier=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
   m_trades[idx].legIndex=legIndex;
   m_trades[idx].fsm.Start(decision.decision_id);
   m_trades[idx].fsm.BindMonitor(m_monitor);
   m_trades[idx].fsm.SetTicket(ticket);
   m_trades[idx].fsm.ForceState(state);
   return true;
  }
#endif
//+------------------------------------------------------------------+
