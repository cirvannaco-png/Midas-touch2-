//+------------------------------------------------------------------+
//| Execution/DynamicStopEngine.mqh                                  |
//| Dynamic Stop Engine v1 — decision policy only.                   |
//+------------------------------------------------------------------+
#ifndef DYNAMICSTOPENGINE_MQH
#define DYNAMICSTOPENGINE_MQH

// The engine deliberately separates STOP POLICY from broker execution.
// PositionManager/BrokerAdapter remain responsible for position lookup,
// broker distance/freeze validation, and the actual modification call.
// This makes the policy deterministic and backtest-friendly.

enum ENUM_DYNAMIC_STOP_STAGE
  {
   DSE_STRUCTURAL = 0,
   DSE_PROTECTION = 1,   // +0.75R: trailing protection becomes eligible
   DSE_BREAKEVEN  = 2,   // +1.00R: move toward breakeven
   DSE_TRAILING   = 3
  };

struct DynamicStopConfig
  {
   double activateAtR;       // 0.75
   double breakevenAtR;      // 1.00
   double atrMultiplier;     // subsequent trailing distance
   double minImprovementPts; // suppress meaningless broker modifications

   void SetDefaults()
     {
      activateAtR      = 0.75;
      breakevenAtR     = 1.00;
      atrMultiplier    = 1.50;
      minImprovementPts = 2.0;
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

   bool IsTighter(bool isBuy, double candidate, double current) const
     {
      if(current <= 0.0) return candidate > 0.0;
      return isBuy ? candidate > current : candidate < current;
     }

   bool ImprovementLargeEnough(string symbol, double candidate, double current) const
     {
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      if(point <= 0.0) return true;
      return MathAbs(candidate - current) >= m_cfg.minImprovementPts * point;
     }

public:
   void Configure(const DynamicStopConfig &cfg) { m_cfg = cfg; }
   DynamicStopConfig Config() const { return m_cfg; }

   // Pure policy calculation. It never widens an existing SL.
   DynamicStopDecision Evaluate(string symbol, bool isBuy, double entry,
                                double structuralSL, double currentSL,
                                double currentPrice, double atr) const
     {
      DynamicStopDecision d;
      d.stage = DSE_STRUCTURAL;
      d.proposedSL = structuralSL;
      d.modify = false;
      d.reason = "structural stop retained";

      double risk = MathAbs(entry - structuralSL);
      if(risk <= 0.0 || currentPrice <= 0.0)
        {
         d.reason = "invalid entry/structural risk";
         return d;
        }

      double favorableMove = isBuy ? currentPrice - entry : entry - currentPrice;
      double r = favorableMove / risk;

      if(r < m_cfg.activateAtR)
         return d;

      d.stage = DSE_PROTECTION;
      double candidate = isBuy
                         ? currentPrice - MathMax(atr, 0.0) * m_cfg.atrMultiplier
                         : currentPrice + MathMax(atr, 0.0) * m_cfg.atrMultiplier;

      if(r >= m_cfg.breakevenAtR)
        {
         d.stage = (atr > 0.0 ? DSE_TRAILING : DSE_BREAKEVEN);
         // Never place the candidate on the losing side of entry once
         // +1R has been reached. ATR trailing may be tighter than entry.
         if(isBuy) candidate = MathMax(candidate, entry);
         else      candidate = MathMin(candidate, entry);
        }

      if(IsTighter(isBuy, candidate, currentSL) && ImprovementLargeEnough(symbol, candidate, currentSL))
        {
         d.proposedSL = candidate;
         d.modify = true;
         d.reason = (d.stage == DSE_BREAKEVEN)
                    ? "+1.00R breakeven protection"
                    : (d.stage == DSE_PROTECTION ? "+0.75R trailing protection" : "ATR trailing tightened");
        }
      return d;
     }
  };

#endif
//+------------------------------------------------------------------+
