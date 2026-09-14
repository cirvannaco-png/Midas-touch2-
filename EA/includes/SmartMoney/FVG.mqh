//+------------------------------------------------------------------+
//|                                                SmartMoney/FVG.mqh |
//+------------------------------------------------------------------+
#ifndef FVG_MQH
#define FVG_MQH

#include "../Core/Config.mqh"
#include "../Core/CandleData.mqh"

class CFVG
  {
private:
   CCandleData*      m_candles;
   FVGZone           m_zones[];
   int               m_zoneCount;

   double            m_minSizeATR;

   void              UpdateState(FVGZone &zone);

public:
                     CFVG();
   void              Init(CCandleData* candleData, double minSizeATR = 0.1);
   void              Detect();
   int               Count() const { return m_zoneCount; }
   FVGZone           GetZone(int i) const;
   void              UpdateAllStates();
  };
//+------------------------------------------------------------------+
CFVG::CFVG() : m_candles(NULL), m_zoneCount(0), m_minSizeATR(0.1) {}
void CFVG::Init(CCandleData* candleData, double minSizeATR)
  {
   m_candles = candleData;
   m_minSizeATR = minSizeATR;
  }
//+------------------------------------------------------------------+
void CFVG::Detect()
  {
   m_zoneCount = 0;
   if(m_candles == NULL) return;
   ArrayFree(m_zones);
   int total = m_candles.Total();
   // A 3-candle FVG needs three completed candles. With series indexing,
   // shift 0 is forming, so the newest usable triplet is shifts 3,2,1.
   if(total < 4) return;

   // Scan newest completed triplets first. The newest candle in each
   // triplet is shift i-2 and must remain >= 1; this guarantees that a
   // forming candle can never create or resize an FVG.
   for(int i = 3; i < total; i++)
     {
      CandleData cd0 = m_candles.GetCandle(i - 2); // newest, completed
      CandleData cd1 = m_candles.GetCandle(i - 1); // middle, completed
      CandleData cd2 = m_candles.GetCandle(i);     // oldest, completed
      double atr = cd1.atr;
      if(atr <= 0) continue;

      if(cd0.low > cd2.high)
        {
         double gap = cd0.low - cd2.high;
         if(gap >= m_minSizeATR * atr)
           {
            FVGZone zone;
            zone.time = cd1.time;
            zone.top = cd0.low;
            zone.bottom = cd2.high;
            zone.dir = FVG_BULL;
            zone.state = FVG_FRESH;
            zone.width = gap / atr;
            zone.bar_index = i - 1;
            int n = m_zoneCount++;
            ArrayResize(m_zones, m_zoneCount);
            m_zones[n] = zone;
           }
        }
      else if(cd0.high < cd2.low)
        {
         double gap = cd2.low - cd0.high;
         if(gap >= m_minSizeATR * atr)
           {
            FVGZone zone;
            zone.time = cd1.time;
            zone.top = cd2.low;
            zone.bottom = cd0.high;
            zone.dir = FVG_BEAR;
            zone.state = FVG_FRESH;
            zone.width = gap / atr;
            zone.bar_index = i - 1;
            int n = m_zoneCount++;
            ArrayResize(m_zones, m_zoneCount);
            m_zones[n] = zone;
           }
        }
     }
  }
//+------------------------------------------------------------------+
void CFVG::UpdateAllStates()
  {
   for(int i = 0; i < m_zoneCount; i++)
      UpdateState(m_zones[i]);
  }
//+------------------------------------------------------------------+
void CFVG::UpdateState(FVGZone &zone)
  {
   if(zone.state == FVG_MITIGATED || zone.state == FVG_INVALIDATED)
      return;
   int total = m_candles.Total();
   for(int bar = 1; bar < total; bar++)
     {
      CandleData cd = m_candles.GetCandle(bar);
      if(cd.time < zone.time)
         break;
      if(zone.dir == FVG_BULL)
        {
         if(cd.low <= zone.top && cd.high >= zone.bottom)
           {
            if(cd.close >= zone.top)
               zone.state = FVG_MITIGATED;
            else if(zone.state == FVG_FRESH)
               zone.state = FVG_TESTED;
           }
        }
      else
        {
         if(cd.high >= zone.bottom && cd.low <= zone.top)
           {
            if(cd.close <= zone.bottom)
               zone.state = FVG_MITIGATED;
            else if(zone.state == FVG_FRESH)
               zone.state = FVG_TESTED;
           }
        }
     }
  }
//+------------------------------------------------------------------+
FVGZone CFVG::GetZone(int i) const
  {
   FVGZone empty;
   ZeroMemory(empty);
   if(i < 0 || i >= m_zoneCount) return empty;
   return m_zones[i];
  }
#endif
//+------------------------------------------------------------------+
