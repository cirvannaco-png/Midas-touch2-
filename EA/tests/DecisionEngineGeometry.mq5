//+------------------------------------------------------------------+
//| EA/tests/DecisionEngineGeometry.mq5                               |
//| Compile/run harness for the decision-boundary setup invariants.    |
//+------------------------------------------------------------------+
#property strict

#include "../includes/Decision/DecisionEngine.mqh"

bool ExpectIgnored(CDecisionEngine &engine, TradeSetup &setup, string label)
  {
   TradeDecisionRecord rec=engine.Decide(setup);
   if(rec.action!=POLICY_IGNORE || rec.valid)
     {
      Print("FAIL: ",label," action=",TradePolicyToString(rec.action)," valid=",rec.valid," reason=",rec.reason);
      return false;
     }
   return true;
  }

bool ExpectAccepted(CDecisionEngine &engine, TradeSetup &setup, string label)
  {
   TradeDecisionRecord rec=engine.Decide(setup);
   if(rec.action==POLICY_IGNORE || !rec.valid || rec.decision_id<=0)
     {
      Print("FAIL: ",label," action=",TradePolicyToString(rec.action)," valid=",rec.valid," reason=",rec.reason);
      return false;
     }
   return true;
  }

TradeSetup MakeBuySetup()
  {
   TradeSetup s;
   ZeroMemory(s);
   s.type=ORDER_TYPE_BUY;
   s.entry_top=101.0;
   s.entry_bottom=100.0;
   s.invalidation=99.0;
   s.stop_loss=98.5;
   s.tp1=102.0;
   s.tp2=103.0;
   s.final_tp=104.0;
   s.confidence=90.0;
   s.active=true;
   s.reasons.regime=REGIME_TRENDING;
   return s;
  }

void OnStart()
  {
   CDecisionEngine engine;
   engine.Init(_Symbol,false,true,60.0,60.0,80.0,0);

   bool ok=true;
   TradeSetup valid=MakeBuySetup();
   ok=ExpectAccepted(engine,valid,"valid buy geometry") && ok;

   TradeSetup stopCrosses=MakeBuySetup();
   stopCrosses.stop_loss=99.5;
   ok=ExpectIgnored(engine,stopCrosses,"stop crosses thesis invalidation") && ok;

   TradeSetup invalidationInside=MakeBuySetup();
   invalidationInside.invalidation=100.5;
   ok=ExpectIgnored(engine,invalidationInside,"invalidation inside entry zone") && ok;

   TradeSetup targetsReversed=MakeBuySetup();
   targetsReversed.tp2=101.5;
   ok=ExpectIgnored(engine,targetsReversed,"targets not monotonic") && ok;

   TradeSetup badConfidence=MakeBuySetup();
   badConfidence.confidence=101.0;
   ok=ExpectIgnored(engine,badConfidence,"confidence outside range") && ok;

   if(!ok) ExpertRemove();
   else Print("PASS: decision setup geometry invariants");
  }
//+------------------------------------------------------------------+
