//+------------------------------------------------------------------+
//|                                            Analysis/TFContext.mqh |
//+------------------------------------------------------------------+
#ifndef TFCONTEXT_MQH
#define TFCONTEXT_MQH

#include "../Core/Config.mqh"
#include "../Core/CandleData.mqh"
#include "../Structure/SwingDetector.mqh"
#include "../Structure/BOS.mqh"
#include "../Structure/CHOCH.mqh"
#include "../SmartMoney/FVG.mqh"
#include "../SmartMoney/Liquidity.mqh"
#include "../SmartMoney/SupportResistance.mqh"
#include "../SmartMoney/VolumeEngine.mqh"
#include "../SmartMoney/FibonacciEngine.mqh"
#include "../SmartMoney/ValueAreaEngine.mqh"
#include "../SmartMoney/OrderBlock.mqh"
#include "TrendEngine.mqh"

// One full SMC detection pipeline, scoped to a single timeframe. Building
// this was the actual fix for "real per-timeframe BOS/liquidity/FVG" —
// previously every concept ran on whatever timeframe the chart happened
// to be on, so labeling a signal "H4 BOS" while running on M15 would have
// been a lie. Each CTFContext owns its own candle series for its own TF.
class CTFContext
  {
private:
   datetime          m_lastBarTime;

public:
   ENUM_TIMEFRAMES   tf;
   CCandleData       candles;
   CSwingDetector    swings;
   CBOS              bos;
   CCHOCH            choch;
   CFVG              fvg;
   CLiquidity        liquidity;
   CSupportResistance sr;
   CTrendEngine      trend;
   CVolumeEngine     volume;
   CFibonacciEngine  fibonacci;
   CValueAreaEngine  valueArea;
   COrderBlock       orderBlock;

   bool              Init(string symbol, ENUM_TIMEFRAMES timeframe, int maxBars,
                          int swingStrength, double fvgMinSizeATR, double liqThresholdATR,
                          int rvolLookback = 20, int vaLookbackBars = 100, int vaNumBins = 24,
                          double vaPercent = 0.70, double obDisplacementATRMult = 1.5, double obMinBodyRatio = 0.5);
   void              Detect(bool force = false);
  };
//+------------------------------------------------------------------+
bool CTFContext::Init(string symbol, ENUM_TIMEFRAMES timeframe, int maxBars,
                      int swingStrength, double fvgMinSizeATR, double liqThresholdATR,
                      int rvolLookback, int vaLookbackBars, int vaNumBins, double vaPercent,
                      double obDisplacementATRMult, double obMinBodyRatio)
  {
   tf = timeframe;
   m_lastBarTime = 0;
   if(!candles.Init(symbol, tf, maxBars))
      return false;
   swings.SetParameters(&candles, swingStrength);
   bos.Init(&swings, &candles);
   choch.Init(&swings, &candles);
   fvg.Init(&candles, fvgMinSizeATR);
   liquidity.Init(&candles, &swings, liqThresholdATR);
   sr.Init(&candles, &swings);
   trend.Init(&swings, &bos, &choch, &candles);
   volume.Init(&candles, rvolLookback);
   fibonacci.Init(&swings, &candles);
   valueArea.Init(&candles, vaLookbackBars, vaNumBins, vaPercent);
   orderBlock.Init(&candles, &bos, obDisplacementATRMult, obMinBodyRatio);
   return true;
  }
//+------------------------------------------------------------------+
void CTFContext::Detect(bool force)
  {
   datetime barTime = iTime(candles.Symbol(), tf, 0);
   if(!force && barTime != 0 && barTime == m_lastBarTime)
      return;
   m_lastBarTime = barTime;

   candles.Refresh();
   if(!candles.IsReady()) return;
   swings.Detect();
   bos.Detect();
   choch.Detect();
   fvg.Detect();
   fvg.UpdateAllStates();
   liquidity.Detect();
   sr.Detect();
   valueArea.Compute();
   orderBlock.Detect();
  }
//+------------------------------------------------------------------+
#define TFPOOL_MAX 8

// Dedupes contexts by timeframe. If the pool is exhausted, Get() now
// fails closed instead of silently returning an unrelated timeframe.
// Returning the wrong context is materially worse than refusing startup:
// it can make an H4 analysis read M15 data while all labels still claim H4.
class CTFContextPool
  {
private:
   CTFContext*       m_ctx[TFPOOL_MAX];
   int               m_count;
   string            m_symbol;
   int               m_maxBars;
   int               m_swingStrength;
   double            m_fvgMinSizeATR;
   double            m_liqThresholdATR;
   int               m_rvolLookback;
   int               m_vaLookbackBars;
   int               m_vaNumBins;
   double            m_vaPercent;
   double            m_obDisplacementATRMult;
   double            m_obMinBodyRatio;

public:
                     CTFContextPool();
                    ~CTFContextPool();
   void              Configure(string symbol, int maxBars, int swingStrength,
                               double fvgMinSizeATR, double liqThresholdATR, int rvolLookback = 20,
                               int vaLookbackBars = 100, int vaNumBins = 24, double vaPercent = 0.70,
                               double obDisplacementATRMult = 1.5, double obMinBodyRatio = 0.5);
   CTFContext*       Get(ENUM_TIMEFRAMES tf);
   void              DetectAll(bool force = false);
  };
//+------------------------------------------------------------------+
CTFContextPool::CTFContextPool() : m_count(0), m_rvolLookback(20), m_vaLookbackBars(100),
                                    m_vaNumBins(24), m_vaPercent(0.70),
                                    m_obDisplacementATRMult(1.5), m_obMinBodyRatio(0.5)
  {
   for(int i = 0; i < TFPOOL_MAX; i++) m_ctx[i] = NULL;
  }
CTFContextPool::~CTFContextPool()
  {
   for(int i = 0; i < m_count; i++)
      if(m_ctx[i] != NULL) delete m_ctx[i];
  }
//+------------------------------------------------------------------+
void CTFContextPool::Configure(string symbol, int maxBars, int swingStrength,
                               double fvgMinSizeATR, double liqThresholdATR, int rvolLookback,
                               int vaLookbackBars, int vaNumBins, double vaPercent,
                               double obDisplacementATRMult, double obMinBodyRatio)
  {
   m_symbol = symbol;
   m_maxBars = maxBars;
   m_swingStrength = swingStrength;
   m_fvgMinSizeATR = fvgMinSizeATR;
   m_liqThresholdATR = liqThresholdATR;
   m_rvolLookback = MathMax(5, rvolLookback);
   m_vaLookbackBars = MathMax(10, vaLookbackBars);
   m_vaNumBins = MathMax(5, vaNumBins);
   m_vaPercent = (vaPercent > 0.0 && vaPercent < 1.0) ? vaPercent : 0.70;
   m_obDisplacementATRMult = (obDisplacementATRMult > 0) ? obDisplacementATRMult : 1.5;
   m_obMinBodyRatio = (obMinBodyRatio > 0 && obMinBodyRatio <= 1.0) ? obMinBodyRatio : 0.5;
  }
//+------------------------------------------------------------------+
CTFContext* CTFContextPool::Get(ENUM_TIMEFRAMES tf)
  {
   for(int i = 0; i < m_count; i++)
      if(m_ctx[i] != NULL && m_ctx[i].tf == tf)
         return m_ctx[i];

   if(m_count >= TFPOOL_MAX)
     {
      Print("MedisTouch: TFContextPool exhausted (", TFPOOL_MAX,
            " unique timeframes) — refusing to substitute an unrelated context.");
      return NULL;
     }
   CTFContext* c = new CTFContext();
   if(!c.Init(m_symbol, tf, m_maxBars, m_swingStrength, m_fvgMinSizeATR, m_liqThresholdATR, m_rvolLookback,
             m_vaLookbackBars, m_vaNumBins, m_vaPercent, m_obDisplacementATRMult, m_obMinBodyRatio))
     {
      Print("MedisTouch: failed to init TFContext for timeframe ", EnumToString(tf));
      delete c;
      return NULL;
     }
   m_ctx[m_count++] = c;
   return c;
  }
//+------------------------------------------------------------------+
void CTFContextPool::DetectAll(bool force)
  {
   for(int i = 0; i < m_count; i++)
      if(m_ctx[i] != NULL)
         m_ctx[i].Detect(force);
  }
#endif
//+------------------------------------------------------------------+
