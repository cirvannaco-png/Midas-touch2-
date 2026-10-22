//+------------------------------------------------------------------+
//| Analysis/TopDownMTFEngine.mqh                                    |
//| Direction-agnostic D1 -> H4 -> H1 -> M30 -> M15 -> M5 -> M1     |
//| Confidence arbitration only: never creates or forces a trade.      |
//+------------------------------------------------------------------+
#ifndef TOPDOWNMTFENGINE_MQH
#define TOPDOWNMTFENGINE_MQH

#include "TFContext.mqh"

class CTopDownMTFEngine
  {
private:
   CTFContext* m_d1;
   CTFContext* m_h4;
   CTFContext* m_h1;
   CTFContext* m_m30;
   CTFContext* m_m15;
   CTFContext* m_m5;
   CTFContext* m_m1;
   double      m_maxConfidenceAdjustment;
   int         m_chochLookbackBars;
   bool        m_ready;
   double      m_longScore;
   double      m_shortScore;
   string      m_summary;

   double TrendStrength(const ENUM_TREND_STATE state) const;
   void AddContext(CTFContext* ctx,const double weight,
                   double &longScore,double &shortScore) const;
   double ClampScore(const double value) const;

public:
   CTopDownMTFEngine();
   bool Init(CTFContext* d1,CTFContext* h4,CTFContext* h1,
             CTFContext* m30,CTFContext* m15,CTFContext* m5,CTFContext* m1);
   void Configure(const double maxConfidenceAdjustment=8.0,
                  const int chochLookbackBars=8);
   bool Evaluate();
   bool IsReady() const { return m_ready; }
   double LongScore() const { return m_longScore; }
   double ShortScore() const { return m_shortScore; }
   double AdjustConfidence(const bool isBuy,const double rawConfidence) const;
   void AdjustSetup(TradeSetup &setup) const;
   string Summary() const { return m_summary; }
  };

CTopDownMTFEngine::CTopDownMTFEngine() :
   m_d1(NULL),m_h4(NULL),m_h1(NULL),m_m30(NULL),m_m15(NULL),m_m5(NULL),m_m1(NULL),
   m_maxConfidenceAdjustment(8.0),m_chochLookbackBars(8),m_ready(false),
   m_longScore(0.0),m_shortScore(0.0),m_summary("top-down context not evaluated")
  {
  }

bool CTopDownMTFEngine::Init(CTFContext* d1,CTFContext* h4,CTFContext* h1,
                             CTFContext* m30,CTFContext* m15,CTFContext* m5,CTFContext* m1)
  {
   if(d1==NULL || h4==NULL || h1==NULL || m30==NULL ||
      m15==NULL || m5==NULL || m1==NULL)
      return false;
   if(d1.tf!=PERIOD_D1 || h4.tf!=PERIOD_H4 || h1.tf!=PERIOD_H1 ||
      m30.tf!=PERIOD_M30 || m15.tf!=PERIOD_M15 ||
      m5.tf!=PERIOD_M5 || m1.tf!=PERIOD_M1)
      return false;
   m_d1=d1;
   m_h4=h4;
   m_h1=h1;
   m_m30=m30;
   m_m15=m15;
   m_m5=m5;
   m_m1=m1;
   m_ready=true;
   return true;
  }

void CTopDownMTFEngine::Configure(const double maxConfidenceAdjustment,
                                  const int chochLookbackBars)
  {
   // A confidence modifier is deliberately bounded; it is never a standalone
   // reason to create, invalidate, or force an order.
   m_maxConfidenceAdjustment=MathMax(0.0,MathMin(15.0,maxConfidenceAdjustment));
   m_chochLookbackBars=MathMax(1,MathMin(100,chochLookbackBars));
  }

double CTopDownMTFEngine::TrendStrength(const ENUM_TREND_STATE state) const
  {
   if(state==TREND_BULL_STRONG || state==TREND_BEAR_STRONG) return 1.0;
   if(state==TREND_BULL || state==TREND_BEAR) return 0.75;
   return 0.0;
  }

double CTopDownMTFEngine::ClampScore(const double value) const
  {
   if(!MathIsValidNumber(value)) return 0.0;
   return MathMax(0.0,MathMin(100.0,value));
  }

void CTopDownMTFEngine::AddContext(CTFContext* ctx,const double weight,
                                   double &longScore,double &shortScore) const
  {
   if(ctx==NULL || !ctx.candles.IsReady()) return;
   ENUM_TREND_STATE trend=ctx.trend.GetCurrentTrend();
   double strength=TrendStrength(trend);
   if(trend==TREND_BULL || trend==TREND_BULL_STRONG)
      longScore+=weight*strength;
   else if(trend==TREND_BEAR || trend==TREND_BEAR_STRONG)
      shortScore+=weight*strength;

   // A recent confirmed CHoCH can surface a genuine reversal candidate even
   // when the trend classification has not yet flipped. It modifies both
   // sides symmetrically and is limited to a small share of that TF's weight.
   if(ctx.choch.Count()>0)
     {
      CHOCHPoint change=ctx.choch.Get(0);
      int shift=iBarShift(ctx.candles.Symbol(),ctx.tf,change.time,false);
      if(shift>=0 && shift<=m_chochLookbackBars)
        {
         double reversalWeight=weight*0.15;
         if(change.bullish)
           {
            longScore+=reversalWeight;
            shortScore-=reversalWeight;
           }
         else
           {
            shortScore+=reversalWeight;
            longScore-=reversalWeight;
           }
        }
     }
  }

bool CTopDownMTFEngine::Evaluate()
  {
   m_ready=(m_d1!=NULL && m_h4!=NULL && m_h1!=NULL &&
            m_m30!=NULL && m_m15!=NULL && m_m5!=NULL && m_m1!=NULL);
   if(!m_ready) return false;
   if(!m_d1.candles.IsReady() || !m_h4.candles.IsReady() ||
      !m_h1.candles.IsReady() || !m_m30.candles.IsReady() ||
      !m_m15.candles.IsReady() || !m_m5.candles.IsReady() ||
      !m_m1.candles.IsReady())
     {
      m_ready=false;
      m_summary="top-down context unavailable: one or more timeframes lack sufficient history";
      return false;
     }

   double longScore=0.0,shortScore=0.0;
   // Weights sum to 100: higher timeframes establish context while entry
   // timeframes refine it. M1 is deliberately a small contributor, not the
   // authority to override a valid higher-timeframe thesis by itself.
   AddContext(m_d1,30.0,longScore,shortScore);
   AddContext(m_h4,24.0,longScore,shortScore);
   AddContext(m_h1,18.0,longScore,shortScore);
   AddContext(m_m30,10.0,longScore,shortScore);
   AddContext(m_m15,8.0,longScore,shortScore);
   AddContext(m_m5,6.0,longScore,shortScore);
   AddContext(m_m1,4.0,longScore,shortScore);
   m_longScore=ClampScore(longScore);
   m_shortScore=ClampScore(shortScore);
   m_summary=StringFormat("MTF long=%.1f short=%.1f [D1/H4/H1/M30/M15/M5/M1]",m_longScore,m_shortScore);
   m_ready=true;
   return true;
  }

double CTopDownMTFEngine::AdjustConfidence(const bool isBuy,const double rawConfidence) const
  {
   if(!m_ready || !MathIsValidNumber(rawConfidence))
      return ClampScore(rawConfidence);
   double directionalEdge=m_longScore-m_shortScore;
   if(!isBuy) directionalEdge=-directionalEdge;
   double adjusted=rawConfidence+m_maxConfidenceAdjustment*directionalEdge/100.0;
   return ClampScore(adjusted);
  }

void CTopDownMTFEngine::AdjustSetup(TradeSetup &setup) const
  {
   if(!setup.active) return;
   if(setup.type==ORDER_TYPE_BUY)
      setup.confidence=AdjustConfidence(true,setup.confidence);
   else if(setup.type==ORDER_TYPE_SELL)
      setup.confidence=AdjustConfidence(false,setup.confidence);
  }

#endif
//+------------------------------------------------------------------+
