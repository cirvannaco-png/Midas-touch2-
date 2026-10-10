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
   ulong                positionIdentifier; // stable POSITION_IDENTIFIER / DEAL_POSITION_ID
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

public:
   void              Init(CBrokerAdapter* broker,int maxOpenTrades,CProductionMonitor* monitor);
   void              SetMaxOpenTrades(int maxOpenTrades);
   bool              Submit(const TradeDecisionRecord &decision,double volume,bool useMarket,double maxEntryDeviation,ulong &ticketOut,int legIndex=0);
   bool              RestoreTrade(const TradeDecisionRecord &decision,double volume,ulong ticket,ENUM_TRADE_STATE state,double fillPrice=0.0,int legIndex=0);
   int               OpenCount();
   int               MaxOpenTrades() const { return m_maxOpen; }
   int               Total() { return ArraySize(m_trades); }
   void              Prune();
   bool              MarkFilledFromPending(ulong orderTicket,ulong positionIdentifier,double fillPrice=0.0,double fillVolume=0.0);
   bool              MarkCancelledOrder(ulong orderTicket);
   long              DecisionIdForTicket(ulong ticket);
   double            FillPriceForDecision(long decisionId);
   ENUM_TRADE_STATE  StateAt(int idx) { return m_trades[idx].fsm.State(); }
   ulong             TicketAt(int idx) { return m_trades[idx].fsm.Ticket(); }
   ulong             PositionIdentifierAt(int idx) { return m_trades[idx].positionIdentifier; }
   ulong             PositionTicketAt(int idx);
   bool              ArchiveClosedPosition(ulong positionIdentifier);
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
// Adaptive capacity changes only the admission ceiling for NEW orders.
// Existing trades are never closed solely because capacity contracts.
void COrderManager::SetMaxOpenTrades(int maxOpenTrades)
  {
   m_maxOpen=MathMax(1,maxOpenTrades);
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
      if(m_trades[i].fsm.Ticket()==ticket ||
         m_trades[i].positionIdentifier==ticket) return i;
   return -1;
  }
ulong COrderManager::PositionTicketAt(int idx)
  {
   if(idx<0 || idx>=ArraySize(m_trades))return 0;
   ulong identifier=m_trades[idx].positionIdentifier;
   if(identifier==0)return 0;
   for(int i=0;i<PositionsTotal();i++)
     {
      ulong currentTicket=PositionGetTicket(i);
      if(currentTicket==0)continue;
      if((ulong)PositionGetInteger(POSITION_IDENTIFIER)==identifier)
         return currentTicket;
     }
   return 0;
  }
//+------------------------------------------------------------------+
bool COrderManager::ArchiveClosedPosition(ulong positionIdentifier)
  {
   int idx=FindByTicket(positionIdentifier);
   if(idx<0 || positionIdentifier==0)return false;
   if(PositionTicketAt(idx)>0)return false; // Stable identifier still resolves to a live position.

   ENUM_TRADE_STATE state=m_trades[idx].fsm.State();
   if(state==TS_CLOSED)
      return m_trades[idx].fsm.Transition(TS_ARCHIVED);
   if(state==TS_FILLED || state==TS_PROTECTED || state==TS_PARTIAL || state==TS_RUNNER)
     {
      if(!m_trades[idx].fsm.Transition(TS_CLOSED))return false;
      return m_trades[idx].fsm.Transition(TS_ARCHIVED);
     }
   return state==TS_ARCHIVED;
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
   datetime now=TimeCurrent();
   ArrayResize(kept,ArraySize(m_trades));
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      ENUM_TRADE_STATE s=m_trades[i].fsm.State();
      bool terminal=(s==TS_ARCHIVED || s==TS_CANCELLED || s==TS_REJECTED);
      if(terminal)
        {
         // Retain terminal identity records briefly so a delayed DEAL_ADD
         // callback can still map the broker's stable position ID to its decision.
         datetime terminalAt=m_trades[i].fsm.LastChange();
         if(terminalAt>0 && now>=terminalAt && now-terminalAt<300)
            kept[n++]=m_trades[i];
         continue;
        }
      kept[n++]=m_trades[i];
     }
   ArrayResize(kept,n);
   ArrayResize(m_trades,n);
   for(int i=0;i<n;i++)m_trades[i]=kept[i];
  }
//+------------------------------------------------------------------+
bool COrderManager::MarkFilledFromPending(ulong orderTicket,ulong positionIdentifier,double fillPrice,double fillVolume)
  {
   if(orderTicket==0 || positionIdentifier==0)return false;
   // First fill of a pending request: replace its order ID with the stable
   // position ID in the state machine while retaining a separate identity field.
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      if(m_trades[i].fsm.State()!=TS_PENDING || m_trades[i].fsm.Ticket()!=orderTicket) continue;
      m_trades[i].positionIdentifier=positionIdentifier;
      m_trades[i].fsm.SetTicket(positionIdentifier);
      if(fillPrice>0.0) m_trades[i].fillPrice=fillPrice;
      if(fillVolume>0.0)m_trades[i].volume=fillVolume;
      bool filled=m_trades[i].fsm.Transition(TS_FILLED);
      ulong currentTicket=PositionTicketAt(i);
      if(currentTicket>0 && PositionSelectByTicket(currentTicket))
        {
         m_trades[i].volume=PositionGetDouble(POSITION_VOLUME);
         double actualEntry=PositionGetDouble(POSITION_PRICE_OPEN);
         if(actualEntry>0.0)m_trades[i].fillPrice=actualEntry;
        }
      if(filled && m_monitor!=NULL)
        {
         double totalMs=m_trades[i].fsm.TotalLatencyMs();
         if(totalMs>=0.0)m_monitor.NotifyTradeLatency(totalMs,0.0);
        }
      return filled;
     }

   // Additional partial fills for the same broker order arrive after the state
   // is already Filled. Refresh live aggregate volume/weighted average entry.
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      if(m_trades[i].positionIdentifier!=positionIdentifier)continue;
      ENUM_TRADE_STATE state=m_trades[i].fsm.State();
      if(state!=TS_FILLED && state!=TS_PROTECTED && state!=TS_PARTIAL && state!=TS_RUNNER)continue;
      ulong currentTicket=PositionTicketAt(i);
      if(currentTicket>0 && PositionSelectByTicket(currentTicket))
        {
         m_trades[i].volume=PositionGetDouble(POSITION_VOLUME);
         double actualEntry=PositionGetDouble(POSITION_PRICE_OPEN);
         if(actualEntry>0.0)m_trades[i].fillPrice=actualEntry;
        }
      else if(fillVolume>0.0)
         m_trades[i].volume+=fillVolume;
      return true;
     }
   return false;
  }
//+------------------------------------------------------------------+
bool COrderManager::MarkCancelledOrder(ulong orderTicket)
  {
   if(orderTicket==0)return false;
   for(int i=0;i<ArraySize(m_trades);i++)
     {
      if(m_trades[i].fsm.State()!=TS_PENDING || m_trades[i].fsm.Ticket()!=orderTicket)continue;
      bool cancelled=m_trades[i].fsm.Transition(TS_CANCELLED);
      if(cancelled)
         PrintFormat("MedisTouch OrderManager: unfilled order #%I64u (decision #%I64d) was cancelled/expired; slot released.",
                     orderTicket,m_trades[i].decision.decision_id);
      return cancelled;
     }
   return false;
  }
//+------------------------------------------------------------------+
long COrderManager::DecisionIdForTicket(ulong ticket)
  {
   int idx=FindByTicket(ticket);
   return idx>=0 ? m_trades[idx].decision.decision_id : -1;
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
      if(excludeTicket!=0 &&
         (m_trades[i].fsm.Ticket()==excludeTicket ||
          m_trades[i].positionIdentifier==excludeTicket)) continue;
      ENUM_TRADE_STATE s=m_trades[i].fsm.State();
      if(s==TS_PENDING || s==TS_WAITING) return true;
      if(s==TS_FILLED || s==TS_PROTECTED || s==TS_PARTIAL || s==TS_RUNNER)
        {
         if(m_trades[i].positionIdentifier>0 &&
            PositionTicketAt(i)>0) return true;
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

   // This order manager models one decision per position. Netting/exchange
   // accounts aggregate same-symbol deals into a single position identifier,
   // so simultaneous decisions would fight over one SL/TP and corrupt attribution.
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      if(OpenCount()>0)
        {
         PrintFormat("MedisTouch OrderManager: new %s exposure blocked; one managed decision at a time is required on netting/exchange accounts.",decision.symbol);
         return false;
        }
      for(int p=0;p<PositionsTotal();p++)
        {
         ulong existingTicket=PositionGetTicket(p);
         if(existingTicket==0 || !PositionSelectByTicket(existingTicket))continue;
         if(PositionGetString(POSITION_SYMBOL)==decision.symbol)
           {
            PrintFormat("MedisTouch OrderManager: new %s exposure blocked because a netting position already exists for that symbol.",decision.symbol);
            return false;
           }
        }
      for(int o=0;o<OrdersTotal();o++)
        {
         ulong existingOrder=OrderGetTicket(o);
         if(existingOrder==0)continue;
         if(OrderGetString(ORDER_SYMBOL)==decision.symbol)
           {
            PrintFormat("MedisTouch OrderManager: new %s exposure blocked because an active order already exists for that symbol on a netting/exchange account.",decision.symbol);
            return false;
           }
        }
     }

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
      bool fillConfirmed=false;
      if(decision.setup.type==ORDER_TYPE_BUY)
         ok=m_broker.MarketBuy(decision.symbol,volume,sl,tp,ticket,fillPrice,fillConfirmed,comment);
      else
         ok=m_broker.MarketSell(decision.symbol,volume,sl,tp,ticket,fillPrice,fillConfirmed,comment);

      if(ok)
        {
         m_trades[idx].fsm.SetTicket(ticket);
         if(fillConfirmed)
           {
            m_trades[idx].positionIdentifier=ticket;
            m_trades[idx].fillPrice=fillPrice;
            m_trades[idx].fsm.Transition(TS_FILLED);
            double totalMs=m_trades[idx].fsm.TotalLatencyMs();
            if(m_monitor!=NULL && totalMs>=0.0)m_monitor.NotifyTradeLatency(totalMs,m_broker.LastLatencyMs());
           }
         else
            PrintFormat("MedisTouch OrderManager: decision #%I64d accepted as order #%I64u; awaiting confirmed deal event.",decision.decision_id,ticket);
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
   if(ok)ticketOut=ticket;
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
   m_trades[idx].legIndex=legIndex;
   m_trades[idx].fsm.Start(decision.decision_id);
   m_trades[idx].fsm.BindMonitor(m_monitor);
   ulong storedIdentity=ticket;
   if(state!=TS_PENDING && state!=TS_WAITING && PositionSelectByTicket(ticket))
     {
      m_trades[idx].positionIdentifier=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      if(m_trades[idx].positionIdentifier>0)storedIdentity=m_trades[idx].positionIdentifier;
     }
   m_trades[idx].fsm.SetTicket(storedIdentity);
   m_trades[idx].fsm.ForceState(state);
   return true;
  }
#endif
//+------------------------------------------------------------------+
