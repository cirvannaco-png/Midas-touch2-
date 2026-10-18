//+------------------------------------------------------------------+
//| Analysis/OrderFlowDiagnostics.mqh                                 |
//| Diagnostic-only order-flow proxies. Never a trade signal by itself|
//+------------------------------------------------------------------+
#ifndef ORDER_FLOW_DIAGNOSTICS_MQH
#define ORDER_FLOW_DIAGNOSTICS_MQH

enum ENUM_OF_DATA_QUALITY
  {
   OF_QUALITY_UNAVAILABLE=0,
   OF_QUALITY_PROXY_ONLY=1
  };

struct OrderFlowSnapshot
  {
   ENUM_OF_DATA_QUALITY quality;
   int tick_count;
   double signed_tick_pressure;
   int positive_tick_count; // count of upward-mid ticks, not traded volume
   int negative_tick_count; // count of downward-mid ticks, not traded volume
   double pressure_ratio;       // [-1, +1], not exchange delta
   double price_progress;
   bool bullish_sweep_reclaim;
   bool bearish_sweep_reclaim;
   bool absorption_proxy;
   bool exhaustion_proxy;
   bool data_stale;
   bool pressure_progress_divergence;
   int continuation_hypothesis; // -1 bearish, 0 none, +1 bullish
   int reversal_hypothesis;     // -1 bearish, 0 none, +1 bullish
   bool auction_context_available;
   double value_area_poc;
   double value_area_vah;
   double value_area_val;
   double value_area_source_quality;
   int value_area_source;
   int auction_location; // -2 below VAL, -1 in value below POC, 0 near POC, +1 in value above POC, +2 above VAH, 9 unavailable
   datetime first_tick_time;
   datetime last_tick_time;
   long first_tick_time_msc;
   long last_tick_time_msc;
  };

class COrderFlowDiagnostics
  {
private:
   int      m_min_ticks;
   double   m_pressure_threshold;
   double   m_small_progress_atr;
   int      m_max_tick_age_seconds;

   double Clamp(double value,double low,double high)
     {
      return MathMax(low,MathMin(high,value));
     }

public:
                     COrderFlowDiagnostics()
     {
      m_min_ticks=8;
      m_pressure_threshold=0.60;
      m_small_progress_atr=0.15;
      m_max_tick_age_seconds=30;
     }

   void Configure(int minTicks,double pressureThreshold,
                  double smallProgressATR,int maxTickAgeSeconds)
     {
      m_min_ticks=(minTicks<3 ? 3 : minTicks);
      m_pressure_threshold=Clamp(pressureThreshold,0.10,0.95);
      m_small_progress_atr=Clamp(smallProgressATR,0.01,1.0);
      m_max_tick_age_seconds=(maxTickAgeSeconds<1 ? 1 : maxTickAgeSeconds);
     }

   // Attach existing value-profile levels to the diagnostic snapshot. The
   // location label is context only; it is not acceptance/rejection by itself.
   void AttachAuctionContext(double poc,double vah,double val,
                             double sourceQuality,int source,double close,
                             OrderFlowSnapshot &out)
     {
      out.auction_context_available=false;
      out.value_area_poc=0.0;
      out.value_area_vah=0.0;
      out.value_area_val=0.0;
      out.value_area_source_quality=0.0;
      out.value_area_source=0;
      out.auction_location=9;
      if(!MathIsValidNumber(poc) || !MathIsValidNumber(vah) ||
         !MathIsValidNumber(val) || !MathIsValidNumber(sourceQuality) ||
         !MathIsValidNumber(close) || poc<=0.0 || vah<=0.0 || val<=0.0 ||
         close<=0.0 || val>poc || poc>vah || sourceQuality<=0.0 || source<=0)
         return;
      out.auction_context_available=true;
      out.value_area_poc=poc;
      out.value_area_vah=vah;
      out.value_area_val=val;
      out.value_area_source_quality=sourceQuality;
      out.value_area_source=source;
      double pocTolerance=(vah-val)*0.01;
      if(close>vah)
         out.auction_location=2;
      else if(close<val)
         out.auction_location=-2;
      else if(MathAbs(close-poc)<=pocTolerance)
         out.auction_location=0;
      else if(close<poc)
         out.auction_location=-1;
      else
         out.auction_location=1;
     }

   // Inputs must be chronological (oldest to newest) and from one bounded
   // decision window. This computes tick-direction pressure, NOT true
   // aggressor-side volume or centralized futures footprint delta.
   bool Analyze(const MqlTick &ticks[],int count,
                double priorHigh,double priorLow,
                double barHigh,double barLow,double barClose,
                double atr,OrderFlowSnapshot &out)
     {
      out.quality=OF_QUALITY_UNAVAILABLE;
      out.tick_count=0;
      out.signed_tick_pressure=0.0;
      out.positive_tick_count=0;
      out.negative_tick_count=0;
      out.pressure_ratio=0.0;
      out.price_progress=0.0;
      out.bullish_sweep_reclaim=false;
      out.bearish_sweep_reclaim=false;
      out.absorption_proxy=false;
      out.exhaustion_proxy=false;
      out.data_stale=true;
      out.pressure_progress_divergence=false;
      out.continuation_hypothesis=0;
      out.reversal_hypothesis=0;
      out.auction_context_available=false;
      out.value_area_poc=0.0;
      out.value_area_vah=0.0;
      out.value_area_val=0.0;
      out.value_area_source_quality=0.0;
      out.value_area_source=0;
      out.auction_location=9;
      out.first_tick_time=0;
      out.last_tick_time=0;
      out.first_tick_time_msc=0;
      out.last_tick_time_msc=0;

      if(count<m_min_ticks || atr<=0.0 || priorHigh<=priorLow)
         return false;

      int valid=0;
      double firstMid=0.0,lastMid=0.0;
      int positive=0,negative=0;
      double previousMid=0.0;
      long previousTimeMsc=0;

      for(int i=0;i<count;i++)
        {
         double bid=ticks[i].bid;
         double ask=ticks[i].ask;
         if(bid<=0.0 || ask<=0.0 || ask<bid ||
            (ticks[i].time<=0 && ticks[i].time_msc<=0))
            continue;
         long tickTimeMsc=(ticks[i].time_msc>0 ? ticks[i].time_msc : (long)ticks[i].time*1000);
         if(tickTimeMsc<=0)
            continue;
         double mid=(bid+ask)*0.5;
         if(valid==0)
           {
            firstMid=mid;
            out.first_tick_time=(ticks[i].time>0 ? ticks[i].time : (datetime)(tickTimeMsc/1000));
            out.first_tick_time_msc=tickTimeMsc;
           }
         else
           {
            if(tickTimeMsc<previousTimeMsc)
               return false; // refuse unordered ticks; no silent sorting
            double delta=mid-previousMid;
            // Each price-changing quote contributes one unit. This is a
            // deliberately conservative tick-direction proxy, not volume.
            if(delta>0.0) positive++;
            else if(delta<0.0) negative++;
           }
         previousMid=mid;
         previousTimeMsc=tickTimeMsc;
         lastMid=mid;
         out.last_tick_time=(ticks[i].time>0 ? ticks[i].time : (datetime)(tickTimeMsc/1000));
         out.last_tick_time_msc=tickTimeMsc;
         valid++;
        }

      if(valid<m_min_ticks)
         return false;

      out.tick_count=valid;
      out.positive_tick_count=positive;
      out.negative_tick_count=negative;
      double directional=positive+negative;
      out.pressure_ratio=(directional>0.0 ? (positive-negative)/directional : 0.0);
      out.signed_tick_pressure=positive-negative;
      out.price_progress=lastMid-firstMid;
      out.quality=OF_QUALITY_PROXY_ONLY;

      datetime now=TimeCurrent();
      out.data_stale=(now>0 && out.last_tick_time>0 &&
                      (now-out.last_tick_time)>m_max_tick_age_seconds);

      // Sweep-and-reclaim uses the supplied completed-bar OHLC and prior
      // levels. Call only after the bar closes to avoid intrabar repainting.
      out.bullish_sweep_reclaim=(barLow<priorLow && barClose>priorLow);
      out.bearish_sweep_reclaim=(barHigh>priorHigh && barClose<priorHigh);

      bool lowProgress=(MathAbs(out.price_progress)<=atr*m_small_progress_atr);
      bool strongPressure=(MathAbs(out.pressure_ratio)>=m_pressure_threshold);
      out.absorption_proxy=(lowProgress && strongPressure &&
                            (barLow<=priorLow+atr*m_small_progress_atr ||
                             barHigh>=priorHigh-atr*m_small_progress_atr));

      // Exhaustion proxy: extended bar with low tick-direction pressure.
      // This flags a condition for review; it does not predict reversal.
      double range=barHigh-barLow;
      out.exhaustion_proxy=(range>=atr*2.0 &&
                            MathAbs(out.pressure_ratio)<0.20);

      // Explicit, research-only tags derived from completed-bar evidence.
      // They are hypotheses for outcome analysis, never entry instructions.
      out.pressure_progress_divergence=
         ((out.pressure_ratio>=m_pressure_threshold && out.price_progress<0.0) ||
          (out.pressure_ratio<=-m_pressure_threshold && out.price_progress>0.0));
      out.continuation_hypothesis=0;
      if(barClose>priorHigh && out.pressure_ratio>=m_pressure_threshold &&
         out.price_progress>0.0)
         out.continuation_hypothesis=1;
      else if(barClose<priorLow && out.pressure_ratio<=-m_pressure_threshold &&
              out.price_progress<0.0)
         out.continuation_hypothesis=-1;

      out.reversal_hypothesis=0;
      if(out.bullish_sweep_reclaim && out.pressure_ratio>0.0)
         out.reversal_hypothesis=1;
      else if(out.bearish_sweep_reclaim && out.pressure_ratio<0.0)
         out.reversal_hypothesis=-1;
      return true;
     }
  };

#endif // ORDER_FLOW_DIAGNOSTICS_MQH
