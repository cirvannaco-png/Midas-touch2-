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
   double               volume;
   double               fillPrice;
   ulong                positionIdentifier; // stable POSITION_IDENTIFIER, separate from POSITION_TICKET
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

public:
   void              Init(CBrokerAdapter* broker,int maxOpenTrades,CProductionMonitor* monitor);
   bool              Submit(const TradeDecisionRecord &decision,double volume,bool useMarket,double maxEntryDeviation,ulong &ticketOut,int legIndex=0);
   bool              RestoreTrade(const TradeDecisionRecord &decision,double volume,ulong ticket,ENUM_TRADE_STATE state,double fillPrice=0.0,int legIndex=0);
   int               OpenCount();
   int               Total() { return ArraySize(m_trades); }
   void              Prune();
   bool              MarkFilledFromPending(ulong orderTicket,ulong positionIdentifier,double fillPrice=0.0);
   long              DecisionIdForTicket(ulong ticket);
   double            FillPriceForDecision(long decisionId);
   ENUM_TRADE_STATE  StateAt(int idx) { return m_trades[idx].fsm.State(); }
   ulong             TicketAt(int idx);
   TradeDecisionRecord DecisionAt(int idx) { return m_trades[idx].decision; }
   double            VolumeAt(int idx) { return m_trades[idx].volume; }
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
bool COrderManager::MarkFilledFromPending(ulong orderTicket,ulong positionIdentifier,double fillPrice)
  {
   if(positionIdentifier==0) return false;
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      if(m_trades[i].fsm.State()!=TS_PENDING || m_trades[i].fsm.Ticket()!=orderTicket) continue;
      // DEAL_POSITION_ID is the stable POSITION_IDENTIFIER, not necessarily
      // the current POSITION_TICKET required by PositionSelectByTicket().
      ulong liveTicket=ResolveLivePositionTicket(positionIdentifier);
      m_trades[i].positionIdentifier=positionIdentifier;
      // If the position has already closed before it can be selected, retain
      // the identifier to preserve the order/deal audit trail. TicketAt()
      // will refresh this to the live position ticket whenever one exists.
      m_trades[i].fsm.SetTicket(liveTicket>0 ? liveTicket : positionIdentifier);
      if(fillPrice>0.0) m_trades[i].fillPrice=fillPrice;
      bool filled=m_trades[i].fsm.Transition(TS_FILLED);
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
   if(ticket==0) return -1;
   for(int i=0;i<ArraySize(m_trades);i++)
      if(m_trades[i].fsm.Ticket()==ticket || m_trades[i].positionIdentifier==ticket)
         return m_trades[i].decision.decision_id;
   return -1;
  }
//+------------------------------------------------------------------+
double COrderManager::FillPriceForDecision(long decisionId)
  {
   for(int i=0;i<ArraySize(m_trades);i++)
      if(m_trades[i].decision.decision_id==decisionId)
         return FillPriceAt(i);
   return 0.0;
  }
bool COrderManager::HasLiveTradeForDecision(long decisionId,ulong excludeTicket)
  {
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      if(m_trades[i].decision.decision_id!=decisionId) continue;
      if(excludeTicket!=0 && m_trades[i].fsm.Ticket()==excludeTicket) continue;
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
bool COrderManager::Submit(const TradeDecisionRecord &decision,double volume,bool useMarket,double maxEntryDeviation,ulong &ticketOut,int legIndex)
  {
   ticketOut=0;
   if(decision.action!=POLICY_EXECUTE_ONLY && decision.action!=POLICY_EXECUTE_AND_SIGNAL) return false;
   if(volume<=0) return false;
   if(OpenCount()>=m_maxOpen) return false;
   if(legIndex<0) return false;
   if(FindByDecisionAndLeg(decision.decision_id,legIndex)>=0) return false;

   double entry=ResolveExecutionEntry(decision.setup);
   int brokerDeviationPoints=20; // Fixed fallback when the ATR band is disabled.
   if(useMarket && maxEntryDeviation>0.0)
     {
      MqlTick tick;
      if(!SymbolInfoTick(decision.symbol,tick)) return false;
      double marketPrice=(decision.setup.type==ORDER_TYPE_BUY)?tick.ask:tick.bid;
      if(!MathIsValidNumber(marketPrice) || marketPrice<=0.0 || !MathIsValidNumber(entry) || entry<=0.0) return false;
      if(MathAbs(marketPrice-entry)>maxEntryDeviation) return false;

      // Keep the actual broker fill inside the same worst-case band used
      // by sizing/geometry validation. Convert remaining price room into
      // broker points and round DOWN so rounding cannot widen the band.
      double point=SymbolInfoDouble(decision.symbol,SYMBOL_POINT);
      if(!MathIsValidNumber(point) || point<=0.0) return false;
      double worstAllowedFill=(decision.setup.type==ORDER_TYPE_BUY)?entry+maxEntryDeviation:entry-maxEntryDeviation;
      double maxPriceSlippage=(decision.setup.type==ORDER_TYPE_BUY)?worstAllowedFill-marketPrice:marketPrice-worstAllowedFill;
      if(!MathIsValidNumber(maxPriceSlippage) || maxPriceSlippage<0.0) return false;
      brokerDeviationPoints=(int)MathMax(0.0,MathFloor(maxPriceSlippage/point));
     }

   int idx=ArraySize(m_trades);
   ArrayResize(m_trades,idx+1);
   m_trades[idx].decision=decision;
   m_trades[idx].volume=volume;
   m_trades[idx].fillPrice=0.0;
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
         m_trades[idx].fsm.SetTicket(ticket);
         if(fillPrice>0.0 && PositionSelectByTicket(ticket))
           {
            m_trades[idx].positionIdentifier=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
            // Only a confirmed deal and live position ticket may advance the
            // manager to FILLED. The stable identifier is retained separately
            // for transaction/outcome mapping if the broker later rekeys ticket.
            m_trades[idx].fsm.Transition(TS_FILLED);
            m_trades[idx].fillPrice=fillPrice;
            double totalMs=m_trades[idx].fsm.TotalLatencyMs();
            if(m_monitor!=NULL && totalMs>=0.0) m_monitor.NotifyTradeLatency(totalMs,m_broker.LastLatencyMs());
           }
         else
            PrintFormat("MedisTouch OrderManager: decision #%I64d accepted without a confirmed live-position ticket; request remains pending under ticket %I64u.",decision.decision_id,ticket);
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
