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
      if(stateAfterStop==TS_PROTECTED && r>=m_partialAtR)
        {
         double vol=m_orders.VolumeAt(i)*m_partialFraction;
         double minVol=SymbolInfoDouble(dec.symbol,SYMBOL_VOLUME_MIN);
         if(vol>=minVol && m_broker.ClosePartial(ticket,vol))
            m_orders.TransitionAt(i,TS_PARTIAL);
        }
      if(m_orders.StateAt(i)==TS_PARTIAL)
         m_orders.TransitionAt(i,TS_RUNNER);
     }
  }
#endif
//+------------------------------------------------------------------+
