//+------------------------------------------------------------------+
//| Execution/PositionManager.mqh                                    |
//+------------------------------------------------------------------+
#ifndef POSITIONMANAGER_MQH
#define POSITIONMANAGER_MQH

#include "OrderManager.mqh"
#include "ExecutionLedgerClient.mqh"
#include "BrokerAdapter.mqh"
#include "DynamicStopEngine.mqh"
#include "DynamicStopInputs.mqh"
#include "PositionManagementPolicy.mqh"
#include "../Monitoring/SLModificationAudit.mqh"
#include "../Structure/SwingDetector.mqh"

struct PendingPositionModificationRecord
  {
   ulong  positionIdentifier;
   ulong  positionTicket;
   bool   brokerStateConfirmed;
   string symbol;
   string direction;
   double volume;
   double entryPrice;
   double previousSL;
   double appliedSL;
   double previousTP;
   double appliedTP;
   double riskR;
   double volatility;
   string evidenceRef;
  };

class CPositionManager
  {
private:
   COrderManager*        m_orders;
   CBrokerAdapter*       m_broker;
   CSwingDetector*       m_structureSwings;
   CExecutionLedgerClient* m_ledger;
   double                m_riskPercentPerTrade;
   bool                  m_ledgerReconciliationHealthy;
   int                   m_modificationSequence;
   PendingPositionModificationRecord m_pendingModifications[];
   CSLModificationAudit  m_audit;
   CDynamicStopEngine    m_dynamicStop;
   double                m_partialAtR;
   double                m_partialFraction;
   int                   m_minModifyIntervalSec;
   ulong                 m_lastModifyTickets[];
   datetime              m_lastModifyTimes[];

   double CurrentExitPrice(string symbol,bool isBuy);
   bool   PartialVolumeForPosition(string symbol,double currentVolume,double &closeVolume);
   double RMultiple(const TradeDecisionRecord &dec,double entry,double price);
   bool   CanModifyNow(ulong ticket);
   void   RecordModification(ulong ticket);
   bool   CalculateModificationRisk(PendingPositionModificationRecord &event);
   void   QueueModification(const PendingPositionModificationRecord &event);
   void   SendPendingModifications();
   bool   HasPendingModification(ulong positionIdentifier);
   double ConfirmedStructuralAnchor(bool isBuy);

public:
   void Init(COrderManager* orders,CBrokerAdapter* broker,
             double breakEvenAtR,double partialAtR,double partialFraction,double trailAtrMult,
             int maxSpreadPoints=0,double minATR=0.0,double maxATR=0.0,
             int minModifyIntervalSec=5,CSwingDetector* structureSwings=NULL,
             CExecutionLedgerClient* ledger=NULL,double riskPercentPerTrade=0.0);
   void OnTick(double currentAtr);
   void RetryPendingLedgerReconciliation();
   bool LedgerReconciliationHealthy() const { return m_ledgerReconciliationHealthy; }
  };

void CPositionManager::Init(COrderManager* orders,CBrokerAdapter* broker,
                            double breakEvenAtR,double partialAtR,double partialFraction,double trailAtrMult,
                            int maxSpreadPoints,double minATR,double maxATR,int minModifyIntervalSec,
                            CSwingDetector* structureSwings,CExecutionLedgerClient* ledger,
                            double riskPercentPerTrade)
  {
   m_orders=orders;
   m_broker=broker;
   m_structureSwings=structureSwings;
   m_ledger=ledger;
   m_riskPercentPerTrade=riskPercentPerTrade;
   m_modificationSequence=0;
   ArrayResize(m_pendingModifications,0);
   m_ledgerReconciliationHealthy=(!InpRequireExecutionLedger ||
                                  (m_ledger!=NULL && m_ledger.Ready()));
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

bool CPositionManager::PartialVolumeForPosition(string symbol,double currentVolume,double &closeVolume)
  {
   closeVolume=0.0;
   if(symbol=="" || !MathIsValidNumber(currentVolume) || currentVolume<=0.0 ||
      !MathIsValidNumber(m_partialFraction) || m_partialFraction<=0.0 || m_partialFraction>=1.0)
      return false;

   double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   double minVolume=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   if(!MathIsValidNumber(step) || !MathIsValidNumber(minVolume) || step<=0.0 || minVolume<=0.0)
      return false;

   int volumeDigits=0;
   for(int d=0;d<=8;d++)
      if(MathAbs(step-NormalizeDouble(step,d))<1e-9) { volumeDigits=d; break; }

   // Round down to the broker's volume step and validate both sides of the
   // partial close. A legal close amount that leaves an illegal remainder
   // is not a legal partial close. Never silently turn it into a full close.
   closeVolume=NormalizeDouble(MathFloor((currentVolume*m_partialFraction+1e-10)/step)*step,volumeDigits);
   double remainingVolume=NormalizeDouble(currentVolume-closeVolume,volumeDigits);
   double tolerance=step*0.25;
   if(closeVolume<minVolume-tolerance || remainingVolume<minVolume-tolerance ||
      closeVolume>=currentVolume-tolerance)
     {
      closeVolume=0.0;
      return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
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

bool CPositionManager::CalculateModificationRisk(PendingPositionModificationRecord &event)
  {
   if(event.volume<=0.0 || event.entryPrice<=0.0 || event.appliedSL<=0.0 ||
      m_riskPercentPerTrade<=0.0 || !MathIsValidNumber(m_riskPercentPerTrade))
      return false;
   double profitAtStop=0.0;
   ENUM_ORDER_TYPE orderType=(event.direction=="BUY")?ORDER_TYPE_BUY:ORDER_TYPE_SELL;
   if(!OrderCalcProfit(orderType,event.symbol,event.volume,event.entryPrice,event.appliedSL,profitAtStop) ||
      !MathIsValidNumber(profitAtStop))
      return false;
   double baseRiskUnit=AccountInfoDouble(ACCOUNT_EQUITY)*m_riskPercentPerTrade/100.0;
   if(baseRiskUnit<=0.0 || !MathIsValidNumber(baseRiskUnit)) return false;
   event.riskR=MathMax(0.0,-profitAtStop)/baseRiskUnit;
   return (MathIsValidNumber(event.riskR) && event.riskR>=0.0);
  }

void CPositionManager::QueueModification(const PendingPositionModificationRecord &event)
  {
   if(m_ledger==NULL && !InpRequireExecutionLedger) return;
   if(m_ledger!=NULL && !m_ledger.Ready() && !InpRequireExecutionLedger) return;
   int n=ArraySize(m_pendingModifications);
   ArrayResize(m_pendingModifications,n+1);
   m_pendingModifications[n]=event;
   m_ledgerReconciliationHealthy=false;
  }

void CPositionManager::SendPendingModifications()
  {
   for(int i=0;i<ArraySize(m_pendingModifications);)
     {
      if(m_ledger==NULL || !m_ledger.Ready())
        {
         i++;
         continue;
        }
      PendingPositionModificationRecord event=m_pendingModifications[i];
      if(!event.brokerStateConfirmed)
        {
         if(!PositionSelectByTicket(event.positionTicket))
           {
            i++;
            continue;
           }
         event.positionIdentifier=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
         event.volume=PositionGetDouble(POSITION_VOLUME);
         event.entryPrice=PositionGetDouble(POSITION_PRICE_OPEN);
         event.appliedSL=PositionGetDouble(POSITION_SL);
         event.appliedTP=PositionGetDouble(POSITION_TP);
         event.brokerStateConfirmed=(event.positionIdentifier>0 && event.appliedSL>0.0 &&
                                     event.volume>0.0 && event.entryPrice>0.0);
         m_pendingModifications[i]=event;
         if(!event.brokerStateConfirmed)
           {
            i++;
            continue;
           }
        }
      if(event.riskR<0.0 && !CalculateModificationRisk(event))
        {
         i++;
         continue;
        }
      // Persist the exact risk snapshot before the HTTP call. If the server
      // commits but the response is lost, an idempotent retry must send the
      // identical payload and evidence fingerprint.
      m_pendingModifications[i]=event;
      if(!m_ledger.PositionModification(event.positionIdentifier,event.symbol,event.direction,
                                        event.volume,event.entryPrice,event.previousSL,event.appliedSL,
                                        event.previousTP,event.appliedTP,event.riskR,event.volatility,
                                        event.evidenceRef))
        {
         i++;
         continue;
        }
      int last=ArraySize(m_pendingModifications)-1;
      if(i!=last) m_pendingModifications[i]=m_pendingModifications[last];
      ArrayResize(m_pendingModifications,last);
     }
   m_ledgerReconciliationHealthy=(ArraySize(m_pendingModifications)==0 &&
                                  (!InpRequireExecutionLedger ||
                                   (m_ledger!=NULL && m_ledger.Ready())));
  }

bool CPositionManager::HasPendingModification(ulong positionIdentifier)
  {
   for(int i=0;i<ArraySize(m_pendingModifications);i++)
      if(m_pendingModifications[i].positionIdentifier==positionIdentifier) return true;
   return false;
}

void CPositionManager::RetryPendingLedgerReconciliation()
  {
   SendPendingModifications();
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
   SendPendingModifications();
   for(int i=0;i<m_orders.Total();i++)
     {
      ENUM_TRADE_STATE state=m_orders.StateAt(i);
      if(state!=TS_FILLED && state!=TS_PROTECTED && state!=TS_PARTIAL && state!=TS_RUNNER)
         continue;

      ulong ticket=m_orders.PositionTicketAt(i);
      if(ticket==0) continue;
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

      ulong currentPositionIdentifier=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      if(InpEnableDynamicStop && !HasPendingModification(currentPositionIdentifier) && CanModifyNow(ticket))
        {
         // Source the anchor from the already-running, confirmed swing
         // detector for the entry timeframe. If no confirmed swing exists,
         // the DynamicStopEngine receives zero and deterministically falls
         // back to its ATR policy; it never fabricates structure.
         double structuralAnchor=ConfirmedStructuralAnchor(isBuy);
         DynamicStopDecision ds=m_dynamicStop.Evaluate(dec.symbol,isBuy,entry,dec.setup.stop_loss,
                                                        curSL,price,currentAtr,spreadPoints,structuralAnchor);
         double previousTP=PositionGetDouble(POSITION_TP);
         if(ds.modify && m_broker.ModifySLTP(ticket,ds.proposedSL,dec.setup.final_tp))
           {
            // Do not treat a successful trade-server retcode as complete
            // reconciliation: queue an immutable event and confirm the broker
            // readback before it can be acknowledged by the remote ledger.
            m_modificationSequence++;
            PendingPositionModificationRecord event;
            event.positionIdentifier=currentPositionIdentifier;
            event.positionTicket=ticket;
            event.brokerStateConfirmed=false;
            event.symbol=dec.symbol;
            event.direction=isBuy?"BUY":"SELL";
            event.volume=PositionGetDouble(POSITION_VOLUME);
            event.entryPrice=PositionGetDouble(POSITION_PRICE_OPEN);
            event.previousSL=curSL;
            event.appliedSL=ds.proposedSL;
            event.previousTP=previousTP;
            event.appliedTP=dec.setup.final_tp;
            event.riskR=-1.0;
            event.volatility=MathMax(0.0,currentAtr);
            event.evidenceRef=StringFormat("mt5-position-modification:%I64u:%I64d:%u:%d:%.8f",
                                           currentPositionIdentifier,(long)TimeCurrent(),
                                           GetTickCount(),m_modificationSequence,ds.proposedSL);
            if(PositionSelectByTicket(ticket))
              {
               ulong observedIdentifier=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
               double observedSL=PositionGetDouble(POSITION_SL);
               if(observedIdentifier==currentPositionIdentifier && observedSL>0.0)
                 {
                  event.positionIdentifier=observedIdentifier;
                  event.volume=PositionGetDouble(POSITION_VOLUME);
                  event.entryPrice=PositionGetDouble(POSITION_PRICE_OPEN);
                  event.appliedSL=observedSL;
                  event.appliedTP=PositionGetDouble(POSITION_TP);
                  event.brokerStateConfirmed=(event.volume>0.0 && event.entryPrice>0.0);
                 }
              }
            QueueModification(event);
            SendPendingModifications();
            m_audit.Record(ticket,dec.symbol,isBuy,EnumToString(ds.stage),curSL,event.appliedSL,price,r,ds.reason);
            RecordModification(ticket);
            if(state==TS_FILLED) m_orders.TransitionAt(i,TS_PROTECTED);
           }
        }

      ENUM_TRADE_STATE stateAfterStop=m_orders.StateAt(i);
      if(ShouldTakePartialAtR(stateAfterStop,r,m_partialAtR))
        {
         double currentVolume=PositionGetDouble(POSITION_VOLUME);
         double closeVolume=0.0;
         // Skip locally when broker volume constraints make a partial close
         // impossible. This avoids repeating a predictably invalid request
         // on every tick while trailing-stop management continues normally.
         if(PartialVolumeForPosition(dec.symbol,currentVolume,closeVolume) &&
            m_broker.ClosePartial(ticket,closeVolume))
            m_orders.TransitionAt(i,TS_PARTIAL);
        }
      if(m_orders.StateAt(i)==TS_PARTIAL)
         m_orders.TransitionAt(i,TS_RUNNER);
     }
  }
#endif
//+------------------------------------------------------------------+
