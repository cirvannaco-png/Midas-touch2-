//+------------------------------------------------------------------+
//|                                    SmartMoney/ValueAreaEngine.mqh |
//+------------------------------------------------------------------+
#ifndef VALUEAREAENGINE_MQH
#define VALUEAREAENGINE_MQH

#include "../Core/Config.mqh"
#include "../Core/CandleData.mqh"

// Cross-asset Value Area / Volume Profile engine.
//
// Data hierarchy:
//   1. COPY_TICKS_TRADE + MqlTick.volume_real  -> real trade-by-price when
//      the connected feed actually exposes trade ticks and real volume.
//   2. COPY_TICKS_TRADE + MqlTick.volume       -> broker trade-tick profile.
//   3. MqlRates.real_volume                    -> real-volume bar proxy.
//   4. MqlRates.tick_volume                    -> broker tick-volume proxy.
//
// The engine is symbol-agnostic. It therefore supports exchange-listed
// futures/stocks/ETFs/indices when traded-volume data is available, and
// OTC/CFD/FX symbols when only broker volume data is available.
//
// It never labels a bar approximation as exchange trade volume.
//
// Trade-tick data is bounded to a recent 7-day window to prevent pathological
// CopyTicksRange allocations. Longer profile horizons use the best available
// bar volume source and record the provenance.
//
// The hard gate is contradiction-based, not "outside Value Area = reject":
// an accepted breakout above VAH can remain valid for a BUY, while a failed
// move above VAH can invalidate that BUY when the profile evidence is strong
// enough. Low-quality tick-volume proxies fail open.

#define VALUEAREA_TICK_PROFILE_MAX_DAYS 7

class CValueAreaEngine
  {
private:
   CCandleData*               m_candles;
   int                        m_lookbackBars;
   int                        m_numBins;
   double                     m_valueAreaPercent;
   int                        m_acceptanceBars;
   int                        m_rejectionLookbackBars;

   bool                       m_valid;
   double                     m_poc;
   double                     m_vah;
   double                     m_val;
   double                     m_pocMigrationATR;
   double                     m_sourceQuality;
   ENUM_VALUE_PROFILE_SOURCE  m_source;
   ENUM_VALUE_PROFILE_STATE   m_state;
   datetime                   m_lastBarTime;
   bool                       m_havePreviousPOC;

   int                        BinForPrice(double price, double rangeLow, double binSize) const;
   bool                       BuildTickProfile(double rangeLow, double binSize, double &volumes[]);
   bool                       BuildBarProfile(double rangeLow, double binSize, double &volumes[], ENUM_VALUE_PROFILE_SOURCE &source);
   void                       ComputeValueArea(double rangeLow, double binSize, double &volumes[]);
   void                       ComputeState();
   double                     ComputeSourceQuality() const;

public:
                              CValueAreaEngine();
   void                       Init(CCandleData* candles, int lookbackBars = 100, int numBins = 24, double valueAreaPercent = 0.70);
   void                       Compute(bool forceRecompute = false);

   bool                       IsValid() const { return m_valid; }
   double                     POC() const { return m_poc; }
   double                     VAH() const { return m_vah; }
   double                     VAL() const { return m_val; }
   double                     POCMigrationATR() const { return m_pocMigrationATR; }
   double                     SourceQuality() const { return m_sourceQuality; }
   ENUM_VALUE_PROFILE_SOURCE  Source() const { return m_source; }
   ENUM_VALUE_PROFILE_STATE   State() const { return m_state; }

   ENUM_VALUE_AREA_ZONE       Zone(double price) const;
   bool                       LocationOK(bool forBuy, double price) const;
   double                     Score(bool forBuy, double price) const;

   // True only when profile evidence actively contradicts this thesis.
   bool                       HardConflict(bool forBuy, double price) const;
  };

//+------------------------------------------------------------------+
CValueAreaEngine::CValueAreaEngine() :
   m_candles(NULL),
   m_lookbackBars(100),
   m_numBins(24),
   m_valueAreaPercent(0.70),
   m_acceptanceBars(3),
   m_rejectionLookbackBars(3),
   m_valid(false),
   m_poc(0.0),
   m_vah(0.0),
   m_val(0.0),
   m_pocMigrationATR(0.0),
   m_sourceQuality(0.0),
   m_source(VA_SOURCE_UNDEFINED),
   m_state(VA_STATE_UNDEFINED),
   m_lastBarTime(0),
   m_havePreviousPOC(false)
  {
  }

//+------------------------------------------------------------------+
void CValueAreaEngine::Init(CCandleData* candles, int lookbackBars, int numBins, double valueAreaPercent)
  {
   m_candles = candles;
   m_lookbackBars = MathMax(10, lookbackBars);
   m_numBins = MathMax(5, numBins);
   m_valueAreaPercent = (valueAreaPercent > 0.0 && valueAreaPercent < 1.0) ? valueAreaPercent : 0.70;
   m_acceptanceBars = 3;
   m_rejectionLookbackBars = 3;
   m_valid = false;
   m_poc = 0.0;
   m_vah = 0.0;
   m_val = 0.0;
   m_pocMigrationATR = 0.0;
   m_sourceQuality = 0.0;
   m_source = VA_SOURCE_UNDEFINED;
   m_state = VA_STATE_UNDEFINED;
   m_lastBarTime = 0;
   m_havePreviousPOC = false;
  }

//+------------------------------------------------------------------+
int CValueAreaEngine::BinForPrice(double price, double rangeLow, double binSize) const
  {
   if(binSize <= 0.0) return 0;
   int b = (int)((price - rangeLow) / binSize);
   return (int)MathMax(0, MathMin(m_numBins - 1, b));
  }

//+------------------------------------------------------------------+
bool CValueAreaEngine::BuildTickProfile(double rangeLow, double binSize, double &volumes[])
  {
   if(m_candles == NULL || m_candles.Total() < 2 || binSize <= 0.0)
      return false;

   int bars = MathMin(m_lookbackBars, m_candles.Total());
   datetime oldest = m_candles.GetCandle(bars - 1).time;
   datetime newest = m_candles.GetCandle(0).time;
   if(oldest <= 0 || newest <= 0)
      return false;

   long spanSeconds = (long)newest - (long)oldest;
   if(spanSeconds <= 0 || spanSeconds > (long)VALUEAREA_TICK_PROFILE_MAX_DAYS * 86400)
      return false;

   ulong fromMsc = (ulong)oldest * 1000;
   ulong toMsc = ((ulong)TimeCurrent() * 1000) + 999;

   MqlTick ticks[];
   int copied = CopyTicksRange(m_candles.Symbol(), ticks, COPY_TICKS_TRADE, fromMsc, toMsc);
   if(copied <= 0)
      return false;

   bool sawRealTradeVolume = false;
   bool sawBrokerTradeVolume = false;
   double totalObservedVolume = 0.0;

   for(int i = 0; i < copied; i++)
     {
      MqlTick tick = ticks[i];
      if((tick.flags & TICK_FLAG_LAST) == 0 || tick.last <= 0.0)
         continue;

      double volume = tick.volume_real;
      if(volume > 0.0)
         sawRealTradeVolume = true;
      else
         volume = (double)tick.volume;

      if(volume > 0.0)
         sawBrokerTradeVolume = true;
      else
         continue;

      int bin = BinForPrice(tick.last, rangeLow, binSize);
      volumes[bin] += volume;
      totalObservedVolume += volume;
     }

   if(totalObservedVolume <= 0.0)
      return false;

   if(sawRealTradeVolume)
      m_source = VA_SOURCE_REAL_TRADE_TICKS;
   else if(sawBrokerTradeVolume)
      m_source = VA_SOURCE_BROKER_TRADE_TICKS;
   else
      return false;

   return true;
  }

//+------------------------------------------------------------------+
bool CValueAreaEngine::BuildBarProfile(double rangeLow, double binSize, double &volumes[],
                                       ENUM_VALUE_PROFILE_SOURCE &source)
  {
   if(m_candles == NULL || binSize <= 0.0)
      return false;

   int bars = MathMin(m_lookbackBars, m_candles.Total());
   bool hasRealVolume = false;

   for(int i = 0; i < bars; i++)
     {
      if(m_candles.GetCandle(i).real_volume > 0)
        {
         hasRealVolume = true;
         break;
        }
     }

   source = hasRealVolume ? VA_SOURCE_REAL_VOLUME_BARS : VA_SOURCE_TICK_VOLUME_BARS;

   for(int i = 0; i < bars; i++)
     {
      CandleData cd = m_candles.GetCandle(i);
      double vol = hasRealVolume ? (double)cd.real_volume : (double)cd.tick_volume;
      if(vol <= 0.0)
         continue;

      if(cd.high <= cd.low)
        {
         volumes[BinForPrice(cd.close, rangeLow, binSize)] += vol;
         continue;
        }

      int startBin = BinForPrice(cd.low, rangeLow, binSize);
      int endBin = BinForPrice(cd.high, rangeLow, binSize);
      if(endBin < startBin)
        {
         int t = startBin;
         startBin = endBin;
         endBin = t;
        }

      int touched = endBin - startBin + 1;
      double volPerBin = vol / touched;

      for(int b = startBin; b <= endBin; b++)
         volumes[b] += volPerBin;
     }

   return true;
  }

//+------------------------------------------------------------------+
void CValueAreaEngine::ComputeValueArea(double rangeLow, double binSize, double &volumes[])
  {
   double totalVol = 0.0;
   int pocBin = 0;
   double pocVol = -1.0;

   for(int b = 0; b < m_numBins; b++)
     {
      totalVol += volumes[b];
      if(volumes[b] > pocVol)
        {
         pocVol = volumes[b];
         pocBin = b;
        }
     }

   if(totalVol <= 0.0 || pocVol <= 0.0)
     {
      m_valid = false;
      return;
     }

   int lowIdx = pocBin;
   int highIdx = pocBin;
   double cumVol = volumes[pocBin];
   double targetVol = totalVol * m_valueAreaPercent;

   while(cumVol < targetVol && (lowIdx > 0 || highIdx < m_numBins - 1))
     {
      double volBelow = (lowIdx > 0) ? volumes[lowIdx - 1] : -1.0;
      double volAbove = (highIdx < m_numBins - 1) ? volumes[highIdx + 1] : -1.0;

      if(volBelow < 0.0 && volAbove < 0.0)
         break;

      if(volBelow >= volAbove)
        {
         lowIdx--;
         cumVol += volumes[lowIdx];
        }
      else
        {
         highIdx++;
         cumVol += volumes[highIdx];
        }
     }

   double previousPOC = m_poc;
   bool hadPrevious = m_havePreviousPOC;

   m_poc = rangeLow + (pocBin + 0.5) * binSize;
   m_val = rangeLow + lowIdx * binSize;
   m_vah = rangeLow + (highIdx + 1) * binSize;

   double atr = m_candles.GetATR(0);
   if(hadPrevious && atr > 0.0)
      m_pocMigrationATR = (m_poc - previousPOC) / atr;
   else
      m_pocMigrationATR = 0.0;

   m_havePreviousPOC = true;
  }

//+------------------------------------------------------------------+
void CValueAreaEngine::ComputeState()
  {
   m_state = VA_STATE_BALANCED;

   if(!m_valid || m_candles == NULL)
     {
      m_state = VA_STATE_UNDEFINED;
      return;
     }

   int inspectBars = MathMin(m_candles.Total() - 1, m_acceptanceBars + 1);
   int maxRejectBars = MathMin(m_candles.Total() - 1, m_rejectionLookbackBars);
   double atr = m_candles.GetATR(1);
   double tolerance = (atr > 0.0) ? atr * 0.05 : 0.0;

   int above = 0;
   int below = 0;
   bool rejectedAbove = false;
   bool rejectedBelow = false;

   for(int shift = 1; shift <= inspectBars; shift++)
     {
      CandleData cd = m_candles.GetCandle(shift);
      if(cd.close > m_vah + tolerance) above++;
      if(cd.close < m_val - tolerance) below++;
     }

   for(int shift = 1; shift <= maxRejectBars; shift++)
     {
      CandleData cd = m_candles.GetCandle(shift);

      if(cd.high > m_vah + tolerance && cd.close <= m_vah + tolerance)
         rejectedAbove = true;

      if(cd.low < m_val - tolerance && cd.close >= m_val - tolerance)
         rejectedBelow = true;
     }

   if(rejectedAbove)
      m_state = VA_STATE_REJECTED_ABOVE;
   else if(rejectedBelow)
      m_state = VA_STATE_REJECTED_BELOW;
   else if(above >= m_acceptanceBars)
      m_state = VA_STATE_ACCEPTED_ABOVE;
   else if(below >= m_acceptanceBars)
      m_state = VA_STATE_ACCEPTED_BELOW;
  }

//+------------------------------------------------------------------+
double CValueAreaEngine::ComputeSourceQuality() const
  {
   switch(m_source)
     {
      case VA_SOURCE_REAL_TRADE_TICKS:   return 1.00;
      case VA_SOURCE_BROKER_TRADE_TICKS: return 0.85;
      case VA_SOURCE_REAL_VOLUME_BARS:   return 0.70;
      case VA_SOURCE_TICK_VOLUME_BARS:   return 0.50;
      default:                            return 0.00;
     }
  }

//+------------------------------------------------------------------+
void CValueAreaEngine::Compute(bool forceRecompute)
  {
   m_valid = false;

   if(m_candles == NULL || m_candles.Total() < 10)
      return;

   datetime barTime = m_candles.GetCandle(0).time;
   if(!forceRecompute && barTime == m_lastBarTime && m_poc != 0.0)
     {
      m_valid = true;
      return;
     }

   int bars = MathMin(m_lookbackBars, m_candles.Total());
   if(bars < 10)
      return;

   double rangeHigh = -DBL_MAX;
   double rangeLow = DBL_MAX;

   for(int i = 0; i < bars; i++)
     {
      CandleData cd = m_candles.GetCandle(i);
      if(cd.high > rangeHigh) rangeHigh = cd.high;
      if(cd.low < rangeLow) rangeLow = cd.low;
     }

   double range = rangeHigh - rangeLow;
   if(range <= 0.0)
      return;

   double binSize = range / m_numBins;
   if(binSize <= 0.0)
      return;

   double volumes[];
   ArrayResize(volumes, m_numBins);
   ArrayInitialize(volumes, 0.0);

   m_source = VA_SOURCE_UNDEFINED;
   bool built = BuildTickProfile(rangeLow, binSize, volumes);

   if(!built)
     {
      ArrayInitialize(volumes, 0.0);
      ENUM_VALUE_PROFILE_SOURCE fallbackSource = VA_SOURCE_UNDEFINED;
      built = BuildBarProfile(rangeLow, binSize, volumes, fallbackSource);
      m_source = fallbackSource;
     }

   if(!built)
      return;

   ComputeValueArea(rangeLow, binSize, volumes);
   if(!m_valid)
      return;

   m_sourceQuality = ComputeSourceQuality();
   m_valid = true;
   ComputeState();
   m_lastBarTime = barTime;
  }

//+------------------------------------------------------------------+
ENUM_VALUE_AREA_ZONE CValueAreaEngine::Zone(double price) const
  {
   if(!m_valid)
      return VA_ZONE_UNDEFINED;

   if(price > m_vah) return VA_ZONE_ABOVE;
   if(price < m_val) return VA_ZONE_BELOW;
   return VA_ZONE_INSIDE;
  }

//+------------------------------------------------------------------+
bool CValueAreaEngine::LocationOK(bool forBuy, double price) const
  {
   if(!m_valid)
      return true;

   ENUM_VALUE_AREA_ZONE z = Zone(price);

   if(forBuy)
      return (z == VA_ZONE_INSIDE || z == VA_ZONE_BELOW);

   return (z == VA_ZONE_INSIDE || z == VA_ZONE_ABOVE);
  }

//+------------------------------------------------------------------+
double CValueAreaEngine::Score(bool forBuy, double price) const
  {
   if(!m_valid || price <= 0.0)
      return 0.0;

   ENUM_VALUE_AREA_ZONE z = Zone(price);

   if(z == VA_ZONE_INSIDE)
     {
      double half = (m_vah - m_val) / 2.0;
      if(half <= 0.0)
         return 0.5;

      double distFromPOC = MathAbs(price - m_poc);
      return MathMax(0.5, MathMin(1.0, 1.0 - 0.5 * distFromPOC / half));
     }

   double atr = m_candles.GetATR(0);
   if(atr <= 0.0)
      return 0.0;

   if(forBuy)
     {
      if(z == VA_ZONE_BELOW)
        {
         double distATR = (m_val - price) / atr;
         return MathMax(0.0, MathMin(0.90, 0.90 * (1.0 - distATR / 2.0)));
        }

      if(z == VA_ZONE_ABOVE)
         return (m_state == VA_STATE_ACCEPTED_ABOVE) ? 0.65 : 0.0;
     }
   else
     {
      if(z == VA_ZONE_ABOVE)
        {
         double distATR = (price - m_vah) / atr;
         return MathMax(0.0, MathMin(0.90, 0.90 * (1.0 - distATR / 2.0)));
        }

      if(z == VA_ZONE_BELOW)
         return (m_state == VA_STATE_ACCEPTED_BELOW) ? 0.65 : 0.0;
     }

   return 0.0;
  }

//+------------------------------------------------------------------+
bool CValueAreaEngine::HardConflict(bool forBuy, double price) const
  {
   if(!m_valid || price <= 0.0 || m_sourceQuality < 0.70)
      return false;

   ENUM_VALUE_AREA_ZONE z = Zone(price);

   if(forBuy && z == VA_ZONE_ABOVE)
     {
      if(m_state == VA_STATE_REJECTED_ABOVE)
         return true;

      if(m_state != VA_STATE_ACCEPTED_ABOVE && m_pocMigrationATR <= -0.25)
         return true;
     }

   if(!forBuy && z == VA_ZONE_BELOW)
     {
      if(m_state == VA_STATE_REJECTED_BELOW)
         return true;

      if(m_state != VA_STATE_ACCEPTED_BELOW && m_pocMigrationATR >= 0.25)
         return true;
     }

   return false;
  }

#endif
//+------------------------------------------------------------------+
