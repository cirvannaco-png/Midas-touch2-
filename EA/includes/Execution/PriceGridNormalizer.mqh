//+------------------------------------------------------------------+
//| Execution/PriceGridNormalizer.mqh                                |
//| Tick-grid normalization for protective SL/TP prices.              |
//+------------------------------------------------------------------+
#ifndef PRICEGRIDNORMALIZER_MQH
#define PRICEGRIDNORMALIZER_MQH

// Normalize a price to the symbol's tradable tick grid.
// roundUp=true is used for SELL protective stops and BUY take-profits.
// roundUp=false is used for BUY protective stops and SELL take-profits.
// Directional rounding never moves a stop/target closer to the market
// solely because a broker requires a coarser tick size.
bool NormalizePriceToTickGrid(const double rawPrice,
                              const double tickSize,
                              const int digits,
                              const bool roundUp,
                              double &normalizedPrice)
  {
   normalizedPrice=0.0;
   if(!MathIsValidNumber(rawPrice) || rawPrice<=0.0 ||
      !MathIsValidNumber(tickSize) || tickSize<=0.0 ||
      digits<0 || digits>8)
      return false;

   double units=rawPrice/tickSize;
   if(!MathIsValidNumber(units)) return false;

   // Scale epsilon to floating-point precision without using a material
   // fraction of a tick. This avoids moving an already-grid-aligned price
   // by a tick because of binary floating-point representation.
   double tolerance=MathMax(1e-9,MathAbs(units)*1.7763568394002505e-15);
   double gridUnits=roundUp ? MathCeil(units-tolerance) : MathFloor(units+tolerance);
   double gridPrice=gridUnits*tickSize;
   if(!MathIsValidNumber(gridPrice) || gridPrice<=0.0) return false;

   normalizedPrice=NormalizeDouble(gridPrice,digits);
   if(!MathIsValidNumber(normalizedPrice) || normalizedPrice<=0.0)
     {
      normalizedPrice=0.0;
      return false;
     }

   // Digits rounding must not undo directional tick rounding.
   double directionalTolerance=tickSize*1e-8;
   if(roundUp && normalizedPrice<rawPrice-directionalTolerance)
     {
      gridUnits+=1.0;
      normalizedPrice=NormalizeDouble(gridUnits*tickSize,digits);
     }
   else if(!roundUp && normalizedPrice>rawPrice+directionalTolerance)
     {
      gridUnits-=1.0;
      normalizedPrice=NormalizeDouble(gridUnits*tickSize,digits);
     }

   if(!MathIsValidNumber(normalizedPrice) || normalizedPrice<=0.0)
     {
      normalizedPrice=0.0;
      return false;
     }
   if(roundUp && normalizedPrice<rawPrice-directionalTolerance) return false;
   if(!roundUp && normalizedPrice>rawPrice+directionalTolerance) return false;
   return true;
  }

#endif
//+------------------------------------------------------------------+
