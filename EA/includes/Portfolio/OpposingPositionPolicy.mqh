//+------------------------------------------------------------------+
//| Portfolio/OpposingPositionPolicy.mqh                              |
//| Pure, fail-closed policy for independent long/short exposure.     |
//+------------------------------------------------------------------+
#ifndef OPPOSINGPOSITIONPOLICY_MQH
#define OPPOSINGPOSITIONPOLICY_MQH

// Returns true only when the position/order direction is opposite to the
// requested market direction. Unknown order types are not inferred as a side;
// the caller's account-mode guard remains responsible for unsupported exposure.
bool MidasIsOpposingPositionDirection(ENUM_ORDER_TYPE desiredType,
                                     ENUM_POSITION_TYPE existingType)
  {
   if(desiredType!=ORDER_TYPE_BUY && desiredType!=ORDER_TYPE_SELL)
      return false;

   if(existingType==POSITION_TYPE_BUY)
      return desiredType==ORDER_TYPE_SELL;
   if(existingType==POSITION_TYPE_SELL)
      return desiredType==ORDER_TYPE_BUY;
   return false;
  }

bool MidasIsOpposingOrderDirection(ENUM_ORDER_TYPE desiredType,
                                   ENUM_ORDER_TYPE existingType)
  {
   if(desiredType!=ORDER_TYPE_BUY && desiredType!=ORDER_TYPE_SELL)
      return false;

   bool existingBuy=(existingType==ORDER_TYPE_BUY ||
                     existingType==ORDER_TYPE_BUY_LIMIT ||
                     existingType==ORDER_TYPE_BUY_STOP ||
                     existingType==ORDER_TYPE_BUY_STOP_LIMIT);
   bool existingSell=(existingType==ORDER_TYPE_SELL ||
                      existingType==ORDER_TYPE_SELL_LIMIT ||
                      existingType==ORDER_TYPE_SELL_STOP ||
                      existingType==ORDER_TYPE_SELL_STOP_LIMIT);

   if(!existingBuy && !existingSell)
      return false;
   return (desiredType==ORDER_TYPE_BUY ? existingSell : existingBuy);
  }

// This tests permission policy only. The production caller must still apply
// account-wide, per-symbol, correlation-group, daily-loss and execution guards.
// A netting/exchange account cannot retain independent opposing same-symbol
// positions, even when an operator attempts to enable the input.
bool MidasConcurrentOpposingPolicyAllows(ENUM_ACCOUNT_MARGIN_MODE accountMode,
                                         bool hasOpposingExposure,
                                         bool explicitlyEnabled,
                                         string &reasonOut)
  {
   reasonOut="";
   if(!hasOpposingExposure)
      return true;

   if(accountMode!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      reasonOut="MT5 netting/exchange accounts cannot retain independent opposing positions on the same symbol";
      return false;
     }

   if(!explicitlyEnabled)
     {
      reasonOut="opposing same-symbol exposure exists; InpAllowConcurrentOpposingPositions must be explicitly enabled";
      return false;
     }

   return true;
  }

#endif
//+------------------------------------------------------------------+
