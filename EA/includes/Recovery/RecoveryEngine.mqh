//+------------------------------------------------------------------+
//| Recovery/RecoveryEngine.mqh                                    |
//+------------------------------------------------------------------+
#ifndef RECOVERYENGINE_MQH
#define RECOVERYENGINE_MQH
#include "../Decision/DecisionStore.mqh"
#include "../Execution/OrderManager.mqh"
#include "../Execution/TradeStateMachine.mqh"
#include "../Trading/OutcomeTrackerLive.mqh"
class CRecoveryEngine
  {
private:
   CDecisionStore* m_store; COrderManager* m_orders; COutcomeTrackerLive* m_tracker; ulong m_magic; string m_symbol;
   bool ParseDecisionId(string comment,long &idOut);
   bool ParseTradeIdentity(string comment,long &idOut,int &legOut);
   ENUM_TRADE_STATE InferPositionState(double submittedVolume,double currentVolume,double entryPrice,double currentSL,bool isBuy);
public:
   void Init(CDecisionStore* store,COrderManager* orders,ulong magic,string symbol,COutcomeTrackerLive* tracker=NULL); int Recover();
  };
void CRecoveryEngine::Init(CDecisionStore* store,COrderManager* orders,ulong magic,string symbol,COutcomeTrackerLive* tracker){m_store=store;m_orders=orders;m_magic=magic;m_symbol=symbol;m_tracker=(tracker!=NULL?tracker:g_activeOutcomeTracker);}
bool CRecoveryEngine::ParseTradeIdentity(string comment,long &idOut,int &legOut)
  {
   idOut=0;legOut=0;
   if(StringSubstr(comment,0,3)!="MT#") return false;
   string payload=StringSubstr(comment,3);
   int sep=StringFind(payload,":L");
   if(sep>=0)
     {
      string legPart=StringSubstr(payload,sep+2);
      payload=StringSubstr(payload,0,sep);
      legOut=(int)StringToInteger(legPart);
      if(legOut<0) return false;
     }
   if(StringLen(payload)==0) return false;
   idOut=(long)StringToInteger(payload);
   return idOut>0;
  }
bool CRecoveryEngine::ParseDecisionId(string comment,long &idOut)
  {
   int leg=0;
   return ParseTradeIdentity(comment,idOut,leg);
  }
ENUM_TRADE_STATE CRecoveryEngine::InferPositionState(double submittedVolume,double currentVolume,double entryPrice,double currentSL,bool isBuy){bool partialTaken=(submittedVolume>0&&currentVolume<submittedVolume-0.0000001);bool atOrPastBreakEven=isBuy?(currentSL>=entryPrice-0.0000001):(currentSL<=entryPrice+0.0000001);if(currentSL==0)atOrPastBreakEven=false;if(partialTaken)return TS_RUNNER;if(atOrPastBreakEven)return TS_PROTECTED;return TS_FILLED;}
int CRecoveryEngine::Recover()
  {
   int restored=0;
   ExecutionRecord execs[];
   int execCount=m_store.LoadAllExecutions(execs);

   for(int i=0;i<PositionsTotal();i++)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0||!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)!=m_symbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=m_magic) continue;

      long decisionId;
      int legIndex=0;
      if(!ParseTradeIdentity(PositionGetString(POSITION_COMMENT),decisionId,legIndex)) continue;

      TradeDecisionRecord dec;
      if(!m_store.FindById(decisionId,dec))
        {
         PrintFormat("MedisTouch Recovery: position #%I64u references decision #%I64d not found in store — skipping.",ticket,decisionId);
         continue;
        }

      double currentVolume=PositionGetDouble(POSITION_VOLUME);
      double submittedVolume=currentVolume;
      double restoredTarget=0.0;
      for(int e=0;e<execCount;e++)
        {
         if(execs[e].decision_id==decisionId && execs[e].leg_index==legIndex)
           {
            submittedVolume=execs[e].volume;
            restoredTarget=execs[e].target;
            break;
           }
        }

      TradeDecisionRecord restoredDecision=dec;
      if(restoredTarget>0.0)
         restoredDecision.setup.final_tp=restoredTarget;

      bool isBuy=restoredDecision.setup.type==ORDER_TYPE_BUY;
      double actualEntry=PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL=PositionGetDouble(POSITION_SL);
      ENUM_TRADE_STATE state=InferPositionState(submittedVolume,currentVolume,actualEntry,currentSL,isBuy);

      if(m_orders.RestoreTrade(restoredDecision,currentVolume,ticket,state,actualEntry,legIndex))
        {
         restored++;
         if(m_tracker!=NULL)
            m_tracker.RestoreExecuted(restoredDecision.setup,decisionId,actualEntry,(datetime)PositionGetInteger(POSITION_TIME),currentVolume);
         PrintFormat("MedisTouch Recovery: restored decision #%I64d leg %d as ticket #%I64u in state %s at broker entry %.5f.",decisionId,legIndex,ticket,TradeStateToString(state),actualEntry);
        }
     }

   for(int i=0;i<OrdersTotal();i++)
     {
      ulong ticket=OrderGetTicket(i);
      if(ticket==0||!OrderSelect(ticket)) continue;
      if(OrderGetString(ORDER_SYMBOL)!=m_symbol) continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC)!=m_magic) continue;

      long decisionId;
      int legIndex=0;
      if(!ParseTradeIdentity(OrderGetString(ORDER_COMMENT),decisionId,legIndex)) continue;

      TradeDecisionRecord dec;
      if(!m_store.FindById(decisionId,dec)) continue;

      double vol=OrderGetDouble(ORDER_VOLUME_CURRENT);
      double restoredTarget=0.0;
      for(int e=0;e<execCount;e++)
        {
         if(execs[e].decision_id==decisionId && execs[e].leg_index==legIndex)
           {
            restoredTarget=execs[e].target;
            break;
           }
        }

      TradeDecisionRecord restoredDecision=dec;
      if(restoredTarget>0.0)
         restoredDecision.setup.final_tp=restoredTarget;

      if(m_orders.RestoreTrade(restoredDecision,vol,ticket,TS_PENDING,0.0,legIndex))
        {
         restored++;
         PrintFormat("MedisTouch Recovery: restored decision #%I64d leg %d as pending order #%I64u.",decisionId,legIndex,ticket);
        }
     }

   return restored;
  }

#endif
//+------------------------------------------------------------------+
