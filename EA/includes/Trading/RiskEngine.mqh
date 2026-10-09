//+------------------------------------------------------------------+
//| Trading/RiskEngine.mqh                                           |
//| Stop-distance validation and account-currency position sizing.    |
//+------------------------------------------------------------------+
#ifndef RISKENGINE_MQH
#define RISKENGINE_MQH

#include "../Core/Config.mqh"

class CRiskEngine
  {
private:
   // Uses MT5's symbol-specific profit model rather than assuming
   // SYMBOL_TRADE_TICK_VALUE / TICK_SIZE is a complete loss model.
   bool              EstimateStopLossPerLot(string symbol,double entry,double stopLoss,double &lossPerLot);

public:
   bool              ValidateSetup(TradeSetup &setup,double minRR,double maxSLDistanceATR,double currentATR);
   bool              ValidateSetupAtEntry(const TradeSetup &setup,double entry,double minRR,double maxSLDistanceATR,double currentATR);
   double            CalculateLotSize(string symbol,double riskPercent,double entry,double stopLoss,
                                      bool halveForReducedRisk,bool allowMinLotOverride,bool &exceededRiskBudget,
                                      double sizeMultiplier=1.0);
   double            RiskAmountForLots(string symbol,double lots,double entry,double stopLoss);
  };

//+------------------------------------------------------------------+
// Estimate the account-currency loss for one lot if the proposed stop
// is reached. The stop side determines the intended direction here:
// below entry = buy stop; above entry = sell stop. ValidateSetup checks
// this geometry against the actual setup direction before execution.
// OrderCalcProfit includes the symbol's MT5 calculation mode and
// account-currency conversion; it does NOT include gap/slippage,
// commission, or swap, so portfolio risk remains a stop-based estimate.
//+------------------------------------------------------------------+
bool CRiskEngine::EstimateStopLossPerLot(string symbol,double entry,double stopLoss,double &lossPerLot)
  {
   lossPerLot=0.0;
   if(symbol=="" || !MathIsValidNumber(entry) || !MathIsValidNumber(stopLoss) ||
      entry<=0.0 || stopLoss<=0.0 || entry==stopLoss)
      return false;

   ENUM_ORDER_TYPE orderType=(stopLoss<entry ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   double estimatedProfit=0.0;
   ResetLastError();
   if(!OrderCalcProfit(orderType,symbol,1.0,entry,stopLoss,estimatedProfit))
      return false;
   if(!MathIsValidNumber(estimatedProfit) || estimatedProfit>=0.0)
      return false;

   lossPerLot=-estimatedProfit;
   return MathIsValidNumber(lossPerLot) && lossPerLot>0.0;
  }

//+------------------------------------------------------------------+
// Convert the requested equity-risk budget into lots. Volume is always
// rounded DOWN to the broker's step. If the risk budget cannot purchase
// the minimum lot, the default is to reject; the explicit override is
// surfaced through exceededRiskBudget. A zero/invalid budget can never
// be raised to minimum lot, even when that override is enabled.
//+------------------------------------------------------------------+
double CRiskEngine::CalculateLotSize(string symbol,double riskPercent,double entry,double stopLoss,
                                     bool halveForReducedRisk,bool allowMinLotOverride,bool &exceededRiskBudget,
                                     double sizeMultiplier)
  {
   exceededRiskBudget=false;
   if(!MathIsValidNumber(riskPercent) || !MathIsValidNumber(sizeMultiplier) ||
      riskPercent<=0.0 || entry<=0.0 || stopLoss<=0.0 || entry==stopLoss)
      return 0.0;

   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(!MathIsValidNumber(equity) || equity<=0.0)
      return 0.0;

   double lossPerLot=0.0;
   if(!EstimateStopLossPerLot(symbol,entry,stopLoss,lossPerLot))
      return 0.0;

   double riskAmount=equity*(riskPercent/100.0);
   if(halveForReducedRisk) riskAmount*=0.5;
   double multiplier=MathMax(0.0,MathMin(1.0,sizeMultiplier));
   riskAmount*=multiplier;
   if(!MathIsValidNumber(riskAmount) || riskAmount<=0.0)
      return 0.0;

   double minLot=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   double maxLot=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
   double lotStep=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(!MathIsValidNumber(minLot) || !MathIsValidNumber(maxLot) ||
      !MathIsValidNumber(lotStep) || minLot<=0.0 || maxLot<minLot || lotStep<=0.0)
      return 0.0;

   double lots=riskAmount/lossPerLot;
   if(!MathIsValidNumber(lots) || lots<=0.0)
      return 0.0;

   // Round down before applying the broker maximum to avoid exceeding
   // the risk budget because of volume-step rounding.
   lots=MathMin(maxLot,lots);
   lots=MathFloor(lots/lotStep+1e-9)*lotStep;
   lots=NormalizeDouble(lots,8);

   if(lots<minLot)
     {
      if(!allowMinLotOverride)
         return 0.0;
      exceededRiskBudget=true;
      lots=minLot;
     }

   return lots;
  }

//+------------------------------------------------------------------+
// Stop-based risk for a proposed position. A stop already at or beyond
// entry protects against ordinary price loss at the stop, so it reports
// zero planned stop risk; gap risk and execution costs still exist.
// Invalid price/tick calculations return zero, and the caller must fail
// closed rather than treating that value as proof of safe exposure.
//+------------------------------------------------------------------+
double CRiskEngine::RiskAmountForLots(string symbol,double lots,double entry,double stopLoss)
  {
   if(!MathIsValidNumber(lots) || lots<=0.0 || !MathIsValidNumber(entry) ||
      !MathIsValidNumber(stopLoss) || entry<=0.0 || stopLoss<=0.0)
      return 0.0;

   if(entry==stopLoss)
      return 0.0;

   double lossPerLot=0.0;
   if(!EstimateStopLossPerLot(symbol,entry,stopLoss,lossPerLot))
      return 0.0;

   double risk=lossPerLot*lots;
   return (MathIsValidNumber(risk) && risk>0.0 ? risk : 0.0);
  }

//+------------------------------------------------------------------+
// Validate at the strategy's resolved entry for the normal setup gate.
//+------------------------------------------------------------------+
bool CRiskEngine::ValidateSetup(TradeSetup &setup,double minRR,double maxSLDistanceATR,double currentATR)
  {
   return ValidateSetupAtEntry(setup,ResolveExecutionEntry(setup),minRR,maxSLDistanceATR,currentATR);
  }

//+------------------------------------------------------------------+
// Validate geometry at a specified executable or conservative entry.
// This is used a second time before sizing a market order, where the
// worst allowed fill inside the configured deviation band must still
// satisfy the same RR and ATR risk limits.
//+------------------------------------------------------------------+
bool CRiskEngine::ValidateSetupAtEntry(const TradeSetup &setup,double entry,double minRR,double maxSLDistanceATR,double currentATR)
  {
   if(!setup.active || (setup.type!=ORDER_TYPE_BUY && setup.type!=ORDER_TYPE_SELL))
      return false;
   if(!MathIsValidNumber(entry) || !MathIsValidNumber(minRR) ||
      !MathIsValidNumber(maxSLDistanceATR) || !MathIsValidNumber(currentATR) ||
      entry<=0.0 || minRR<=0.0)
      return false;

   double sl=setup.stop_loss;
   double tp1=setup.tp1;
   if(!MathIsValidNumber(sl) || !MathIsValidNumber(tp1) ||
      !MathIsValidNumber(setup.tp2) || !MathIsValidNumber(setup.final_tp) ||
      sl<=0.0 || tp1<=0.0)
      return false;

   if(setup.type==ORDER_TYPE_BUY)
     {
      if(!(sl<entry && tp1>entry)) return false;
      if(setup.tp2>0.0 && setup.tp2<=entry) return false;
      if(setup.final_tp>0.0 && setup.final_tp<=entry) return false;
     }
   else
     {
      if(!(sl>entry && tp1<entry)) return false;
      if(setup.tp2>0.0 && setup.tp2>=entry) return false;
      if(setup.final_tp>0.0 && setup.final_tp>=entry) return false;
     }

   double slDist=MathAbs(entry-sl);
   double tpDist=MathAbs(tp1-entry);
   if(slDist<=0.0 || tpDist/slDist<minRR)
      return false;

   // A zero cap disables the ATR-distance limit; positive caps enforce it.
   if(currentATR>0.0 && maxSLDistanceATR>0.0)
     {
      double slDistATR=slDist/currentATR;
      if(!MathIsValidNumber(slDistATR) || slDistATR>maxSLDistanceATR)
         return false;
     }
   return true;
  }
#endif
//+------------------------------------------------------------------+
