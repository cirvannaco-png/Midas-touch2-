//+------------------------------------------------------------------+
//| Execution/PositionManager.mqh                                    |
//+------------------------------------------------------------------+
#ifndef POSITIONMANAGER_MQH
#define POSITIONMANAGER_MQH

#include "OrderManager.mqh"
#include "BrokerAdapter.mqh"
#include "ExecutionLedgerClient.mqh"
#include "../Trading/RiskEngine.mqh"
#include "DynamicStopEngine.mqh"
#include "DynamicStopInputs.mqh"
#include "PositionManagementPolicy.mqh"
#include "../Monitoring/SLModificationAudit.mqh"
#include "../Structure/SwingDetector.mqh"

class CPositionManager
  {
private:
   COrderManager*        m_orders;
   CBrokerAdapter*       m_broker;
   CExecutionLedgerClient* m_ledger;
   CRiskEngine*           m_risk;
   double                 m_riskPercent;
   CSwingDetector*       m_structureSwings;
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
   double ConfirmedStructuralAnchor(bool isBuy);

public:
   void Init(COrderManager* orders,CBrokerAdapter* broker,
             double breakEvenAtR,double partialAtR,double partialFraction,double trailAtrMult,
             int maxSpreadPoints=0,double minATR=0.0,double maxATR=0.0,
             int minModifyIntervalSec=5,CSwingDetector* structureSwings=NULL,
             CExecutionLedgerClient* ledger=NULL,CRiskEngine* risk=NULL,double riskPercent=0.0);
   void OnTick(double currentAtr);
  };

void CPositionManager::Init(COrderManager* orders,CBrokerAdapter* broker,
                            double breakEvenAtR,double partialAtR,double partialFraction,double trailAtrMult,
                            int maxSpreadPoints,double minATR,double maxATR,int minModifyIntervalSec,
                            CSwingDetector* structureSwings,CExecutionLedgerClient* ledger,
                            CRiskEngine* risk,double riskPercent)
  {
   m_orders=orders;
   m_broker=broker;
   m_ledger=ledger;
   m_risk=risk;
   m_riskPercent=riskPercent;
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

      if(InpEnableDynamicStop && CanModifyNow(ticket))
        {
         // Source the anchor from the already-running, confirmed swing
         // detector for the entry timeframe. If no confirmed swing exists,
         // the DynamicStopEngine receives zero and deterministically falls
         // back to its ATR policy; it never fabricates structure.
         double structuralAnchor=ConfirmedStructuralAnchor(isBuy);
         DynamicStopDecision ds=m_dynamicStop.Evaluate(dec.symbol,isBuy,entry,dec.setup.stop_loss,
                                                        curSL,price,currentAtr,spreadPoints,structuralAnchor);
         if(ds.modify)
           {
            ulong positionIdentifier=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
            double oldTP=PositionGetDouble(POSITION_TP);
            string direction=isBuy?"BUY":"SELL";
            string eventId=StringFormat("modify:%I64u:%.10f:%.10f:%.10f:%.10f",
                                        positionIdentifier,curSL,ds.proposedSL,oldTP,dec.setup.final_tp);
            string intentEvidence="mt5-stop-intent:"+eventId;
            bool ledgerIntentReady=(m_ledger!=NULL && m_ledger.Ready() && positionIdentifier>0 &&
               m_ledger.PreparePositionModification(eventId,positionIdentifier,dec.symbol,direction,
                                                      curSL,oldTP,ds.proposedSL,dec.setup.final_tp,
                                                      intentEvidence));
            if(!ledgerIntentReady && m_ledger!=NULL)
               m_ledger.RequireReconciliation();

            // Protective broker changes are still attempted when the ledger
            // is unavailable. The admission latch remains closed until a
            // broker snapshot resolves any durable PENDING intent.
            bool brokerModified=m_broker.ModifySLTP(ticket,ds.proposedSL,dec.setup.final_tp);
            if(brokerModified)
              {
               double appliedSL=0.0;
               double appliedTP=0.0;
               if(PositionSelectByTicket(ticket))
                 {
                  double observedSL=PositionGetDouble(POSITION_SL);
                  double observedTP=PositionGetDouble(POSITION_TP);
                  appliedSL=observedSL;
                  appliedTP=observedTP;
                 }
               if(appliedSL<=0.0)
                 {
                  if(m_ledger!=NULL) m_ledger.RequireReconciliation();
                  PrintFormat("Midas position modification accepted but broker snapshot unavailable; ticket=%I64u",ticket);
                  continue;
                 }

               bool ledgerConfirmed=false;
               if(ledgerIntentReady && m_risk!=NULL && m_riskPercent>0.0)
                 {
                  double remainingRisk=0.0;
                  bool stopLocked=(isBuy && appliedSL>=entry) || (!isBuy && appliedSL<=entry);
                  if(stopLocked)
                     remainingRisk=0.0;
                  else
                     remainingRisk=m_risk.RiskAmountForLots(dec.symbol,PositionGetDouble(POSITION_VOLUME),
                                                            entry,appliedSL);
                  double baseRiskUnit=AccountInfoDouble(ACCOUNT_EQUITY)*m_riskPercent/100.0;
                  double riskR=(stopLocked ? 0.0 :
                                (baseRiskUnit>0.0 && remainingRisk>0.0 ? remainingRisk/baseRiskUnit : -1.0));
                  string confirmEvidence="mt5-stop-observed:"+eventId;
                  if(riskR>=0.0 && MathIsValidNumber(riskR))
                     ledgerConfirmed=m_ledger.ConfirmPositionModification(eventId,appliedSL,appliedTP,
                                                                            riskR,MathMax(0.0,currentAtr),
                                                                            confirmEvidence);
                 }
               if(!ledgerConfirmed && m_ledger!=NULL)
                 {
                  m_ledger.RequireReconciliation();
                  PrintFormat("Midas position modification awaits ledger reconciliation; ticket=%I64u",ticket);
                 }

               m_audit.Record(ticket,dec.symbol,isBuy,EnumToString(ds.stage),curSL,appliedSL,price,r,ds.reason);
               RecordModification(ticket);
               if(state==TS_FILLED) m_orders.TransitionAt(i,TS_PROTECTED);
              }
            else
              {
               // The broker result may be ambiguous after a transport failure.
               // Keep the intent unresolved and block further new entries.
               if(ledgerIntentReady && m_ledger!=NULL)
                  m_ledger.RequireReconciliation();
               RecordModification(ticket);
              }
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
