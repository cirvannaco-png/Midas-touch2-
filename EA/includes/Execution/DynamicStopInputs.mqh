//+------------------------------------------------------------------+
//| Execution/DynamicStopInputs.mqh                                  |
//| Canonical EA-facing controls for Dynamic Stop Engine v1.          |
//+------------------------------------------------------------------+
#ifndef DYNAMICSTOPINPUTS_MQH
#define DYNAMICSTOPINPUTS_MQH

input group "Dynamic Stop Engine v1"
input bool   InpEnableDynamicStop = true;       // protect open positions after the initial structural SL
input double InpDynamicStopActivateAtR = 0.75;  // protection activates at +0.75R
input double InpDynamicStopBreakevenAtR = 1.00; // breakeven protection begins at +1R
input double InpDynamicStopATRMult = 1.50;      // ATR trailing distance
input double InpDynamicStopMinImprovementPoints = 2.0; // ignore insignificant SL changes
input int    InpDynamicStopMaxSpreadPoints = 0; // 0 = no additional modification spread gate
input double InpDynamicStopMinATR = 0.0;        // 0 = no volatility floor
input double InpDynamicStopMaxATR = 0.0;        // 0 = no volatility ceiling
input int    InpDynamicStopModifyIntervalSec = 5; // minimum seconds between successful SL changes per ticket

#endif
//+------------------------------------------------------------------+
