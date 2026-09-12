//+------------------------------------------------------------------+
//|                                        Execution/OrderManager.mqh |
//+------------------------------------------------------------------+
#ifndef ORDERMANAGER_MQH
#define ORDERMANAGER_MQH

#include "../Decision/TradeDecision.mqh"
#include "TradeStateMachine.mqh"
#include "BrokerAdapter.mqh"

struct ManagedTrade
  {
   TradeDecisionRecord  decision;
   CTradeStateMachine   fsm;
   double               volume;
   double               fillPrice;
  };

class COrderManager
  {
private:
   CBrokerAdapter*     m_broker;
   ManagedTrade        m_trades[];
   int                 m_maxOpen;
   CProductionMonitor* m_monitor;
   int                 FindByDecisionId(long id);

public:
   void              Init(CBrokerAdapter* broker,int maxOpenTrades,CProductionMonitor* monitor);
   bool              Submit(const TradeDecisionRecord &decision,double volume,bool useMarket,double maxEntryDeviation,ulong &ticketOut);
   bool              RestoreTrade(const TradeDecisionRecord &decision,double volume,ulong ticket,ENUM_TRADE_STATE state,double fillPrice=0.0);
   int               OpenCount();
   int               Total() { return ArraySize(m_trades); }
   void              Prune();
   bool              MarkFilledFromPending(ulong orderTicket,ulong positionTicket,double fillPrice=0.0);
   long              DecisionIdForTicket(ulong ticket);
   double            FillPriceForDecision(long decisionId);
   ENUM_TRADE_STATE  StateAt(int idx) { return m_trades[idx].fsm.State(); }
   ulong             TicketAt(int idx) { return m_trades[idx].fsm.Ticket(); }
   TradeDecisionRecord DecisionAt(int idx) { return m_trades[idx].decision; }
   double            VolumeAt(int idx) { return m_trades[idx].volume; }
   bool              TransitionAt(int idx,ENUM_TRADE_STATE to) { return m_trades[idx].fsm.Transition(to); }
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
int COrderManager::FindByDecisionId(long id)
  {
   for(int i=0;i<ArraySize(m_trades);i++) if(m_trades[i].decision.decision_id==id) return i;
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
bool COrderManager::MarkFilledFromPending(ulong orderTicket,ulong positionTicket,double fillPrice)
  {
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      if(m_trades[i].fsm.State()!=TS_PENDING || m_trades[i].fsm.Ticket()!=orderTicket) continue;
      m_trades[i].fsm.SetTicket(positionTicket);
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
   for(int i=0;i<ArraySize(m_trades);i++)
      if(m_trades[i].fsm.Ticket()==ticket) return m_trades[i].decision.decision_id;
   return -1;
  }
//+------------------------------------------------------------------+
double COrderManager::FillPriceForDecision(long decisionId)
  {
   int idx=FindByDecisionId(decisionId);
   if(idx<0) return 0.0;
   return FillPriceAt(idx);
  }
//+------------------------------------------------------------------+
bool COrderManager::Submit(const TradeDecisionRecord &decision,double volume,bool useMarket,double maxEntryDeviation,ulong &ticketOut)
  {
   ticketOut=0;
   if(decision.action!=POLICY_EXECUTE_ONLY && decision.action!=POLICY_EXECUTE_AND_SIGNAL) return false;
   if(volume<=0) return false;
   if(OpenCount()>=m_maxOpen) return false;
   if(FindByDecisionId(decision.decision_id)>=0) return false;

   double entry=ResolveExecutionEntry(decision.setup);
   if(useMarket && maxEntryDeviation>0.0)
     {
      MqlTick tick;
      if(!SymbolInfoTick(decision.symbol,tick)) return false;
      double marketPrice=(decision.setup.type==ORDER_TYPE_BUY)?tick.ask:tick.bid;
      if(MathAbs(marketPrice-entry)>maxEntryDeviation) return false;
     }

   int idx=ArraySize(m_trades);
   ArrayResize(m_trades,idx+1);
   m_trades[idx].decision=decision;
   m_trades[idx].volume=volume;
   m_trades[idx].fillPrice=0.0;
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
      if(decision.setup.type==ORDER_TYPE_BUY)
         ok=m_broker.MarketBuy(decision.symbol,volume,sl,tp,ticket,fillPrice,"MT#"+IntegerToString(decision.decision_id));
      else
         ok=m_broker.MarketSell(decision.symbol,volume,sl,tp,ticket,fillPrice,"MT#"+IntegerToString(decision.decision_id));
      if(ok)
        {
         m_trades[idx].fsm.SetTicket(ticket);
         m_trades[idx].fsm.Transition(TS_FILLED);
         m_trades[idx].fillPrice=fillPrice;
         double totalMs=m_trades[idx].fsm.TotalLatencyMs();
         if(m_monitor!=NULL && totalMs>=0.0) m_monitor.NotifyTradeLatency(totalMs,m_broker.LastLatencyMs());
        }
      else m_trades[idx].fsm.Transition(TS_REJECTED);
     }
   else
     {
      m_trades[idx].fsm.Transition(TS_WAITING);
      m_trades[idx].fsm.Transition(TS_PENDING);
      ENUM_ORDER_TYPE limitType=(decision.setup.type==ORDER_TYPE_BUY)?ORDER_TYPE_BUY_LIMIT:ORDER_TYPE_SELL_LIMIT;
      ok=m_broker.PlaceLimit(decision.symbol,limitType,volume,entry,sl,tp,ticket,"MT#"+IntegerToString(decision.decision_id));
      if(ok) m_trades[idx].fsm.SetTicket(ticket);
      else m_trades[idx].fsm.Transition(TS_REJECTED);
     }
   if(ok) ticketOut=ticket;
   return ok;
  }
//+------------------------------------------------------------------+
bool COrderManager::RestoreTrade(const TradeDecisionRecord &decision,double volume,ulong ticket,ENUM_TRADE_STATE state,double fillPrice)
  {
   if(FindByDecisionId(decision.decision_id)>=0) return false;
   int idx=ArraySize(m_trades);
   ArrayResize(m_trades,idx+1);
   m_trades[idx].decision=decision;
   m_trades[idx].volume=volume;
   m_trades[idx].fillPrice=fillPrice;
   m_trades[idx].fsm.Start(decision.decision_id);
   m_trades[idx].fsm.BindMonitor(m_monitor);
   m_trades[idx].fsm.SetTicket(ticket);
   m_trades[idx].fsm.ForceState(state);
   return true;
  }
#endif
//+------------------------------------------------------------------+
