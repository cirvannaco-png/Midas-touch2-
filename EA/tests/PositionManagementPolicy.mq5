#property strict
#include "../includes/Execution/PositionManagementPolicy.mqh"

int failures=0;
void AssertTrue(bool condition,string name)
  {
   if(!condition) { PrintFormat("FAIL: %s",name); failures++; }
   else PrintFormat("PASS: %s",name);
  }

int OnInit()
  {
   AssertTrue(ShouldTakePartialAtR(TS_FILLED,2.0,2.0),"filled position reaches partial target without a trailing-stop edit");
   AssertTrue(ShouldTakePartialAtR(TS_PROTECTED,2.5,2.0),"protected position reaches partial target");
   AssertTrue(!ShouldTakePartialAtR(TS_FILLED,1.99,2.0),"partial close does not occur below target");
   AssertTrue(!ShouldTakePartialAtR(TS_PARTIAL,3.0,2.0),"partial position cannot enter first partial path twice");
   AssertTrue(!ShouldTakePartialAtR(TS_RUNNER,3.0,2.0),"runner is not eligible for the first partial close");
   AssertTrue(!ShouldTakePartialAtR(TS_FILLED,3.0,0.0),"invalid partial target fails closed");
   AssertTrue(!ShouldTakePartialAtR(TS_FILLED,NAN,2.0),"non-finite R multiple fails closed");
   PrintFormat("PositionManagementPolicy tests: %d failure(s)",failures);
   return failures==0 ? INIT_SUCCEEDED : INIT_FAILED;
  }
