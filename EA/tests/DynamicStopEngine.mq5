//+------------------------------------------------------------------+
//| DynamicStopEngine.mq5                                             |
//| Deterministic policy tests; no broker orders are submitted.       |
//+------------------------------------------------------------------+
#property strict
#include "../includes/Execution/DynamicStopEngine.mqh"

int failures=0;
string g_traceSummary="";
string g_policySymbol="MidasTestStopPolicy";
bool g_testSymbolReady=false;
double g_testPoint=0.0;
int g_testStops=0,g_testFreeze=0,g_testDigits=0,g_testSelected=0,g_testSymbolError=0;

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

bool SetupSyntheticTestSymbol()
  {
   bool existsCustom=false;
   ResetLastError();
   bool exists=SymbolExist(g_policySymbol,existsCustom);
   if(exists && !existsCustom)
     {
      PrintFormat("DYNAMIC_STOP_TEST_SETUP_FAIL: %s exists but is not custom",g_policySymbol);
      return false;
     }
   if(!exists)
     {
      ResetLastError();
      if(!CustomSymbolCreate(g_policySymbol,"MidasTests",_Symbol))
        {
         int error=GetLastError();
         bool customAfterFailure=false;
         if(error!=5304 || !SymbolExist(g_policySymbol,customAfterFailure) || !customAfterFailure)
           {
            PrintFormat("DYNAMIC_STOP_TEST_SETUP_FAIL: CustomSymbolCreate error=%d",error);
            return false;
           }
        }
     }

   ResetLastError();
   bool ok=true;
   ok=CustomSymbolSetInteger(g_policySymbol,SYMBOL_DIGITS,4) && ok;
   ok=CustomSymbolSetInteger(g_policySymbol,SYMBOL_TRADE_STOPS_LEVEL,0) && ok;
   ok=CustomSymbolSetInteger(g_policySymbol,SYMBOL_TRADE_FREEZE_LEVEL,0) && ok;
   ok=CustomSymbolSetDouble(g_policySymbol,SYMBOL_POINT,0.0001) && ok;
   ok=CustomSymbolSetDouble(g_policySymbol,SYMBOL_TRADE_TICK_SIZE,0.0001) && ok;
   if(!ok)
     {
      PrintFormat("DYNAMIC_STOP_TEST_SETUP_FAIL: setting custom symbol properties error=%d",GetLastError());
      return false;
     }
   if(!SymbolSelect(g_policySymbol,true))
     {
      PrintFormat("DYNAMIC_STOP_TEST_SETUP_FAIL: SymbolSelect error=%d",GetLastError());
      return false;
     }

   double point=SymbolInfoDouble(g_policySymbol,SYMBOL_POINT);
   long digits=SymbolInfoInteger(g_policySymbol,SYMBOL_DIGITS);
   long stops=SymbolInfoInteger(g_policySymbol,SYMBOL_TRADE_STOPS_LEVEL);
   long freeze=SymbolInfoInteger(g_policySymbol,SYMBOL_TRADE_FREEZE_LEVEL);
   PrintFormat("DYNAMIC_STOP_TEST_SYMBOL symbol=%s point=%.10f digits=%d stops=%d freeze=%d",
               g_policySymbol,point,(int)digits,(int)stops,(int)freeze);
   return point==0.0001 && digits==4 && stops==0 && freeze==0;
  }

void TestDynamicStop()
  {
   g_testSymbolReady=SetupSyntheticTestSymbol();
   ResetLastError();
   g_testSelected=(int)SymbolSelect(g_policySymbol,true);
   g_testPoint=SymbolInfoDouble(g_policySymbol,SYMBOL_POINT);
   g_testDigits=(int)SymbolInfoInteger(g_policySymbol,SYMBOL_DIGITS);
   g_testStops=(int)SymbolInfoInteger(g_policySymbol,SYMBOL_TRADE_STOPS_LEVEL);
   g_testFreeze=(int)SymbolInfoInteger(g_policySymbol,SYMBOL_TRADE_FREEZE_LEVEL);
   g_testSymbolError=GetLastError();
   if(!g_testSymbolReady)
     {
      failures++;
      Print("DYNAMIC_STOP_TEST_SETUP_FAIL: synthetic broker geometry unavailable; policy assertions skipped.");
      return;
     }
   CDynamicStopEngine engine;
   DynamicStopConfig cfg; cfg.SetDefaults();
   cfg.minImprovementPts=0.0;
   engine.Configure(cfg);

   // 1R definition: entry 100, structural SL 99 => 1R = 1 price unit.
   // Below +0.75R the structural stop must remain untouched.
   DynamicStopDecision d=engine.Evaluate(g_policySymbol,true,100.0,99.0,99.0,100.50,1.0,0.0);
   TraceDecision("case-1",d);
   AssertTrue(!d.modify && d.stage==DSE_STRUCTURAL,"BUY below 0.75R retains structural SL");

   // +0.75R activates protection.
   d=engine.Evaluate(g_policySymbol,true,100.0,99.0,99.0,100.75,0.25,0.0,0.0,0.00001);
   TraceDecision("case-2",d);
   AssertTrue(d.modify && d.proposedSL>99.0,"BUY +0.75R activates protection");

   // +1R cannot leave the stop on the losing side of entry.
   d=engine.Evaluate(g_policySymbol,true,100.0,99.0,99.0,101.0,0.10,0.0,0.0,0.00001);
   TraceDecision("case-3",d);
   AssertTrue(d.modify && d.proposedSL>=100.0,"BUY +1R reaches at least breakeven");

   // SELL direction is independent and mirrored.
   d=engine.Evaluate(g_policySymbol,false,100.0,101.0,101.0,99.25,0.25,0.0,0.0,0.00001);
   TraceDecision("case-4",d);
   AssertTrue(d.modify && d.proposedSL<101.0,"SELL +0.75R activates protection");
   d=engine.Evaluate(g_policySymbol,false,100.0,101.0,101.0,99.0,0.10,0.0,0.0,0.00001);
   TraceDecision("case-5",d);
   AssertTrue(d.modify && d.proposedSL<=100.0,"SELL +1R reaches at least breakeven");

   // Existing stop must never widen.
   d=engine.Evaluate(g_policySymbol,true,100.0,99.0,100.50,102.0,2.0,0.0);
   TraceDecision("case-6",d);
   AssertTrue(!d.modify,"BUY never widens an existing tighter SL");
   d=engine.Evaluate(g_policySymbol,false,100.0,101.0,99.50,98.0,2.0,0.0);
   TraceDecision("case-7",d);
   AssertTrue(!d.modify,"SELL never widens an existing tighter SL");

   // Confirmed structural anchor takes precedence over ATR fallback.
   d=engine.Evaluate(g_policySymbol,true,100.0,99.0,99.0,102.0,1.0,0.0,101.0,0.00001);
   TraceDecision("case-8",d);
   AssertTrue(d.modify && d.stage==DSE_TRAILING,"BUY confirmed anchor selects trailing stage");
   AssertNear(d.proposedSL,100.9,0.000001,"BUY anchor uses configured ATR buffer");
   d=engine.Evaluate(g_policySymbol,false,100.0,101.0,101.0,98.0,1.0,0.0,99.0,0.00001);
   TraceDecision("case-9",d);
   AssertTrue(d.modify && d.stage==DSE_TRAILING,"SELL confirmed anchor selects trailing stage");
   AssertNear(d.proposedSL,99.1,0.000001,"SELL anchor uses configured ATR buffer");

   // Invalid anchor geometry must fall back deterministically to ATR.
   d=engine.Evaluate(g_policySymbol,true,100.0,99.0,99.0,102.0,1.0,0.0,103.0,0.00001);
   TraceDecision("case-10",d);
   AssertTrue(d.modify && d.stage==DSE_TRAILING,"invalid BUY anchor falls back to ATR trailing at +2R");
   d=engine.Evaluate(g_policySymbol,false,100.0,101.0,101.0,98.0,1.0,0.0,97.0,0.00001);
   TraceDecision("case-11",d);
   AssertTrue(d.modify && d.stage==DSE_TRAILING,"invalid SELL anchor falls back to ATR trailing at +2R");

   // Protection gates are fail-closed when explicitly configured.
   cfg.maxSpreadPoints=10;
   cfg.minATR=0.50;
   cfg.maxATR=2.00;
   engine.Configure(cfg);
   d=engine.Evaluate(g_policySymbol,true,100.0,99.0,99.0,101.0,1.0,11.0);
   TraceDecision("case-12",d);
   AssertTrue(!d.modify,"spread protection blocks modification");
   d=engine.Evaluate(g_policySymbol,true,100.0,99.0,99.0,101.0,0.25,5.0);
   TraceDecision("case-13",d);
   AssertTrue(!d.modify,"low-volatility protection blocks modification");
   d=engine.Evaluate(g_policySymbol,true,100.0,99.0,99.0,101.0,2.5,5.0);
   TraceDecision("case-14",d);
   AssertTrue(!d.modify,"high-volatility protection blocks modification");

   // Threshold suppression prevents pointless sub-point changes.
   cfg.maxSpreadPoints=0; cfg.minATR=0; cfg.maxATR=0; cfg.minImprovementPts=250000.0;
   engine.Configure(cfg);
   d=engine.Evaluate(g_policySymbol,true,100.0,99.0,99.0,101.0,0.10,0.0,0.0,0.00001);
   TraceDecision("case-15",d);
   AssertTrue(!d.modify,"minimum-improvement threshold suppresses tiny change");
  }

int OnInit()
  {
   TestDynamicStop();
   PrintFormat("DynamicStopEngine tests: %d failure(s) | symbol=%s selected=%d point=%.10f digits=%d stops=%d freeze=%d error=%d | trace=%s",
               failures,g_policySymbol,g_testSelected,g_testPoint,g_testDigits,g_testStops,g_testFreeze,
               g_testSymbolError,g_traceSummary);
   return failures==0 ? INIT_SUCCEEDED : INIT_FAILED;
  }
