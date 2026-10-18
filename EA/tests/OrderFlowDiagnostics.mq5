#property strict
#include "../includes/Analysis/OrderFlowDiagnostics.mqh"

int g_failures=0;

void AssertTrue(bool condition,string name)
  {
   if(!condition)
     {
      PrintFormat("FAIL: %s",name);
      g_failures++;
     }
   else
      PrintFormat("PASS: %s",name);
  }

void FillTicks(double &midpoints[],MqlTick &ticks[])
  {
   int count=ArraySize(midpoints);
   ArrayResize(ticks,count);
   // Fixed epoch keeps unit fixtures deterministic in Strategy Tester agents
   // where TimeCurrent/TimeLocal may be unavailable during OnInit.
   datetime base=(datetime)1700000000;
   base-=count+2;
   for(int i=0;i<count;i++)
     {
      ZeroMemory(ticks[i]);
      ticks[i].time=base+i;
      ticks[i].time_msc=(long)ticks[i].time*1000+(long)i*17;
      ticks[i].bid=midpoints[i]-0.0001;
      ticks[i].ask=midpoints[i]+0.0001;
     }
  }

int OnInit()
  {
   COrderFlowDiagnostics engine;
   engine.Configure(8,0.60,0.15,30);
   MqlTick ticks[];
   OrderFlowSnapshot snapshot;

   double bullish[8]={1.10000,1.10010,1.10020,1.10030,1.10040,1.10050,1.10060,1.10070};
   FillTicks(bullish,ticks);
   bool ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                          1.10100,1.09900,1.10050,0.00100,snapshot);
   AssertTrue(ok,"bullish tick window is accepted");
   if(ok)
     {
      AssertTrue(snapshot.quality==OF_QUALITY_PROXY_ONLY,"valid window is labelled proxy-only");
      AssertTrue(snapshot.pressure_ratio>0.99 && snapshot.positive_tick_count==7,
                 "upward midpoint changes produce positive pressure");
      AssertTrue(snapshot.continuation_hypothesis==0,
                 "no continuation tag without a completed breakout");
     }

   double bearish[8]={1.10070,1.10060,1.10050,1.10040,1.10030,1.10020,1.10010,1.10000};
   FillTicks(bearish,ticks);
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10100,1.09900,1.09950,0.00100,snapshot);
   AssertTrue(ok && snapshot.pressure_ratio<-0.99 && snapshot.negative_tick_count==7,
              "downward midpoint changes produce negative pressure");

   double neutral[8]={1.10000,1.10000,1.10000,1.10000,1.10000,1.10000,1.10000,1.10000};
   FillTicks(neutral,ticks);
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10100,1.09900,1.10000,0.00100,snapshot);
   AssertTrue(ok && snapshot.pressure_ratio==0.0 && snapshot.signed_tick_pressure==0.0,
              "unchanged midpoint has neutral pressure");

   FillTicks(bullish,ticks);
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10000,1.09750,1.09900,0.00100,snapshot);
   AssertTrue(ok && snapshot.bullish_sweep_reclaim && snapshot.reversal_hypothesis==1,
              "bullish sweep-and-reclaim is a separate research hypothesis");

   FillTicks(bearish,ticks);
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10250,1.10000,1.10100,0.00100,snapshot);
   AssertTrue(ok && snapshot.bearish_sweep_reclaim && snapshot.reversal_hypothesis==-1,
              "bearish sweep-and-reclaim is a separate research hypothesis");

   FillTicks(bullish,ticks);
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10300,1.10000,1.10250,0.00100,snapshot);
   AssertTrue(ok && snapshot.continuation_hypothesis==1,
              "bullish breakout with aligned pressure gets continuation tag");

   FillTicks(bearish,ticks);
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10000,1.09700,1.09750,0.00100,snapshot);
   AssertTrue(ok && snapshot.continuation_hypothesis==-1,
              "bearish breakout with aligned pressure gets continuation tag");

   double absorption[8]={1.10000,1.10001,1.10002,1.10003,1.10004,1.10005,1.10006,1.09900};
   FillTicks(absorption,ticks);
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10100,1.09850,1.09950,0.01000,snapshot);
   AssertTrue(ok && snapshot.absorption_proxy,
              "low progress with strong tick pressure near range edge flags absorption proxy");
   AssertTrue(ok && snapshot.pressure_progress_divergence,
              "pressure/progress disagreement is tagged separately");

   FillTicks(neutral,ticks);
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10300,1.09800,1.10000,0.00100,snapshot);
   AssertTrue(ok && snapshot.exhaustion_proxy,
              "extended bar with weak pressure flags exhaustion proxy");

   FillTicks(bullish,ticks);
   ticks[3].time_msc=ticks[2].time_msc-1;
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10100,1.09900,1.10050,0.00100,snapshot);
   AssertTrue(!ok && snapshot.quality==OF_QUALITY_UNAVAILABLE,
              "unordered tick history fails closed");

   double shortWindow[7]={1.10000,1.10010,1.10020,1.10030,1.10040,1.10050,1.10060};
   FillTicks(shortWindow,ticks);
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10100,1.09900,1.10050,0.00100,snapshot);
   AssertTrue(!ok,"insufficient valid tick history is rejected");

   FillTicks(bullish,ticks);
   ok=engine.Analyze(ticks,ArraySize(ticks)+1,1.10200,1.09800,
                     1.10100,1.09900,1.10050,0.00100,snapshot);
   AssertTrue(!ok,"tick count greater than array size is rejected");

   FillTicks(bullish,ticks);
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10100,1.09900,1.10200,0.00100,snapshot);
   AssertTrue(!ok,"OHLC close outside bar range is rejected");

   FillTicks(bullish,ticks);
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10100,1.09900,1.10050,0.00100,snapshot);
   if(ok)
     {
      engine.AttachAuctionContext(1.10000,1.10200,1.09800,0.90,1,1.10300,snapshot);
      AssertTrue(snapshot.auction_context_available && snapshot.auction_location==2,
                 "auction context identifies close above VAH");
      engine.AttachAuctionContext(1.10000,1.10200,1.09800,0.0,1,1.10300,snapshot);
      AssertTrue(!snapshot.auction_context_available && snapshot.auction_location==9,
                 "invalid profile source quality fails closed");
     }
   else
      AssertTrue(false,"auction context fixture has valid pressure input");

   // Replay tests pin time to the closed-window boundary, not wall-clock time.
   FillTicks(bullish,ticks);
   datetime evaluationTime=ticks[ArraySize(ticks)-1].time+1;
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10100,1.09900,1.10050,0.00100,snapshot,evaluationTime);
   AssertTrue(ok && !snapshot.data_stale,
              "fresh ticks are classified against the closed-window boundary");
   double replayPressure=snapshot.pressure_ratio;
   bool replayStale=snapshot.data_stale;
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10100,1.09900,1.10050,0.00100,snapshot,evaluationTime);
   AssertTrue(ok && snapshot.pressure_ratio==replayPressure && snapshot.data_stale==replayStale,
              "same tick window and evaluation time replay deterministically");

   FillTicks(bullish,ticks);
   evaluationTime=ticks[ArraySize(ticks)-1].time+1;
   ticks[ArraySize(ticks)-1].time_msc=(long)(evaluationTime+1)*1000;
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10100,1.09900,1.10050,0.00100,snapshot,evaluationTime);
   AssertTrue(!ok,"ticks after the closed-window boundary are rejected to prevent look-ahead");

   engine.Configure(8,0.60,0.15,5);
   FillTicks(bullish,ticks);
   evaluationTime=ticks[ArraySize(ticks)-1].time+60;
   ok=engine.Analyze(ticks,ArraySize(ticks),1.10200,1.09800,
                     1.10100,1.09900,1.10050,0.00100,snapshot,evaluationTime);
   AssertTrue(ok && snapshot.data_stale,
              "staleness is deterministic relative to the evaluation boundary");
   engine.Configure(8,0.60,0.15,30);

   PrintFormat("OrderFlowDiagnostics tests: %d failure(s)",g_failures);
   return g_failures==0 ? INIT_SUCCEEDED : INIT_FAILED;
  }
