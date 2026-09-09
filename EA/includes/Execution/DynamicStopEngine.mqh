//+------------------------------------------------------------------+
//| Execution/DynamicStopEngine.mqh                                  |
//| Dynamic Stop Engine v1 — deterministic stop-policy layer.        |
//+------------------------------------------------------------------+
#ifndef DYNAMICSTOPENGINE_MQH
#define DYNAMICSTOPENGINE_MQH

enum ENUM_DYNAMIC_STOP_STAGE
  {
   DSE_STRUCTURAL = 0,
   DSE_PROTECTION = 1,
   DSE_BREAKEVEN  = 2,
   DSE_TRAILING   = 3
  };

struct DynamicStopConfig
  {
   double activateAtR;          // +0.75R
   double breakevenAtR;         // +1.00R
   double atrMultiplier;        // structural/ATR trailing distance
   double minImprovementPts;    // suppress meaningless modifications
   int    maxSpreadPoints;      // 0 = disabled
   double minATR;               // 0 = disabled
   double maxATR;               // 0 = disabled

   void SetDefaults()
     {
      activateAtR       = 0.75;
      breakevenAtR      = 1.00;
      atrMultiplier     = 1.50;
      minImprovementPts = 2.0;
      maxSpreadPoints   = 0;
      minATR            = 0.0;
      maxATR            = 0.0;
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

public:
   void Configure(const DynamicStopConfig &cfg) { m_cfg=cfg; }
   DynamicStopConfig Config() const { return m_cfg; }

   // Pure policy calculation. Broker checks and PositionModify remain
   // outside this class so the same decision can be replayed in a test.
   DynamicStopDecision Evaluate(string symbol,bool isBuy,double entry,
                                double structuralSL,double currentSL,
                                double currentPrice,double atr,
                                double spreadPoints=0.0) const
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

      if(r>=m_cfg.breakevenAtR)
        {
         d.stage=(atr>0.0 ? DSE_TRAILING : DSE_BREAKEVEN);
         if(isBuy) candidate=MathMax(candidate,entry);
         else      candidate=MathMin(candidate,entry);
        }

      if(IsTighter(isBuy,candidate,currentSL) && ImprovementLargeEnough(symbol,candidate,currentSL))
        {
         d.proposedSL=candidate;
         d.modify=true;
         d.reason=(d.stage==DSE_BREAKEVEN)
                   ? "+1R breakeven protection"
                   : (d.stage==DSE_PROTECTION ? "+0.75R protection" : "ATR trailing tightened");
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
