//+------------------------------------------------------------------+
//|                                        Recovery/RecoveryEngine.mqh |
//+------------------------------------------------------------------+
#ifndef RECOVERYENGINE_MQH
#define RECOVERYENGINE_MQH

#include "../Decision/DecisionStore.mqh"
#include "../Execution/OrderManager.mqh"
#include "../Execution/TradeStateMachine.mqh"

class CRecoveryEngine
  {
private:
   CDecisionStore*   m_store;
   COrderManager*    m_orders;
   ulong             m_magic;
   string            m_symbol;

   bool              ParseDecisionId(string comment,long &idOut);
   ENUM_TRADE_STATE  InferPositionState(double submittedVolume,double currentVolume,
                                        double entryPrice,double currentSL,bool isBuy);

public:
   void Init(CDecisionStore* store,COrderManager* orders,ulong magic,string symbol);
   int Recover();
  };
//+------------------------------------------------------------------+
void CRecoveryEngine::Init(CDecisionStore* store,COrderManager* orders,ulong magic,string symbol)
  {
   m_store=store; m_orders=orders; m_magic=magic; m_symbol=symbol;
  }
//+------------------------------------------------------------------+
bool CRecoveryEngine::ParseDecisionId(string comment,long &idOut)
  {
   idOut=0;
   if(StringSubstr(comment,0,3)!="MT#") return false;
   string numPart=StringSubstr(comment,3);
   if(StringLen(numPart)==0) return false;
   idOut=(long)StringToInteger(numPart);
   return idOut>0;
  }
//+------------------------------------------------------------------+
ENUM_TRADE_STATE CRecoveryEngine::InferPositionState(double submittedVolume,double currentVolume,double entryPrice,double currentSL,bool isBuy)
  {
   bool partialTaken=(submittedVolume>0 && currentVolume<submittedVolume-0.0000001);
   bool atOrPastBreakEven=isBuy ? (currentSL>=entryPrice-0.0000001) : (currentSL<=entryPrice+0.0000001);
   if(currentSL==0) atOrPastBreakEven=false;
   if(partialTaken) return TS_RUNNER;
   if(atOrPastBreakEven) return TS_PROTECTED;
   return TS_FILLED;
  }
//+------------------------------------------------------------------+
int CRecoveryEngine::Recover()
  {
   int restored=0;
   ExecutionRecord execs[];
   int execCount=m_store.LoadAllExecutions(execs);

   for(int i=0;i<PositionsTotal();i++)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)!=m_symbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=m_magic) continue;

      long decisionId;
      if(!ParseDecisionId(PositionGetString(POSITION_COMMENT),decisionId)) continue;
      TradeDecisionRecord dec;
      if(!m_store.FindById(decisionId,dec))
        {
         PrintFormat("MedisTouch Recovery: position #%d references decision #%d, not found in the decision store — skipping.",ticket,decisionId);
         continue;
        }

      double currentVolume=PositionGetDouble(POSITION_VOLUME);
      double submittedVolume=currentVolume;
      for(int e=0;e<execCount;e++)
         if(execs[e].decision_id==decisionId) { submittedVolume=execs[e].volume; break; }

      bool isBuy=(dec.setup.type==ORDER_TYPE_BUY);
      double actualEntry=PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL=PositionGetDouble(POSITION_SL);
      ENUM_TRADE_STATE state=InferPositionState(submittedVolume,currentVolume,actualEntry,currentSL,isBuy);

      if(m_orders.RestoreTrade(dec,currentVolume,ticket,state,actualEntry))
        {
         restored++;
         PrintFormat("MedisTouch Recovery: restored decision #%d as ticket #%d in state %s at broker entry %.5f.",
                     decisionId,ticket,TradeStateToString(state),actualEntry);
        }
     }

   for(int i=0;i<OrdersTotal();i++)
     {
      ulong ticket=OrderGetTicket(i);
      if(ticket==0 || !OrderSelect(ticket)) continue;
      if(OrderGetString(ORDER_SYMBOL)!=m_symbol) continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC)!=m_magic) continue;

      long decisionId;
      if(!ParseDecisionId(OrderGetString(ORDER_COMMENT),decisionId)) continue;
      TradeDecisionRecord dec;
      if(!m_store.FindById(decisionId,dec)) continue;
      double vol=OrderGetDouble(ORDER_VOLUME_CURRENT);
      if(m_orders.RestoreTrade(dec,vol,ticket,TS_PENDING,0.0))
        {
         restored++;
         PrintFormat("MedisTouch Recovery: restored decision #%d as pending order #%d.",decisionId,ticket);
        }
     }
   return restored;
  }
#endif
//+------------------------------------------------------------------+
