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
   double               fillPrice;           // volume-weighted authoritative fill price
   double               filledVolume;        // cumulative authoritative entry-deal volume
   double               fillNotional;        // sum(fill price * fill quantity)
   int                  legIndex;
   ulong                positionIdentifier;  // stable POSITION_IDENTIFIER / DEAL_POSITION_ID
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
   bool                IsBrokerVolumeValid(string symbol,double volume);
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
   bool              MarkFilledFromPending(ulong orderTicket,ulong positionIdentifier,ulong positionTicket,double fillPrice=0.0,double fillVolume=0.0,ulong dealTicket=0);
   bool              BindPositionIdentity(ulong knownTicket,ulong positionIdentifier,ulong positionTicket);
   ulong             PositionTicketAt(int idx);
   long              DecisionIdForPositionIdentifier(ulong positionIdentifier);
   bool              MarkPositionExitByIdentifier(ulong positionIdentifier,bool positionStillOpen);
   long              DecisionIdForTicket(ulong ticket);
   double            FillPriceForDecision(long decisionId);
   ENUM_TRADE_STATE  StateAt(int idx) { return m_trades[idx].fsm.State(); }
   ulong             TicketAt(int idx) { return m_trades[idx].fsm.Ticket(); }
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
bool COrderManager::MarkFilledFromPending(ulong orderTicket,ulong positionIdentifier,ulong positionTicket,double fillPrice,double fillVolume,ulong dealTicket)
  {
   if(positionIdentifier==0) return false;
   if(FillDealSeen(dealTicket)) return true;
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      bool orderMatch=(orderTicket>0 && m_trades[i].fsm.Ticket()==orderTicket);
      bool positionMatch=(m_trades[i].positionIdentifier==positionIdentifier);
      bool ticketMatch=(positionTicket>0 && m_trades[i].fsm.Ticket()==positionTicket);
      if(!orderMatch && !positionMatch && !ticketMatch) continue;

      ulong existingIdentifier=m_trades[i].positionIdentifier;
      if(existingIdentifier>0 && existingIdentifier!=positionIdentifier)
        {
         PrintFormat("MedisTouch OrderManager: refusing conflicting position identity for decision #%I64d (existing=%I64u observed=%I64u).",
                     m_trades[i].decision.decision_id,existingIdentifier,positionIdentifier);
         return false;
        }
      if(fillVolume>0.0)
        {
         if(!MathIsValidNumber(fillVolume) || !MathIsValidNumber(fillPrice) || fillVolume<=0.0 || fillPrice<=0.0)
            return false;
         double nextFilled=m_trades[i].filledVolume+fillVolume;
         double tolerance=MathMax(1e-8,m_trades[i].volume*1e-6);
         if(!MathIsValidNumber(nextFilled) || nextFilled>m_trades[i].volume+tolerance)
           {
            PrintFormat("MedisTouch OrderManager: cumulative fill %.8f exceeds requested volume %.8f for decision #%I64d; reconciliation required.",
                        nextFilled,m_trades[i].volume,m_trades[i].decision.decision_id);
            return false;
           }
         double nextNotional=m_trades[i].fillNotional+fillPrice*fillVolume;
         if(!MathIsValidNumber(nextNotional) || nextNotional<=0.0) return false;
         m_trades[i].filledVolume=nextFilled;
         m_trades[i].fillNotional=nextNotional;
         m_trades[i].fillPrice=nextNotional/nextFilled;
         RememberFillDeal(dealTicket);
        }
      else if(fillPrice>0.0 && m_trades[i].filledVolume<=0.0)
         m_trades[i].fillPrice=fillPrice;

      m_trades[i].positionIdentifier=positionIdentifier;
      ulong liveTicket=ResolveLivePositionTicket(positionIdentifier);
      ENUM_TRADE_STATE state=m_trades[i].fsm.State();
      if(liveTicket>0)
         m_trades[i].fsm.SetTicket(liveTicket);
      else if(positionTicket>0)
         m_trades[i].fsm.SetTicket(positionTicket);
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
// Bind the stable broker history identity to the current selectable position ticket.
bool COrderManager::BindPositionIdentity(ulong knownTicket,ulong positionIdentifier,ulong positionTicket)
  {
   if(positionIdentifier==0 || positionTicket==0) return false;
   int idx=FindByTicket(knownTicket);
   if(idx<0) idx=FindByTicket(positionIdentifier);
   if(idx<0) idx=FindByTicket(positionTicket);
   if(idx<0) return false;
   if(m_trades[idx].positionIdentifier!=0 &&
      m_trades[idx].positionIdentifier!=positionIdentifier)
     {
      PrintFormat("MedisTouch OrderManager: refused conflicting position identity for decision #%I64d.",m_trades[idx].decision.decision_id);
      return false;
     }
   m_trades[idx].positionIdentifier=positionIdentifier;
   m_trades[idx].fsm.SetTicket(positionTicket);
   return true;
  }
//+------------------------------------------------------------------+
ulong COrderManager::PositionTicketAt(int idx)
  {
   if(idx<0 || idx>=ArraySize(m_trades)) return 0;
   // Until a stable deal/position identity is bound, do not guess that a
   // broker order ticket or history identifier is a selectable position.
   ulong identifier=m_trades[idx].positionIdentifier;
   if(identifier==0) return 0;

   ulong ticket=m_trades[idx].fsm.Ticket();
   if(ticket>0 && PositionSelectByTicket(ticket))
     {
      if(PositionGetString(POSITION_SYMBOL)==m_trades[idx].decision.symbol &&
         (ulong)PositionGetInteger(POSITION_IDENTIFIER)==identifier)
         return ticket;
     }

   // POSITION_TICKET may change over the lifetime of a live position. Resolve
   // the current ticket via the stable POSITION_IDENTIFIER and repair the FSM.
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong actualTicket=PositionGetTicket(i);
      if(actualTicket==0 || !PositionSelectByTicket(actualTicket)) continue;
      if(PositionGetString(POSITION_SYMBOL)!=m_trades[idx].decision.symbol) continue;
      if((ulong)PositionGetInteger(POSITION_IDENTIFIER)!=identifier) continue;
      m_trades[idx].fsm.SetTicket(actualTicket);
      return actualTicket;
     }
   return 0;
  }
//+------------------------------------------------------------------+
long COrderManager::DecisionIdForPositionIdentifier(ulong positionIdentifier)
  {
   if(positionIdentifier==0) return -1;
   for(int i=0;i<ArraySize(m_trades);i++)
      if(m_trades[i].positionIdentifier==positionIdentifier)
         return m_trades[i].decision.decision_id;
   return -1;
  }
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
bool COrderManager::MarkPositionExitByIdentifier(ulong positionIdentifier,bool positionStillOpen)
  {
   if(positionIdentifier==0) return false;
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      if(m_trades[i].positionIdentifier!=positionIdentifier) continue;
      if(positionStillOpen) return true;

      ENUM_TRADE_STATE state=m_trades[i].fsm.State();
      if(state==TS_ARCHIVED) return true;
      if(state!=TS_CLOSED && !m_trades[i].fsm.Transition(TS_CLOSED))
        {
         PrintFormat("MedisTouch OrderManager: could not close decision #%I64d after broker position #%I64u disappeared.",
                     m_trades[i].decision.decision_id,positionIdentifier);
         return false;
        }
      if(m_trades[i].fsm.State()==TS_CLOSED)
         return m_trades[i].fsm.Transition(TS_ARCHIVED);
      return true;
     }
   return false;
  }
//+------------------------------------------------------------------+
long COrderManager::DecisionIdForTicket(ulong ticket)
  {
   for(int i=0;i<ArraySize(m_trades);i++)
      if(m_trades[i].fsm.Ticket()==ticket) return m_trades[i].decision.decision_id;
   return -1;
  }
//+------------------------------------------------------------------+
double COrderManager::FillPriceForDecision(long decisionId)
  {
   double authoritativeNotional=0.0,authoritativeVolume=0.0;
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      if(m_trades[i].decision.decision_id!=decisionId || m_trades[i].filledVolume<=0.0) continue;
      authoritativeNotional+=m_trades[i].fillNotional;
      authoritativeVolume+=m_trades[i].filledVolume;
     }
   // Never combine observed deal prices with estimates for legs without an
   // authoritative fill record.
   if(authoritativeVolume>0.0)
      return authoritativeNotional/authoritativeVolume;

   double estimatedNotional=0.0,estimatedVolume=0.0;
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      if(m_trades[i].decision.decision_id!=decisionId || m_trades[i].fillPrice<=0.0 || m_trades[i].volume<=0.0) continue;
      estimatedNotional+=m_trades[i].fillPrice*m_trades[i].volume;
      estimatedVolume+=m_trades[i].volume;
     }
   return estimatedVolume>0.0 ? estimatedNotional/estimatedVolume : 0.0;
  }
bool COrderManager::HasLiveTradeForDecision(long decisionId,ulong excludeTicket)
  {
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      if(m_trades[i].decision.decision_id!=decisionId) continue;
      if(excludeTicket!=0 && (m_trades[i].fsm.Ticket()==excludeTicket || m_trades[i].positionIdentifier==excludeTicket)) continue;
      ENUM_TRADE_STATE s=m_trades[i].fsm.State();
      if(s==TS_PENDING || s==TS_WAITING) return true;
      if(s==TS_FILLED || s==TS_PROTECTED || s==TS_PARTIAL || s==TS_RUNNER)
        {
         ulong ticket=PositionTicketAt(i);
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
bool COrderManager::IsBrokerVolumeValid(string symbol,double volume)
  {
   if(symbol=="" || !MathIsValidNumber(volume) || volume<=0.0) return false;

   double minLot=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   double maxLot=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
   double lotStep=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(!MathIsValidNumber(minLot) || !MathIsValidNumber(maxLot) ||
      !MathIsValidNumber(lotStep) || minLot<=0.0 || maxLot<minLot || lotStep<=0.0)
      return false;
   if(volume<minLot || volume>maxLot) return false;

   // Validate against the broker's minimum-anchored step grid. Reject rather
   // than silently round a caller's requested volume and change its risk.
   double steps=(volume-minLot)/lotStep;
   if(!MathIsValidNumber(steps) || steps<0.0) return false;
   double alignedVolume=minLot+MathRound(steps)*lotStep;
   double tolerance=MathMax(1e-8,lotStep*1e-6);
   if(MathAbs(volume-alignedVolume)>tolerance) return false;
   return true;
  }
//+------------------------------------------------------------------+
bool COrderManager::Submit(const TradeDecisionRecord &decision,double volume,bool useMarket,double maxEntryDeviation,double maxRiskCash,ulong &ticketOut,int legIndex)
  {
   ticketOut=0;
   if(decision.action!=POLICY_EXECUTE_ONLY && decision.action!=POLICY_EXECUTE_AND_SIGNAL) return false;
   if(decision.decision_id<=0 ||
      (decision.setup.type!=ORDER_TYPE_BUY && decision.setup.type!=ORDER_TYPE_SELL) ||
      !MathIsValidNumber(maxEntryDeviation) || !MathIsValidNumber(maxRiskCash) || maxRiskCash<=0.0)
      return false;
   if(!IsBrokerVolumeValid(decision.symbol,volume))
     {
      PrintFormat("MedisTouch OrderManager: reject decision #%I64d — volume %.8f violates broker min/max/step for %s.",
                  decision.decision_id,volume,decision.symbol);
      return false;
     }
   if(OpenCount()>=m_maxOpen) return false;
   if(legIndex<0) return false;
   if(FindByDecisionAndLeg(decision.decision_id,legIndex)>=0) return false;

   double entry=ResolveExecutionEntry(decision.setup);
   if(!MathIsValidNumber(entry) || entry<=0.0 ||
      !MathIsValidNumber(decision.setup.stop_loss) || decision.setup.stop_loss<=0.0)
      return false;

   MqlTick tick;
   int brokerDeviationPoints=20;
   double riskEntry=entry;
   if(useMarket)
     {
      if(!SymbolInfoTick(decision.symbol,tick)) return false;
      double marketPrice=(decision.setup.type==ORDER_TYPE_BUY)?tick.ask:tick.bid;
      double point=SymbolInfoDouble(decision.symbol,SYMBOL_POINT);
      if(!MathIsValidNumber(marketPrice) || marketPrice<=0.0 ||
         !MathIsValidNumber(point) || point<=0.0)
         return false;
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
         riskEntry=(decision.setup.type==ORDER_TYPE_BUY)
                   ? marketPrice+20.0*point : marketPrice-20.0*point;
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
   double riskTolerance=MathMax(0.000001,maxRiskCash*1e-8);
   if(!MathIsValidNumber(estimatedRisk) || estimatedRisk>maxRiskCash+riskTolerance)
     {
      PrintFormat("MedisTouch OrderManager: rejecting decision #%I64d — worst-case stop risk %.2f exceeds configured budget %.2f.",
                  decision.decision_id,estimatedRisk,maxRiskCash);
      return false;
     }

   int idx=ArraySize(m_trades);
   if(ArrayResize(m_trades,idx+1)!=idx+1) return false;
   m_trades[idx].decision=decision;
   m_trades[idx].volume=volume;
   m_trades[idx].fillPrice=0.0;
   m_trades[idx].filledVolume=0.0;
   m_trades[idx].fillNotional=0.0;
   m_trades[idx].legIndex=legIndex;
   m_trades[idx].positionIdentifier=0;
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
         ok=m_broker.MarketBuy(decision.symbol,volume,sl,tp,ticket,fillPrice,comment,brokerDeviationPoints);
      else
         ok=m_broker.MarketSell(decision.symbol,volume,sl,tp,ticket,fillPrice,comment,brokerDeviationPoints);
      if(ok)
        {
         // BrokerAdapter returns the stable history identifier; resolve the
         // current selectable ticket separately and keep unresolved exposure reserved.
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
            m_trades[idx].fsm.SetTicket(ticket);
            PrintFormat("MedisTouch OrderManager: decision #%I64d accepted; position identity %I64u awaits live-ticket resolution.",
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
   m_trades[idx].legIndex=legIndex;
   m_trades[idx].positionIdentifier=0;
   m_trades[idx].fsm.Start(decision.decision_id);
   m_trades[idx].fsm.BindMonitor(m_monitor);
   m_trades[idx].fsm.SetTicket(ticket);
   m_trades[idx].fsm.ForceState(state);
   return true;
  }
#endif
//+------------------------------------------------------------------+
