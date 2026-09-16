//+------------------------------------------------------------------+
//| Trading/StrategySetupBuilders.mqh                                |
//| Strategy-owned TradeSetup construction boundary.                 |
//+------------------------------------------------------------------+
#ifndef STRATEGYSETUPBUILDERS_MQH
#define STRATEGYSETUPBUILDERS_MQH

#include "../Core/Config.mqh"
#include "../Analysis/TFContext.mqh"
#include "Targets.mqh"

// This class does not select strategies. It receives an authoritative
// selection and constructs the setup for THAT strategy only. A missing or
// structurally ambiguous strategy read fails closed; SMC is never used as
// a silent fallback for a challenger.
class CStrategySetupBuilders
  {
private:
   static bool FindRecentBOS(CTFContext* bosCtx, bool forBuy, BOSEvent &out, int maxBars = 20)
     {
      if(bosCtx == NULL) return false;
      for(int i = 0; i < bosCtx.bos.Count(); i++)
        {
         BOSEvent ev = bosCtx.bos.GetBOS(i);
         if(ev.bar_index > maxBars) break;
         if(ev.is_bullish == forBuy) { out = ev; return true; }
        }
      return false;
     }

   static bool FindNearestSR(CTFContext* srCtx, bool forBuy, double price, double atr,
                             double &level, int &touches)
     {
      if(srCtx == NULL || atr <= 0) return false;
      double best = DBL_MAX;
      bool found = false;
      touches = 0;
      for(int i = 0; i < srCtx.sr.Count(); i++)
        {
         SRZone z = srCtx.sr.GetZone(i);
         bool support = (z.type == SR_MAJOR_SUPPORT || z.type == SR_MINOR_SUPPORT);
         bool resistance = (z.type == SR_MAJOR_RESISTANCE || z.type == SR_MINOR_RESISTANCE);
         if(forBuy && !support) continue;
         if(!forBuy && !resistance) continue;
         double candidate = forBuy ? z.top : z.bottom;
         double dist = MathAbs(price - candidate);
         if(dist <= 3.0 * atr && dist < best)
           { best = dist; level = candidate; touches = z.touches; found = true; }
        }
      return found;
     }

   static bool FindValueEdge(CTFContext* srCtx, bool forBuy, double price, double atr,
                             double &edge, double &stretchATR)
     {
      if(srCtx == NULL || !srCtx.valueArea.IsValid() || atr <= 0) return false;
      edge = forBuy ? srCtx.valueArea.VAL() : srCtx.valueArea.VAH();
      stretchATR = forBuy ? (edge - price) / atr : (price - edge) / atr;
      return stretchATR >= 1.0;
     }

   static bool ValidateCandidate(TradeSetup &setup, bool forBuy)
     {
      if(!setup.active) return false;
      if(!MathIsValidNumber(setup.entry_top) || !MathIsValidNumber(setup.entry_bottom) ||
         !MathIsValidNumber(setup.invalidation) || !MathIsValidNumber(setup.stop_loss) ||
         !MathIsValidNumber(setup.tp1) || !MathIsValidNumber(setup.tp2) ||
         !MathIsValidNumber(setup.final_tp) || !MathIsValidNumber(setup.confidence)) return false;
      if(setup.entry_top < setup.entry_bottom) return false;
      if(forBuy)
        return setup.stop_loss < setup.entry_bottom && setup.invalidation < setup.entry_bottom &&
               setup.tp1 > setup.entry_top && setup.tp2 > setup.tp1 && setup.final_tp > setup.tp2;
      return setup.stop_loss > setup.entry_top && setup.invalidation > setup.entry_top &&
             setup.tp1 < setup.entry_bottom && setup.tp2 < setup.tp1 && setup.final_tp < setup.tp2;
     }

public:
   static bool BuildMomentum(bool forBuy, double confidence, const SetupReasons &r,
                             CTFContext* priceCtx, CTFContext* bosCtx, CTFContext* liqCtx,
                             TradeSetup &out)
     {
      ZeroMemory(out);
      if(r.regime != REGIME_TRENDING ||
         (r.breakout_class != BREAKOUT_EXPANSION && r.breakout_class != BREAKOUT_LIQUIDITY) ||
         priceCtx == NULL || bosCtx == NULL) return false;
      double price = priceCtx.candles.GetCandle(0).close;
      double atr = bosCtx.candles.GetATR(0);
      if(price <= 0 || atr <= 0) return false;
      BOSEvent bos;
      if(!FindRecentBOS(bosCtx, forBuy, bos)) return false;
      double chase = forBuy ? (price - bos.price) / atr : (bos.price - price) / atr;
      if(chase > 0.75) return false;

      out.type = forBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      out.entry_top = price;
      out.entry_bottom = price;
      out.invalidation = forBuy ? bos.price - 0.15 * atr : bos.price + 0.15 * atr;
      out.stop_loss = forBuy ? out.invalidation - 0.10 * atr : out.invalidation + 0.10 * atr;
      CTargetSelector::AssignTargets(out, liqCtx, priceCtx.candles.Symbol(), atr, price);
      out.confidence = MathMax(0.0, MathMin(confidence, 100.0));
      out.creation_time = TimeCurrent();
      out.expiry_time = 0;
      out.active = true;
      out.reasons = r;
      out.reasons.risk_warning = StringFormat("Momentum breakout owner: BOS %.5f, chase %.2f ATR", bos.price, chase);
      return ValidateCandidate(out, forBuy);
     }

   static bool BuildMeanReversion(bool forBuy, double confidence, const SetupReasons &r,
                                  CTFContext* priceCtx, CTFContext* srCtx, CTFContext* liqCtx,
                                  TradeSetup &out)
     {
      ZeroMemory(out);
      if(r.regime != REGIME_RANGING ||
         (r.reversion_class != REVERSION_VALUE_FADE && r.reversion_class != REVERSION_LEVEL_REJECTION) ||
         priceCtx == NULL || srCtx == NULL) return false;
      double price = priceCtx.candles.GetCandle(0).close;
      double atr = srCtx.candles.GetATR(0);
      if(price <= 0 || atr <= 0) return false;

      double level = 0.0, stretch = 0.0;
      bool haveValue = FindValueEdge(srCtx, forBuy, price, atr, level, stretch);
      int touches = 0;
      if(!haveValue && !FindNearestSR(srCtx, forBuy, price, atr, level, touches)) return false;
      if(r.reversion_class == REVERSION_VALUE_FADE && !haveValue) return false;

      out.type = forBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      out.entry_top = price;
      out.entry_bottom = price;
      out.invalidation = forBuy ? level - 0.25 * atr : level + 0.25 * atr;
      out.stop_loss = forBuy ? out.invalidation - 0.15 * atr : out.invalidation + 0.15 * atr;
      CTargetSelector::AssignTargets(out, liqCtx, priceCtx.candles.Symbol(), atr, price);
      out.confidence = MathMax(0.0, MathMin(confidence, 100.0));
      out.creation_time = TimeCurrent();
      out.expiry_time = 0;
      out.active = true;
      out.reasons = r;
      out.reasons.risk_warning = StringFormat("Mean-reversion owner: reference %.5f%s", level,
                                               haveValue ? StringFormat(", stretch %.2f ATR", stretch) : "");
      return ValidateCandidate(out, forBuy);
     }

   static bool BuildKeyLevel(bool forBuy, double confidence, const SetupReasons &r,
                             CTFContext* priceCtx, CTFContext* srCtx, CTFContext* liqCtx,
                             TradeSetup &out)
     {
      ZeroMemory(out);
      if(r.regime != REGIME_TRANSITION ||
         (r.keylevel_reaction != REACTION_REJECTION && r.keylevel_reaction != REACTION_RETEST &&
          r.keylevel_reaction != REACTION_FAILED_BREAK && r.keylevel_reaction != REACTION_ABSORPTION) ||
         priceCtx == NULL || srCtx == NULL) return false;
      double price = priceCtx.candles.GetCandle(0).close;
      double atr = srCtx.candles.GetATR(0);
      if(price <= 0 || atr <= 0) return false;

      double level = 0.0;
      int touches = 0;
      if(!FindNearestSR(srCtx, forBuy, price, atr, level, touches)) return false;

      out.type = forBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      out.entry_top = price;
      out.entry_bottom = price;
      out.invalidation = forBuy ? level - 0.25 * atr : level + 0.25 * atr;
      out.stop_loss = forBuy ? out.invalidation - 0.15 * atr : out.invalidation + 0.15 * atr;
      CTargetSelector::AssignTargets(out, liqCtx, priceCtx.candles.Symbol(), atr, price);
      out.confidence = MathMax(0.0, MathMin(confidence, 100.0));
      out.creation_time = TimeCurrent();
      out.expiry_time = 0;
      out.active = true;
      out.reasons = r;
      out.reasons.risk_warning = StringFormat("Key-level owner: level %.5f, %d touches, reaction %s",
                                               level, touches, EnumToString(r.keylevel_reaction));
      return ValidateCandidate(out, forBuy);
     }
  };

#endif
//+------------------------------------------------------------------+
