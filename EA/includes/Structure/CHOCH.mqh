//+------------------------------------------------------------------+
//|                                                 Structure/CHOCH.mqh |
//+------------------------------------------------------------------+
#ifndef CHOCH_MQH
#define CHOCH_MQH

#include "../Core/Config.mqh"
#include "../Core/CandleData.mqh"
#include "SwingDetector.mqh"

class CCHOCH
  {
private:
   CSwingDetector*   m_swings;
   CCandleData*      m_candles;
   CHOCHPoint        m_choch[];
   int               m_count;

public:
                     CCHOCH();
   void              Init(CSwingDetector* swings, CCandleData* candles);
   void              Detect();
   int               Count() const { return m_count; }
   CHOCHPoint        Get(int i) const;
  };
//+------------------------------------------------------------------+
CCHOCH::CCHOCH() : m_swings(NULL), m_candles(NULL), m_count(0) {}
void CCHOCH::Init(CSwingDetector* swings, CCandleData* candles)
  {
   m_swings = swings;
   m_candles = candles;
  }
//+------------------------------------------------------------------+
void CCHOCH::Detect()
  {
   m_count = 0;
   if(m_swings == NULL || m_candles == NULL) return;
   ArrayResize(m_choch, 2);

   CHOCHPoint bull, bear;
   ZeroMemory(bull);
   ZeroMemory(bear);
   bool haveBull = false, haveBear = false;

   // Bearish -> Bullish CHoCH: a confirmed lower high is broken by a
   // completed candle. Shift 0 is deliberately excluded: a forming bar
   // must never manufacture a structure-shift event.
   int highCount = m_swings.HighCount();
   if(highCount >= 2)
     {
      for(int i = 0; i < highCount - 1; i++)
        {
         SwingPoint curr = m_swings.GetHigh(i);
         SwingPoint prev = m_swings.GetHigh(i + 1);
         if(curr.price < prev.price)
           {
            for(int bar = curr.bar_index - 1; bar >= 1; bar--)
              {
               CandleData cd = m_candles.GetCandle(bar);
               if(cd.close > curr.price)
                 {
                  bull.time = cd.time;
                  bull.price = curr.price;
                  bull.bullish = true;
                  bull.bar_index = bar;
                  haveBull = true;
                  break;
                 }
              }
            break;
           }
        }
     }

   // Bullish -> Bearish CHoCH: a confirmed higher low is broken by a
   // completed candle. Shift 0 is deliberately excluded for causality.
   int lowCount = m_swings.LowCount();
   if(lowCount >= 2)
     {
      for(int i = 0; i < lowCount - 1; i++)
        {
         SwingPoint curr = m_swings.GetLow(i);
         SwingPoint prev = m_swings.GetLow(i + 1);
         if(curr.price > prev.price)
           {
            for(int bar = curr.bar_index - 1; bar >= 1; bar--)
              {
               CandleData cd = m_candles.GetCandle(bar);
               if(cd.close < curr.price)
                 {
                  bear.time = cd.time;
                  bear.price = curr.price;
                  bear.bullish = false;
                  bear.bar_index = bar;
                  haveBear = true;
                  break;
                 }
              }
            break;
           }
        }
     }

   if(haveBull && haveBear)
     {
      if(bull.bar_index <= bear.bar_index)
        {
         m_choch[0] = bull;
         m_choch[1] = bear;
        }
      else
        {
         m_choch[0] = bear;
         m_choch[1] = bull;
        }
      m_count = 2;
     }
   else if(haveBull)
     {
      m_choch[0] = bull;
      m_count = 1;
     }
   else if(haveBear)
     {
      m_choch[0] = bear;
      m_count = 1;
     }
   ArrayResize(m_choch, m_count);
  }
//+------------------------------------------------------------------+
CHOCHPoint CCHOCH::Get(int i) const
  {
   CHOCHPoint empty;
   ZeroMemory(empty);
   if(i < 0 || i >= m_count) return empty;
   return m_choch[i];
  }
#endif
//+------------------------------------------------------------------+
