//+------------------------------------------------------------------+
//| DynamicStopEngine.mq5                                             |
//| Deterministic policy tests; no broker orders are submitted.       |
//+------------------------------------------------------------------+
#property strict
#define MIDAS_DYNAMIC_STOP_TESTING
#include "../includes/Execution/DynamicStopEngine.mqh"
#include "../includes/Execution/PriceGridNormalizer.mqh"

int failures=0;
string g_traceSummary="";

void AssertTrue(bool condition,string name)
  {
   if(!condition)
     { PrintFormat("FAIL: %s",name); failures++; }
   else PrintFormat("PASS: %s",name);
  }

void AssertNear(double actual,double expected,double tolerance,string name)
  { AssertTrue(MathAbs(actual-expected)<=tolerance,name); }

void TraceDecision(const string &label,const DynamicStopDecision &d)
  {
   g_traceSummary+=StringFormat("%s[m=%d stage=%d sl=%.10f reason=%s];",
                                label,(int)d.modify,(int)d.stage,d.proposedSL,d.reason);
  }

void TestPriceGridNormalization()
  {
   double normalized=0.0;
   AssertTrue(NormalizePriceToTickGrid(1.10346,0.00005,5,false,normalized),
              "BUY stop normalization accepts valid tick grid");
   AssertNear(normalized,1.10345,0.00000001,
              "BUY stop rounds down to tick without moving closer to market");

   AssertTrue(NormalizePriceToTickGrid(1.10346,0.00005,5,true,normalized),
              "SELL stop normalization accepts valid tick grid");
   AssertNear(normalized,1.10350,0.00000001,
              "SELL stop rounds up to tick without moving closer to market");

   AssertTrue(NormalizePriceToTickGrid(1.10350,0.00005,5,false,normalized),
              "already-aligned price accepted when rounding down");
   AssertNear(normalized,1.10350,0.00000001,
              "already-aligned price remains unchanged");

   AssertTrue(NormalizePriceToTickGrid(2345.17,0.25,2,false,normalized),
              "coarse metal/index tick accepts BUY stop");
   AssertNear(normalized,2345.00,0.001,
              "coarse BUY stop rounds down to tradable tick");
   AssertTrue(NormalizePriceToTickGrid(2345.17,0.25,2,true,normalized),
              "coarse metal/index tick accepts SELL stop");
   AssertNear(normalized,2345.25,0.001,
              "coarse SELL stop rounds up to tradable tick");

   AssertTrue(!NormalizePriceToTickGrid(1.10346,0.0,5,false,normalized),
              "missing tick size fails closed");
   AssertTrue(!NormalizePriceToTickGrid(0.0,0.00005,5,false,normalized),
              "non-positive price fails closed");
   AssertTrue(!NormalizePriceToTickGrid(1.10346,0.00005,9,false,normalized),
              "unsupported digit precision fails closed");
  }

void TestDynamicStop()
  {
   CDynamicStopEngine engine;
   DynamicStopConfig cfg; cfg.SetDefaults();
   cfg.minImprovementPts=0.0;
   engine.Configure(cfg);

   // 1R definition: entry 100, structural SL 99 => 1R = 1 price unit.
   // Below +0.75R the structural stop must remain untouched.
   DynamicStopDecision d=engine.Evaluate(_Symbol,true,100.0,99.0,99.0,100.50,1.0,0.0);
   TraceDecision("case-1",d);
   AssertTrue(!d.modify && d.stage==DSE_STRUCTURAL,"BUY below 0.75R retains structural SL");

   // The production entry point must fail closed if terminal symbol metadata is unavailable.
   DynamicStopDecision missingGeometry=engine.Evaluate("MidasMissingSymbolZZQ",true,
                                                        100.0,99.0,99.0,100.75,0.25,0.0);
   AssertTrue(!missingGeometry.modify &&
              missingGeometry.reason=="broker stops/freeze distance protection",
              "production path refuses modification without broker point metadata");

   // +0.75R activates protection.
   d=engine.EvaluateForTest(_Symbol,true,100.0,99.0,99.0,100.75,0.25,0.0,0.0,0.00001);
   TraceDecision("case-2",d);
   AssertTrue(d.modify && d.proposedSL>99.0,"BUY +0.75R activates protection");

   // +1R cannot leave the stop on the losing side of entry.
   d=engine.EvaluateForTest(_Symbol,true,100.0,99.0,99.0,101.0,0.10,0.0,0.0,0.00001);
   TraceDecision("case-3",d);
   AssertTrue(d.modify && d.proposedSL>=100.0,"BUY +1R reaches at least breakeven");

   // Missing ATR cannot create a stop exactly at the current market price,
   // even where broker stop/freeze levels are zero.
   d=engine.EvaluateForTest(_Symbol,true,100.0,99.0,99.0,101.0,0.0,0.0,0.0,0.00001);
   TraceDecision("case-3a",d);
   AssertTrue(!d.modify && d.reason=="broker stops/freeze distance protection",
              "BUY missing ATR fails closed instead of proposing market-price SL");

   // SELL direction is independent and mirrored.
   d=engine.EvaluateForTest(_Symbol,false,100.0,101.0,101.0,99.25,0.25,0.0,0.0,0.00001);
   TraceDecision("case-4",d);
   AssertTrue(d.modify && d.proposedSL<101.0,"SELL +0.75R activates protection");
   d=engine.EvaluateForTest(_Symbol,false,100.0,101.0,101.0,99.0,0.10,0.0,0.0,0.00001);
   TraceDecision("case-5",d);
   AssertTrue(d.modify && d.proposedSL<=100.0,"SELL +1R reaches at least breakeven");

   d=engine.EvaluateForTest(_Symbol,false,100.0,101.0,101.0,99.0,0.0,0.0,0.0,0.00001);
   TraceDecision("case-5a",d);
   AssertTrue(!d.modify && d.reason=="broker stops/freeze distance protection",
              "SELL missing ATR fails closed instead of proposing market-price SL");

   // Existing stop must never widen.
   d=engine.EvaluateForTest(_Symbol,true,100.0,99.0,100.50,102.0,2.0,0.0,0.0,0.00001);
   TraceDecision("case-6",d);
   AssertTrue(!d.modify,"BUY never widens an existing tighter SL");
   d=engine.EvaluateForTest(_Symbol,false,100.0,101.0,99.50,98.0,2.0,0.0,0.0,0.00001);
   TraceDecision("case-7",d);
   AssertTrue(!d.modify,"SELL never widens an existing tighter SL");

   // Confirmed structural anchor takes precedence over ATR fallback.
   d=engine.EvaluateForTest(_Symbol,true,100.0,99.0,99.0,102.0,1.0,0.0,101.0,0.00001);
   TraceDecision("case-8",d);
   AssertTrue(d.modify && d.stage==DSE_TRAILING,"BUY confirmed anchor selects trailing stage");
   AssertNear(d.proposedSL,100.9,0.000001,"BUY anchor uses configured ATR buffer");
   d=engine.EvaluateForTest(_Symbol,false,100.0,101.0,101.0,98.0,1.0,0.0,99.0,0.00001);
   TraceDecision("case-9",d);
   AssertTrue(d.modify && d.stage==DSE_TRAILING,"SELL confirmed anchor selects trailing stage");
   AssertNear(d.proposedSL,99.1,0.000001,"SELL anchor uses configured ATR buffer");

   // Invalid anchor geometry must fall back deterministically to ATR.
   d=engine.EvaluateForTest(_Symbol,true,100.0,99.0,99.0,102.0,1.0,0.0,103.0,0.00001);
   TraceDecision("case-10",d);
   AssertTrue(d.modify && d.stage==DSE_TRAILING,"invalid BUY anchor falls back to ATR trailing at +2R");
   d=engine.EvaluateForTest(_Symbol,false,100.0,101.0,101.0,98.0,1.0,0.0,97.0,0.00001);
   TraceDecision("case-11",d);
   AssertTrue(d.modify && d.stage==DSE_TRAILING,"invalid SELL anchor falls back to ATR trailing at +2R");

   // Protection gates are fail-closed when explicitly configured.
   cfg.maxSpreadPoints=10;
   cfg.minATR=0.50;
   cfg.maxATR=2.00;
   engine.Configure(cfg);
   d=engine.Evaluate(_Symbol,true,100.0,99.0,99.0,101.0,1.0,11.0);
   TraceDecision("case-12",d);
   AssertTrue(!d.modify,"spread protection blocks modification");
   d=engine.Evaluate(_Symbol,true,100.0,99.0,99.0,101.0,0.25,5.0);
   TraceDecision("case-13",d);
   AssertTrue(!d.modify,"low-volatility protection blocks modification");
   d=engine.Evaluate(_Symbol,true,100.0,99.0,99.0,101.0,2.5,5.0);
   TraceDecision("case-14",d);
   AssertTrue(!d.modify,"high-volatility protection blocks modification");

   // Threshold suppression blocks a five-point improvement below the six-point minimum.
   cfg.maxSpreadPoints=0; cfg.minATR=0; cfg.maxATR=0; cfg.minImprovementPts=6.0;
   engine.Configure(cfg);
   d=engine.EvaluateForTest(_Symbol,true,1.1000,1.0900,1.10780,1.1080,0.00010,0.0,0.0,0.00001);
   TraceDecision("case-15",d);
   AssertTrue(!d.modify,"minimum-improvement threshold suppresses tiny change");
  }

int OnInit()
  {
   TestPriceGridNormalization();
   TestDynamicStop();
   PrintFormat("DynamicStopEngine tests: %d failure(s) | explicit test point override used for deterministic geometry | trace=%s",
               failures,g_traceSummary);
   return failures==0 ? INIT_SUCCEEDED : INIT_FAILED;
  }
