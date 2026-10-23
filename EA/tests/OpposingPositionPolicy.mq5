//+------------------------------------------------------------------+
//| OpposingPositionPolicy.mq5                                        |
//| Deterministic policy tests; no account login or market orders.    |
//+------------------------------------------------------------------+
#property strict
#property version "1.00"

#include "../includes/Portfolio/OpposingPositionPolicy.mqh"

int failures=0;

void AssertTrue(bool condition,string name)
  {
   if(!condition)
     {
      PrintFormat("FAIL: %s",name);
      failures++;
     }
   else
      PrintFormat("PASS: %s",name);
  }

void TestPositionDirectionMatrix()
  {
   AssertTrue(MidasIsOpposingPositionDirection(ORDER_TYPE_BUY,POSITION_TYPE_SELL),
              "BUY candidate recognizes existing SELL position as opposite");
   AssertTrue(MidasIsOpposingPositionDirection(ORDER_TYPE_SELL,POSITION_TYPE_BUY),
              "SELL candidate recognizes existing BUY position as opposite");
   AssertTrue(!MidasIsOpposingPositionDirection(ORDER_TYPE_BUY,POSITION_TYPE_BUY),
              "BUY candidate does not misclassify existing BUY position");
   AssertTrue(!MidasIsOpposingPositionDirection(ORDER_TYPE_SELL,POSITION_TYPE_SELL),
              "SELL candidate does not misclassify existing SELL position");

   AssertTrue(MidasIsOpposingOrderDirection(ORDER_TYPE_BUY,ORDER_TYPE_SELL_LIMIT),
              "BUY candidate recognizes pending SELL limit");
   AssertTrue(MidasIsOpposingOrderDirection(ORDER_TYPE_SELL,ORDER_TYPE_BUY_STOP),
              "SELL candidate recognizes pending BUY stop");
   AssertTrue(MidasIsOpposingOrderDirection(ORDER_TYPE_BUY,ORDER_TYPE_SELL_STOP_LIMIT),
              "BUY candidate recognizes pending SELL stop-limit");
   AssertTrue(!MidasIsOpposingOrderDirection(ORDER_TYPE_BUY,ORDER_TYPE_BUY_LIMIT),
              "BUY candidate does not treat same-side BUY limit as opposing");
   AssertTrue(!MidasIsOpposingOrderDirection(ORDER_TYPE_SELL,ORDER_TYPE_SELL_STOP),
              "SELL candidate does not treat same-side SELL stop as opposing");
  }

void TestAccountModeAndExplicitEnableMatrix()
  {
   string reason="stale";
   AssertTrue(MidasConcurrentOpposingPolicyAllows(ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
                                                   false,false,reason),
              "hedging account without opposing exposure remains eligible when disabled");
   AssertTrue(reason=="","allowed no-opposing case clears stale block reason");

   reason="";
   AssertTrue(!MidasConcurrentOpposingPolicyAllows(ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
                                                    true,false,reason),
              "hedging account blocks opposite exposure by default");
   AssertTrue(StringFind(reason,"explicitly enabled")>=0,
              "default-disabled hedge emits actionable diagnostic");

   reason="";
   AssertTrue(MidasConcurrentOpposingPolicyAllows(ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
                                                   true,true,reason),
              "retail-hedging account permits opposite exposure only when enabled");

   reason="";
   AssertTrue(!MidasConcurrentOpposingPolicyAllows(ACCOUNT_MARGIN_MODE_RETAIL_NETTING,
                                                    true,true,reason),
              "retail-netting account blocks independent opposing positions even when enabled");
   AssertTrue(StringFind(reason,"netting/exchange")>=0,
              "retail-netting rejection explains account limitation");

   reason="";
   AssertTrue(!MidasConcurrentOpposingPolicyAllows(ACCOUNT_MARGIN_MODE_EXCHANGE,
                                                    true,true,reason),
              "exchange account blocks independent opposing positions even when enabled");

   reason="";
   AssertTrue(MidasConcurrentOpposingPolicyAllows(ACCOUNT_MARGIN_MODE_RETAIL_NETTING,
                                                   false,true,reason),
              "opposing-policy check alone does not invent an opposing position");
  }

int OnInit()
  {
   TestPositionDirectionMatrix();
   TestAccountModeAndExplicitEnableMatrix();
   PrintFormat("OpposingPositionPolicy tests: %d failure(s)",failures);
   return failures==0 ? INIT_SUCCEEDED : INIT_FAILED;
  }
//+------------------------------------------------------------------+
