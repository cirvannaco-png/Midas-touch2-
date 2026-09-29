//+------------------------------------------------------------------+
//| SmartMoney/SMCStructuralValidator.mqh                           |
//+------------------------------------------------------------------+
#ifndef SMC_STRUCTURAL_VALIDATOR_MQH
#define SMC_STRUCTURAL_VALIDATOR_MQH

#include "../Core/Config.mqh"
#include "../Analysis/TFContext.mqh"

// Diagnostic structural validator for the SMC chain.
//
// It does NOT modify confidence, strategy selection, risk, or execution.
// Its job is to make the causal structure measurable so backtests can
// compare structurally-valid and structurally-invalid SMC outcomes before
// any hard gate is promoted.
//
// Chain represented here:
//   trend/HTF structure -> liquidity target -> sweep -> displacement/BOS
//   -> causal entry origin (FVG or local OB) -> premium/discount
//   -> freshness -> structural invalidation.
//
// "HTF OB" is deliberately telemetry-only. A nearby HTF OB is context, not
// proof that the entry-timeframe structure is valid.

class CSMCStructuralValidator
  {
private:
   CTFContext* m_trendCtx;
   CTFContext* m_fvgCtx;
   CTFContext* m_htfObCtx;
   double       m_fvgMaxDistATR;
   double       m_obDistATRMax;

   bool FindCausalFVG(bool forBuy, int sweepBarIndex, int bosBarIndex, double price, int &barIndex);
   bool FindCausalOrderBlock(bool forBuy, int sweepBarIndex, int bosBarIndex, double price, int &barIndex);

public:
   CSMCStructuralValidator();
   void Init(CTFContext* trendCtx, CTFContext* fvgCtx, CTFContext* htfObCtx);
   void Configure(double fvgMaxDistATR = 1.25, double obDistATRMax = 2.0);
   SMCStructuralValidation Validate(bool forBuy, const InducementResult &ind,
                                     double price, ENUM_MARKET_REGIME regime,
                                     bool premiumDiscountValid);
  };

//+------------------------------------------------------------------+
CSMCStructuralValidator::CSMCStructuralValidator()
  : m_trendCtx(NULL), m_fvgCtx(NULL), m_htfObCtx(NULL),
    m_fvgMaxDistATR(1.25), m_obDistATRMax(2.0)
  {
  }

//+------------------------------------------------------------------+
void CSMCStructuralValidator::Init(CTFContext* trendCtx, CTFContext* fvgCtx,
                                    CTFContext* htfObCtx)
  {
   m_trendCtx = trendCtx;
   m_fvgCtx = fvgCtx;
   m_htfObCtx = htfObCtx;
  }

//+------------------------------------------------------------------+
void CSMCStructuralValidator::Configure(double fvgMaxDistATR, double obDistATRMax)
  {
   m_fvgMaxDistATR = (fvgMaxDistATR > 0.0) ? fvgMaxDistATR : 1.25;
   m_obDistATRMax = (obDistATRMax > 0.0) ? obDistATRMax : 2.0;
  }

//+------------------------------------------------------------------+
// Entry-origin causality is intentionally time-directional:
// a qualifying FVG must be at the BOS bar or newer (smaller series
// index), never older than the confirming BOS. Shift 0 is excluded because
// the current candle is still forming when the EA evaluates a new bar.
bool CSMCStructuralValidator::FindCausalFVG(bool forBuy, int sweepBarIndex, int bosBarIndex,
                                             double price, int &barIndex)
  {
   barIndex = -1;
   if(m_fvgCtx == NULL || sweepBarIndex <= 0 || bosBarIndex <= 0 || sweepBarIndex < bosBarIndex || price <= 0.0) return false;
   double atr = m_fvgCtx.candles.GetATR(1);
   if(atr <= 0.0) return false;

   ENUM_FVG_DIR wantDir = forBuy ? FVG_BULL : FVG_BEAR;
   double bestScore = -1.0;

   for(int i = 0; i < m_fvgCtx.fvg.Count(); i++)
     {
      FVGZone z = m_fvgCtx.fvg.GetZone(i);
      if(z.dir != wantDir) continue;
      if(z.state != FVG_FRESH && z.state != FVG_TESTED) continue;
      if(z.bar_index <= 0 || z.bar_index > sweepBarIndex || z.bar_index < bosBarIndex) continue;

      double mid = (z.top + z.bottom) / 2.0;
      double distATR = MathAbs(price - mid) / atr;
      if(distATR > m_fvgMaxDistATR) continue;

      double base = (z.state == FVG_FRESH) ? 1.0 : 0.6;
      double proximity = MathMax(0.0, 1.0 - distATR / m_fvgMaxDistATR);
      double score = base * (0.5 + 0.5 * proximity);
      if(score > bestScore)
        {
         bestScore = score;
         barIndex = z.bar_index;
        }
     }

   return barIndex > 0;
  }

//+------------------------------------------------------------------+
// A local/entry-timeframe OB is causal only when its originating candle
// is no older than the confirming BOS and the zone comes from the same
// timeframe as the entry FVG. The chart-TF SR context is deliberately not
// used for causal provenance; HTF OB is handled separately below.
bool CSMCStructuralValidator::FindCausalOrderBlock(bool forBuy, int sweepBarIndex, int bosBarIndex,
                                                    double price, int &barIndex)
  {
   barIndex = -1;
   // Causal/local OB provenance must come from the same timeframe as the
   // entry FVG. the chart-TF SR context may differ from m_fvgCtx;
   // using it here would mislabel a cross-timeframe zone as entry-causal.
   if(m_fvgCtx == NULL || sweepBarIndex <= 0 || bosBarIndex <= 0 || sweepBarIndex < bosBarIndex || price <= 0.0) return false;

   // Use a closed entry-TF bar for the distance normalization so the
   // diagnostic dataset does not depend on the still-forming bar's ATR.
   double atr = m_fvgCtx.candles.GetATR(1);
   if(atr <= 0.0) return false;

   ENUM_FVG_DIR wantDir = forBuy ? FVG_BULL : FVG_BEAR;
   double bestDist = DBL_MAX;

   for(int i = 0; i < m_fvgCtx.orderBlock.Count(); i++)
     {
      OrderBlockZone z = m_fvgCtx.orderBlock.GetZone(i);
      if(z.dir != wantDir || z.state == OB_MITIGATED) continue;
      if(z.bar_index <= 0 || z.bar_index > sweepBarIndex || z.bar_index < bosBarIndex) continue;

      double mid = (z.top + z.bottom) / 2.0;
      double distATR = MathAbs(price - mid) / atr;
      if(distATR > m_obDistATRMax) continue;
      if(distATR < bestDist)
        {
         bestDist = distATR;
         barIndex = z.bar_index;
        }
     }

   return barIndex > 0;
  }

//+------------------------------------------------------------------+
SMCStructuralValidation CSMCStructuralValidator::Validate(
   bool forBuy, const InducementResult &ind, double price,
   ENUM_MARKET_REGIME regime, bool premiumDiscountValid)
  {
   SMCStructuralValidation v;
   ZeroMemory(v);
   v.state = SMC_WAIT;
   v.sweep_bar_index = ind.sweepBarIndex;
   v.bos_bar_index = ind.bosBarIndex;
   v.displacement_bar_index = ind.displacementBarIndex;
   v.entry_fvg_bar_index = -1;
   v.causal_ob_bar_index = -1;
   v.premium_discount_valid = premiumDiscountValid;

   // Market state is applicability context, not a confidence bonus.
   v.regime_applicable = (regime != REGIME_UNDEFINED);

   // Treat the trend context as HTF only when it is actually slower
   // than the entry/FVG context. A parameter called "TrendTF" is not enough
   // proof by itself; the validator verifies the timeframe relationship.
   bool genuineHtf = (m_trendCtx != NULL && m_fvgCtx != NULL &&
                      PeriodSeconds(m_trendCtx.tf) > PeriodSeconds(m_fvgCtx.tf));
   if(genuineHtf)
     {
      ENUM_TREND_STATE trend = m_trendCtx.trend.GetCurrentTrend();
      v.htf_structure_valid = forBuy
                              ? (trend == TREND_BULL || trend == TREND_BULL_STRONG)
                              : (trend == TREND_BEAR || trend == TREND_BEAR_STRONG);
     }
   else
     {
      v.htf_structure_valid = false;
     }

   v.liquidity_target_valid = ind.internalStructureFound && ind.sweepFound;
   v.sweep_valid = ind.sweepFound;
   v.displacement_valid = ind.impulseFound && ind.leg.valid && ind.displacementBarIndex > ind.sweepBarIndex && ind.sweepBarIndex > ind.bosBarIndex && ind.bosBarIndex > 0;
   v.bos_valid = ind.bosConfirmed && ind.sweepBarIndex > ind.bosBarIndex && ind.bosBarIndex > 0;
   v.freshness_valid = (ind.timeDecay > 0.0);

   // Structural invalidation uses the protected extreme of the impulse leg.
   // Crossing it means the causal thesis that created the setup is no longer
   // intact, regardless of confidence.
   v.protected_level = ind.leg.start_price;
   v.invalidation_level = ind.leg.start_price;
   v.invalidation_clear = true;
   if(ind.leg.valid && price > 0.0)
      v.invalidation_clear = forBuy ? (price > v.invalidation_level)
                                    : (price < v.invalidation_level);

   if(ind.bosConfirmed && v.displacement_valid && price > 0.0)
     {
      v.fvg_causal = FindCausalFVG(forBuy, ind.sweepBarIndex, ind.bosBarIndex, price, v.entry_fvg_bar_index);
      v.order_block_causal = FindCausalOrderBlock(forBuy, ind.sweepBarIndex, ind.bosBarIndex, price, v.causal_ob_bar_index);
     }

   if(m_htfObCtx != NULL && price > 0.0)
     {
      double atr = m_htfObCtx.candles.GetATR(1);
      if(atr > 0.0)
        {
         OrderBlockZone z;
         if(m_htfObCtx.orderBlock.NearestZone(forBuy ? FVG_BULL : FVG_BEAR,
                                               price, atr, m_obDistATRMax, z))
            v.htf_ob_present = (z.state == OB_FRESH || z.state == OB_TESTED);
        }
     }

   if(!v.displacement_valid || !ind.internalStructureFound || !v.sweep_valid || !v.bos_valid)
     {
      v.state = SMC_WAIT;
      v.failure_reason = ind.reason;
      return v;
     }

   if(!v.invalidation_clear)
     {
      v.state = SMC_INVALIDATED;
      v.failure_reason = "Structural invalidation level breached";
      return v;
     }

   if(!v.freshness_valid)
     {
      v.state = SMC_STALE;
      v.failure_reason = "BOS/sweep chain is stale";
      return v;
     }

   if(!v.regime_applicable)
     {
      v.state = SMC_WAIT;
      v.failure_reason = "Market regime undefined";
      return v;
     }

   if(!v.htf_structure_valid)
     {
      v.state = SMC_INVALID;
      v.failure_reason = genuineHtf ? (forBuy ? "HTF structure is not bullish" : "HTF structure is not bearish") : "Trend context is not a genuine higher timeframe";
      return v;
     }

   if(!v.premium_discount_valid)
     {
      v.state = SMC_INVALID;
      v.failure_reason = forBuy ? "BUY is outside validated discount location"
                                : "SELL is outside validated premium location";
      return v;
     }

   if(!v.fvg_causal && !v.order_block_causal)
     {
      v.state = SMC_WAIT;
      v.failure_reason = "No causal entry FVG or order block linked to the confirming BOS";
      return v;
     }

   v.structural_valid = true;
   v.state = SMC_VALID;
   v.failure_reason = "Structural SMC chain validated";
   return v;
  }

#endif
//+------------------------------------------------------------------+
