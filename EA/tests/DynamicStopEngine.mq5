//+------------------------------------------------------------------+
//| DynamicStopEngine.mq5                                             |
//| Deterministic policy tests; no broker orders are submitted.       |
//+------------------------------------------------------------------+
#property strict
#include "../includes/Execution/DynamicStopEngine.mqh"

int failures=0;

void AssertTrue(bool condition,string name)
  {
   if(!condition)
     { PrintFormat("FAIL: %s",name); failures++; }
   else PrintFormat("PASS: %s",name);
  }

void AssertNear(double actual,double expected,double tolerance,string name)
  { AssertTrue(MathAbs(actual-expected)<=tolerance,name); }

void TestDynamicStop()
  {
   CDynamicStopEngine engine;
   DynamicStopConfig cfg; cfg.SetDefaults();
   cfg.minImprovementPts=0.0;
   engine.Configure(cfg);

   // 1R definition: entry 100, structural SL 99 => 1R = 1 price unit.
   // Below +0.75R the structural stop must remain untouched.
   DynamicStopDecision d=engine.Evaluate(_Symbol,true,100.0,99.0,99.0,100.50,1.0,0.0);
   AssertTrue(!d.modify && d.stage==DSE_STRUCTURAL,"BUY below 0.75R retains structural SL");

   // +0.75R activates protection.
   d=engine.Evaluate(_Symbol,true,100.0,99.0,99.0,100.75,0.25,0.0);
   AssertTrue(d.modify && d.proposedSL>99.0,"BUY +0.75R activates protection");

   // +1R cannot leave the stop on the losing side of entry.
   d=engine.Evaluate(_Symbol,true,100.0,99.0,99.0,101.0,0.10,0.0);
   AssertTrue(d.modify && d.proposedSL>=100.0,"BUY +1R reaches at least breakeven");

   // SELL direction is independent and mirrored.
   d=engine.Evaluate(_Symbol,false,100.0,101.0,101.0,99.25,0.25,0.0);
   AssertTrue(d.modify && d.proposedSL<101.0,"SELL +0.75R activates protection");
   d=engine.Evaluate(_Symbol,false,100.0,101.0,101.0,99.0,0.10,0.0);
   AssertTrue(d.modify && d.proposedSL<=100.0,"SELL +1R reaches at least breakeven");

   // Existing stop must never widen.
   d=engine.Evaluate(_Symbol,true,100.0,99.0,100.50,102.0,2.0,0.0);
   AssertTrue(!d.modify,"BUY never widens an existing tighter SL");
   d=engine.Evaluate(_Symbol,false,100.0,101.0,99.50,98.0,2.0,0.0);
   AssertTrue(!d.modify,"SELL never widens an existing tighter SL");

   // Protection gates are fail-closed when explicitly configured.
   cfg.maxSpreadPoints=10;
   cfg.minATR=0.50;
   cfg.maxATR=2.00;
   engine.Configure(cfg);
   d=engine.Evaluate(_Symbol,true,100.0,99.0,99.0,101.0,1.0,11.0);
   AssertTrue(!d.modify,"spread protection blocks modification");
   d=engine.Evaluate(_Symbol,true,100.0,99.0,99.0,101.0,0.25,5.0);
   AssertTrue(!d.modify,"low-volatility protection blocks modification");
   d=engine.Evaluate(_Symbol,true,100.0,99.0,99.0,101.0,2.5,5.0);
   AssertTrue(!d.modify,"high-volatility protection blocks modification");

   // Threshold suppression prevents pointless sub-point changes.
   cfg.maxSpreadPoints=0; cfg.minATR=0; cfg.maxATR=0; cfg.minImprovementPts=1000.0;
   engine.Configure(cfg);
   d=engine.Evaluate(_Symbol,true,100.0,99.0,99.0,101.0,0.10,0.0);
   AssertTrue(!d.modify,"minimum-improvement threshold suppresses tiny change");
  }

int OnInit()
  {
   TestDynamicStop();
   PrintFormat("DynamicStopEngine tests: %d failure(s)",failures);
   return failures==0 ? INIT_SUCCEEDED : INIT_FAILED;
  }
