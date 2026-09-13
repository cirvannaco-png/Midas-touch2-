//+------------------------------------------------------------------+
//| Execution/DynamicStopEngine.mqh                                  |
//| Dynamic Stop Engine v1 — deterministic stop-policy layer.        |
//+------------------------------------------------------------------+
#ifndef DYNAMICSTOPENGINE_MQH
#define DYNAMICSTOPENGINE_MQH

#include "DynamicStopInputs.mqh"

enum ENUM_DYNAMIC_STOP_STAGE
  {
   DSE_STRUCTURAL = 0,
   DSE_PROTECTION = 1,
   DSE_BREAKEVEN  = 2,
   DSE_TRAILING   = 3
  };

struct DynamicStopConfig
  {
   double activateAtR;
   double breakevenAtR;
   double atrMultiplier;
   double minImprovementPts;
   int    maxSpreadPoints;
   double minATR;
   double maxATR;
   bool   useStructuralAnchor;
   double structuralBufferATR;

   void SetDefaults()
     {
      activateAtR          = 0.75;
      breakevenAtR         = 1.00;
      atrMultiplier        = 1.50;
      minImprovementPts    = 2.0;
      maxSpreadPoints      = 0;
      minATR               = 0.0;
      maxATR               = 0.0;
      useStructuralAnchor  = true;
      structuralBufferATR  = 0.10;
     }
  };

struct DynamicStopDecision
  {
   ENUM_DYNAMIC_STOP_STAGE stage;
   double proposedSL;
   bool modify;
   string reason;
  };

class CDynamicStopEngine
  {
private:
   DynamicStopConfig m_cfg;

   bool IsTighter(bool isBuy,double candidate,double current) const
     {
      if(candidate<=0.0) return false;
      if(current<=0.0) return true;
      return isBuy ? candidate>current : candidate<current;
     }

   bool ImprovementLargeEnough(string symbol,double candidate,double current) const
     {
      double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
      if(point<=0.0) return true;
      return MathAbs(candidate-current)>=m_cfg.minImprovementPts*point;
     }

   // Preflight the same broker geometry that BrokerAdapter validates before
   // sending PositionModify().  For an open BUY the protective stop is
   // measured from Bid; for an open SELL it is measured from Ask.  Stops
   // and freeze levels are broker constraints, not strategy preferences.
   // Rejecting here avoids repeatedly generating modifications that the
   // broker is guaranteed to reject while the price is inside the freeze
   // band. BrokerAdapter still performs the authoritative final check.
   bool BrokerDistanceSafe(string symbol,bool isBuy,double candidate,double currentPrice) const
     {
      if(candidate<=0.0 || currentPrice<=0.0) return false;
      double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
      if(point<=0.0) return false;
      long stops=(long)SymbolInfoInteger(symbol,SYMBOL_TRADE_STOPS_LEVEL);
      long freeze=(long)SymbolInfoInteger(symbol,SYMBOL_TRADE_FREEZE_LEVEL);
      long required=MathMax(stops,freeze);
      if(required<=0) return true;
      double minDistance=(double)required*point;
      return MathAbs(currentPrice-candidate)>=minDistance;
     }

public:
   void Configure(const DynamicStopConfig &cfg) { m_cfg=cfg; }
   DynamicStopConfig Config() const { return m_cfg; }

   // structuralAnchor is supplied by the caller from a confirmed market
   // structure point. Zero means "no anchor available" and causes a
   // deterministic ATR fallback rather than inventing structure.
   DynamicStopDecision Evaluate(string symbol,bool isBuy,double entry,
                                double structuralSL,double currentSL,
                                double currentPrice,double atr,
                                double spreadPoints=0.0,
                                double structuralAnchor=0.0) const
     {
      DynamicStopDecision d;
      d.stage=DSE_STRUCTURAL;
      d.proposedSL=structuralSL;
      d.modify=false;
      d.reason="structural stop retained";

      if(entry<=0.0 || structuralSL<=0.0 || currentPrice<=0.0)
        { d.reason="invalid entry/structural stop/price"; return d; }
      if(m_cfg.maxSpreadPoints>0 && spreadPoints>m_cfg.maxSpreadPoints)
        { d.reason="spread protection"; return d; }
      if(m_cfg.minATR>0.0 && atr<m_cfg.minATR)
        { d.reason="volatility below floor"; return d; }
      if(m_cfg.maxATR>0.0 && atr>m_cfg.maxATR)
        { d.reason="volatility above ceiling"; return d; }

      double risk=MathAbs(entry-structuralSL);
      if(risk<=0.0) { d.reason="zero structural risk"; return d; }
      double favorableMove=isBuy ? currentPrice-entry : entry-currentPrice;
      double r=favorableMove/risk;
      if(r<m_cfg.activateAtR) return d;

      d.stage=DSE_PROTECTION;
      double candidate=isBuy
                        ? currentPrice-MathMax(atr,0.0)*m_cfg.atrMultiplier
                        : currentPrice+MathMax(atr,0.0)*m_cfg.atrMultiplier;

      if(m_cfg.useStructuralAnchor && structuralAnchor>0.0 && atr>0.0)
        {
         double anchorCandidate=isBuy
                               ? structuralAnchor-MathMax(0.0,m_cfg.structuralBufferATR)*atr
                               : structuralAnchor+MathMax(0.0,m_cfg.structuralBufferATR)*atr;
         // Never manufacture a stop on the wrong side of the market.
         bool validAnchor=isBuy ? (anchorCandidate<currentPrice && anchorCandidate>0.0)
                                : (anchorCandidate>currentPrice && anchorCandidate>0.0);
         if(validAnchor)
           {
            candidate=anchorCandidate;
            d.stage=DSE_TRAILING;
            d.reason="confirmed structural-anchor trailing";
           }
        }

      if(r>=m_cfg.breakevenAtR)
        {
         if(isBuy) candidate=MathMax(candidate,entry);
         else      candidate=MathMin(candidate,entry);
         if(d.stage!=DSE_TRAILING)
            d.stage=(atr>0.0 ? DSE_TRAILING : DSE_BREAKEVEN);
        }

      if(!BrokerDistanceSafe(symbol,isBuy,candidate,currentPrice))
        {
         d.reason="broker stops/freeze distance protection";
         return d;
        }

      if(IsTighter(isBuy,candidate,currentSL) && ImprovementLargeEnough(symbol,candidate,currentSL))
        {
         d.proposedSL=candidate;
         d.modify=true;
         if(d.reason=="structural stop retained")
            d.reason=(d.stage==DSE_BREAKEVEN ? "+1R breakeven protection" : "+0.75R protection");
        }
      else if(!IsTighter(isBuy,candidate,currentSL))
         d.reason="candidate would widen or equal current stop";
      else
         d.reason="improvement below modification threshold";
      return d;
     }
  };
#endif
//+------------------------------------------------------------------+
