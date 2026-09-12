//+------------------------------------------------------------------+
//|                                       Decision/TradeDecision.mqh |
//|  Shared record types for the analysis -> decision -> action seam. |
//+------------------------------------------------------------------+
#ifndef TRADEDECISION_MQH
#define TRADEDECISION_MQH

#include "../Core/Config.mqh"

enum ENUM_TRADE_POLICY
  {
   POLICY_IGNORE = 0,
   POLICY_SIGNAL_ONLY,
   POLICY_EXECUTE_ONLY,
   POLICY_EXECUTE_AND_SIGNAL
  };

string TradePolicyToString(ENUM_TRADE_POLICY p)
  {
   switch(p)
     {
      case POLICY_SIGNAL_ONLY:        return "SIGNAL_ONLY";
      case POLICY_EXECUTE_ONLY:       return "EXECUTE_ONLY";
      case POLICY_EXECUTE_AND_SIGNAL: return "EXECUTE_AND_SIGNAL";
      default:                        return "IGNORE";
     }
  }

struct TradeDecisionRecord
  {
   long              decision_id;
   string            symbol;
   TradeSetup        setup;
   ENUM_TRADE_POLICY action;
   bool              reduce_risk;
   bool              valid;
   double            confidence;
   double            spread_points;
   datetime          decided_time;
   string            reason;
  };

struct ExecutionRecord
  {
   long              decision_id;
   double            volume;
   ulong             ticket;
   datetime          submitted_time;
  };

#endif
//+------------------------------------------------------------------+
