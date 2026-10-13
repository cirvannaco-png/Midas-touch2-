//+------------------------------------------------------------------+
//| Execution/PositionManagementPolicy.mqh                            |
//| Pure policy helpers for independently testable position handling. |
//+------------------------------------------------------------------+
#ifndef POSITIONMANAGEMENTPOLICY_MQH
#define POSITIONMANAGEMENTPOLICY_MQH

#include "TradeStateMachine.mqh"

// Partial profit-taking is an exit policy, not a side effect of trailing
// stop modification. A valid filled position can reach its partial target
// even when dynamic trailing is disabled or the broker rejects a stop edit.
// Recovery must restore the trade state and remaining volume before this
// policy is evaluated; this helper intentionally does not infer fills.
bool ShouldTakePartialAtR(ENUM_TRADE_STATE state,double r,double partialAtR)
  {
   if(!MathIsValidNumber(r) || !MathIsValidNumber(partialAtR)) return false;
   if(partialAtR<=0.0 || r<partialAtR) return false;
   return (state==TS_FILLED || state==TS_PROTECTED);
  }

#endif
//+------------------------------------------------------------------+
