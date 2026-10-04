//+------------------------------------------------------------------+
//| Execution/PositionManager.mqh                                    |
//+------------------------------------------------------------------+
#ifndef POSITIONMANAGER_MQH
#define POSITIONMANAGER_MQH

#include "OrderManager.mqh"
#include "BrokerAdapter.mqh"
#include "DynamicStopEngine.mqh"
#include "DynamicStopInputs.mqh"
#include "../Monitoring/SLModificationAudit.mqh"
#include "../Structure/SwingDetector.mqh"

class CPositionManager
  {
private:
   COrderManager*        m_orders;
   CBrokerAdapter*       m_broker;
   CSwingDetector*       m_structureSwings;
   CSLModificationAudit  m_audit;
   CDynamicStopEngine    m_dynamicStop;
   double                m_partialAtR;
   double                m_partialFraction;
   int                   m_minModifyIntervalSec;
   ulong                 m_lastModifyTickets[];
   datetime              m_lastModifyTimes[];
   bool                  m_tp1Done[];
   bool                  m_tp2Done[];

   int    TargetStateIndex(ulong ticket);
   bool   TargetReached(bool isBuy,double price,double target) const;
   bool   CloseTargetSlice(int idx,ulong ticket,bool isBuy,double target,double fraction);
   void   SyncTargetStage(int idx,ulong ticket);

   double CurrentExitPrice(string symbol,bool isBuy);
   double RMultiple(const TradeDecisionRecord &dec,double entry,double price);
   bool   CanModifyNow(ulong ticket);
   void   RecordModification(ulong ticket);
   double ConfirmedStructuralAnchor(bool isBuy);

public:
   void Init(COrderManager* orders,CBrokerAdapter* broker,
             double breakEvenAtR,double partialAtR,double partialFraction,double trailAtrMult,
             int maxSpreadPoints=0,double minATR=0.0,double maxATR=0.0,
             int minModifyIntervalSec=5,CSwingDetector* structureSwings=NULL);
   void OnTick(double currentAtr);
  };

void CPositionManager::Init(COrderManager* orders,CBrokerAdapter* broker,
                            double breakEvenAtR,double partialAtR,double partialFraction,double trailAtrMult,
                            int maxSpreadPoints,double minATR,double maxATR,int minModifyIntervalSec,
                            CSwingDetector* structureSwings)
  {
   m_orders=orders;
   m_broker=broker;
   m_structureSwings=structureSwings;
   m_partialAtR=partialAtR;
   m_partialFraction=partialFraction;
   m_minModifyIntervalSec=MathMax(0,minModifyIntervalSec);
   ArrayResize(m_lastModifyTickets,0);
   ArrayResize(m_lastModifyTimes,0);
   ArrayResize(m_tp1Done,0);
   ArrayResize(m_tp2Done,0);
   m_audit.Init();

   DynamicStopConfig cfg;
   cfg.SetDefaults();
   cfg.activateAtR=InpDynamicStopActivateAtR;
   cfg.breakevenAtR=InpDynamicStopBreakevenAtR;
   cfg.atrMultiplier=InpDynamicStopATRMult;
   cfg.minImprovementPts=InpDynamicStopMinImprovementPoints;
   cfg.maxSpreadPoints=InpDynamicStopMaxSpreadPoints;
   cfg.minATR=InpDynamicStopMinATR;
   cfg.maxATR=InpDynamicStopMaxATR;
   cfg.useStructuralAnchor=InpDynamicStopUseStructuralAnchor;
   cfg.structuralBufferATR=InpDynamicStopStructuralBufferATR;
   m_minModifyIntervalSec=MathMax(0,InpDynamicStopModifyIntervalSec);
   m_dynamicStop.Configure(cfg);
  }

double CPositionManager::CurrentExitPrice(string symbol,bool isBuy)
  {
   MqlTick tick;
   if(!SymbolInfoTick(symbol,tick)) return 0.0;
   return isBuy ? tick.bid : tick.ask;
  }

double CPositionManager::RMultiple(const TradeDecisionRecord &dec,double entry,double price)
  {
   bool isBuy=(dec.setup.type==ORDER_TYPE_BUY);
   double riskDist=MathAbs(entry-dec.setup.stop_loss);
   if(riskDist<=0.0) return 0.0;
   double moveInFavor=isBuy ? price-entry : entry-price;
   return moveInFavor/riskDist;
  }

bool CPositionManager::CanModifyNow(ulong ticket)
  {
   if(m_minModifyIntervalSec<=0) return true;
   for(int i=0;i<ArraySize(m_lastModifyTickets);i++)
      if(m_lastModifyTickets[i]==ticket)
         return (TimeCurrent()-m_lastModifyTimes[i])>=m_minModifyIntervalSec;
   return true;
  }

void CPositionManager::RecordModification(ulong ticket)
  {
   for(int i=0;i<ArraySize(m_lastModifyTickets);i++)
      if(m_lastModifyTickets[i]==ticket)
        { m_lastModifyTimes[i]=TimeCurrent(); return; }
   int n=ArraySize(m_lastModifyTickets);
   ArrayResize(m_lastModifyTickets,n+1);
   ArrayResize(m_lastModifyTimes,n+1);
   m_lastModifyTickets[n]=ticket;
   m_lastModifyTimes[n]=TimeCurrent();
  }

int CPositionManager::TargetStateIndex(ulong ticket)
  {
   for(int i=0;i<ArraySize(m_lastModifyTickets);i++)
      if(m_lastModifyTickets[i]==ticket)
        {
         if(ArraySize(m_tp1Done)<ArraySize(m_lastModifyTickets)) ArrayResize(m_tp1Done,ArraySize(m_lastModifyTickets));
         if(ArraySize(m_tp2Done)<ArraySize(m_lastModifyTickets)) ArrayResize(m_tp2Done,ArraySize(m_lastModifyTickets));
         return i;
        }

   int n=ArraySize(m_lastModifyTickets);
   ArrayResize(m_lastModifyTickets,n+1);
   ArrayResize(m_lastModifyTimes,n+1);
   ArrayResize(m_tp1Done,n+1);
   ArrayResize(m_tp2Done,n+1);
   m_lastModifyTickets[n]=ticket;
   m_lastModifyTimes[n]=0;
   m_tp1Done[n]=false;
   m_tp2Done[n]=false;
   return n;
  }

bool CPositionManager::TargetReached(bool isBuy,double price,double target) const
  {
   if(price<=0.0 || target<=0.0) return false;
   return isBuy ? price>=target : price<=target;
  }

void CPositionManager::SyncTargetStage(int idx,ulong ticket)
  {
   if(idx<0 || ticket==0 || !PositionSelectByTicket(ticket)) return;
   int state=TargetStateIndex(ticket);
   if(state<0) return;

   TradeDecisionRecord dec=m_orders.DecisionAt(idx);
   double original=m_orders.VolumeAt(idx);
   double current=PositionGetDouble(POSITION_VOLUME);
   if(original<=0.0 || current<=0.0) return;

   double minVol=SymbolInfoDouble(dec.symbol,SYMBOL_VOLUME_MIN);
   double step=SymbolInfoDouble(dec.symbol,SYMBOL_VOLUME_STEP);
   if(minVol<=0.0) return;

   double first=MathMin(original-minVol,original*MathMin(1.0,MathMax(0.0,InpTP1PartialFraction)));
   if(step>0.0) first=MathFloor(first/step)*step;

   if(first>=minVol && current <= original-first+(step>0.0?step*0.5:0.00000001))
      m_tp1Done[state]=true;

   if(m_tp1Done[state])
     {
      double afterFirst=original-first;
      double second=MathMin(afterFirst-minVol,original*MathMin(1.0,MathMax(0.0,InpTP2PartialFraction)));
      if(step>0.0) second=MathFloor(second/step)*step;
      if(second>=minVol && current <= afterFirst-second+(step>0.0?step*0.5:0.00000001))
         m_tp2Done[state]=true;
     }
  }

bool CPositionManager::CloseTargetSlice(int idx,ulong ticket,bool isBuy,double target,double fraction)
  {
   if(idx<0 || ticket==0 || fraction<=0.0 || m_broker==NULL || m_orders==NULL) return false;
   TradeDecisionRecord dec=m_orders.DecisionAt(idx);
   double price=CurrentExitPrice(dec.symbol,isBuy);
   if(!TargetReached(isBuy,price,target)) return false;
   if(!PositionSelectByTicket(ticket)) return false;

   double currentVolume=PositionGetDouble(POSITION_VOLUME);
   double originalVolume=m_orders.VolumeAt(idx);
   double minVolume=SymbolInfoDouble(dec.symbol,SYMBOL_VOLUME_MIN);
   double step=SymbolInfoDouble(dec.symbol,SYMBOL_VOLUME_STEP);
   if(currentVolume<=0.0 || originalVolume<=0.0 || minVolume<=0.0) return false;

   double closeVolume=MathMin(currentVolume-minVolume,originalVolume*MathMin(1.0,MathMax(0.0,fraction)));
   if(step>0.0) closeVolume=MathFloor(closeVolume/step)*step;
   if(closeVolume<minVolume || closeVolume>=currentVolume) return false;

   if(m_broker.ClosePartial(ticket,closeVolume))
     {
      m_orders.TransitionAt(idx,TS_PARTIAL);
      m_orders.TransitionAt(idx,TS_RUNNER);
      return true;
     }
   return false;
  }

// Return the newest CONFIRMED swing on the opposite side of the position.
// CSwingDetector only exposes swings after its left/right strength window
// has completed, so this is market structure derived from the actual
// terminal candle feed rather than a synthetic price level.
// BUY  -> most recent confirmed swing low.
// SELL -> most recent confirmed swing high.
// The DynamicStopEngine remains the final geometry/safety gate.
double CPositionManager::ConfirmedStructuralAnchor(bool isBuy)
  {
   if(m_structureSwings==NULL) return 0.0;
   if(isBuy)
     {
      if(m_structureSwings.LowCount()<=0) return 0.0;
      SwingPoint low=m_structureSwings.GetLow(0);
      if(low.time<=0 || low.price<=0.0 || low.is_high) return 0.0;
      return low.price;
     }
   if(m_structureSwings.HighCount()<=0) return 0.0;
   SwingPoint high=m_structureSwings.GetHigh(0);
   if(high.time<=0 || high.price<=0.0 || !high.is_high) return 0.0;
   return high.price;
  }

void CPositionManager::OnTick(double currentAtr)
  {
   for(int i=0;i<m_orders.Total();i++)
     {
      ENUM_TRADE_STATE state=m_orders.StateAt(i);
      if(state!=TS_FILLED && state!=TS_PROTECTED && state!=TS_PARTIAL && state!=TS_RUNNER)
         continue;

      ulong ticket=m_orders.TicketAt(i);
      if(!PositionSelectByTicket(ticket))
        {
         m_orders.TransitionAt(i,TS_CLOSED);
         m_orders.TransitionAt(i,TS_ARCHIVED);
         continue;
        }

      TradeDecisionRecord dec=m_orders.DecisionAt(i);
      bool isBuy=(dec.setup.type==ORDER_TYPE_BUY);
      double entry=m_orders.FillPriceAt(i);
      double price=CurrentExitPrice(dec.symbol,isBuy);
      if(price<=0.0 || entry<=0.0) continue;
      double r=RMultiple(dec,entry,price);
      double curSL=PositionGetDouble(POSITION_SL);

      MqlTick tick;
      if(!SymbolInfoTick(dec.symbol,tick)) continue;
      double point=SymbolInfoDouble(dec.symbol,SYMBOL_POINT);
      double spreadPoints=(point>0.0 ? (tick.ask-tick.bid)/point : 0.0);

      if(InpEnableDynamicStop && CanModifyNow(ticket))
        {
         // Source the anchor from the already-running, confirmed swing
         // detector for the entry timeframe. If no confirmed swing exists,
         // the DynamicStopEngine receives zero and deterministically falls
         // back to its ATR policy; it never fabricates structure.
         double structuralAnchor=ConfirmedStructuralAnchor(isBuy);
         DynamicStopDecision ds=m_dynamicStop.Evaluate(dec.symbol,isBuy,entry,dec.setup.stop_loss,
                                                        curSL,price,currentAtr,spreadPoints,structuralAnchor);
         if(ds.modify && m_broker.ModifySLTP(ticket,ds.proposedSL,dec.setup.final_tp))
           {
            m_audit.Record(ticket,dec.symbol,isBuy,EnumToString(ds.stage),curSL,ds.proposedSL,price,r,ds.reason);
            RecordModification(ticket);
            if(state==TS_FILLED) m_orders.TransitionAt(i,TS_PROTECTED);
           }
        }

      ENUM_TRADE_STATE stateAfterStop=m_orders.StateAt(i);

      // Research target ladder: TP1 realizes the first slice and TP2 realizes
      // a second slice, both from the original leg volume. The final TP order
      // remains attached to the runner. Promotion requires locked OOS evidence.
      if(InpEnableTargetLadder)
        {
         SyncTargetStage(i,ticket);
         int targetState=TargetStateIndex(ticket);
         if(!m_tp1Done[targetState] && dec.setup.tp1>0.0 &&
            CloseTargetSlice(i,ticket,isBuy,dec.setup.tp1,InpTP1PartialFraction))
            m_tp1Done[targetState]=true;
         if(!m_tp2Done[targetState] && dec.setup.tp2>0.0 &&
            CloseTargetSlice(i,ticket,isBuy,dec.setup.tp2,InpTP2PartialFraction))
            m_tp2Done[targetState]=true;
        }
      else if((stateAfterStop==TS_PROTECTED || stateAfterStop==TS_FILLED) && r>=m_partialAtR)
        {
         double vol=m_orders.VolumeAt(i)*m_partialFraction;
         double minVol=SymbolInfoDouble(dec.symbol,SYMBOL_VOLUME_MIN);
         if(vol>=minVol && vol<PositionGetDouble(POSITION_VOLUME) && m_broker.ClosePartial(ticket,vol))
            m_orders.TransitionAt(i,TS_PARTIAL);
         if(m_orders.StateAt(i)==TS_PARTIAL)
            m_orders.TransitionAt(i,TS_RUNNER);
        }
     }
  }
#endif
//+------------------------------------------------------------------+
