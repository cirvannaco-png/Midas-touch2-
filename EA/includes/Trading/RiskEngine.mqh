//+------------------------------------------------------------------+
//|                                              Trading/RiskEngine.mqh |
//+------------------------------------------------------------------+
#ifndef RISKENGINE_MQH
#define RISKENGINE_MQH
#include "../Core/Config.mqh"
#include "TradeZone.mqh"

class CRiskEngine
  {
public:
   bool ValidateSetup(TradeSetup &setup,double minRR,double maxSLDistanceATR,double currentATR);
   double CalculateLotSize(string symbol,double riskPercent,double entry,double stopLoss,bool halveForReducedRisk,bool allowMinLotOverride,bool &exceededRiskBudget,double sizeMultiplier=1.0);
   double RiskAmountForLots(string symbol,double lots,double entry,double stopLoss);
  };

// Volume is rounded down to the broker step and then normalized to the
// number of decimal places implied by that step. This prevents values such
// as 0.30000000000000004 reaching OrderSend while preserving the invariant
// that the requested risk is never exceeded by rounding.
double CRiskEngine::CalculateLotSize(string symbol,double riskPercent,double entry,double stopLoss,bool halveForReducedRisk,bool allowMinLotOverride,bool &exceededRiskBudget,double sizeMultiplier)
  {
   exceededRiskBudget=false; double slDistance=MathAbs(entry-stopLoss); if(slDistance<=0)return 0.0;
   double equity=AccountInfoDouble(ACCOUNT_EQUITY),riskAmount=equity*(riskPercent/100.0); if(halveForReducedRisk)riskAmount*=0.5; riskAmount*=MathMax(0.0,MathMin(1.0,sizeMultiplier));
   double tickSize=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE),tickValue=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_VALUE); if(tickSize<=0||tickValue<=0)return 0.0;
   double lossPerLot=slDistance*(tickValue/tickSize); if(lossPerLot<=0)return 0.0;
   double rawLots=riskAmount/lossPerLot,minLot=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN),maxLot=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX),lotStep=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP); if(minLot<=0||maxLot<=0)return 0.0;
   double lots=rawLots; if(lotStep>0)lots=MathFloor((lots+1e-12)/lotStep)*lotStep;
   if(lots<minLot){if(!allowMinLotOverride)return 0.0;exceededRiskBudget=true;lots=minLot;}
   lots=MathMin(maxLot,lots);
   if(lotStep>0){int precision=0;double s=lotStep;while(precision<8&&MathAbs(s-MathRound(s))>1e-10){s*=10.0;precision++;}lots=NormalizeDouble(lots,precision);}
   if(lots<minLot-1e-12)return 0.0; return lots;
  }

double CRiskEngine::RiskAmountForLots(string symbol,double lots,double entry,double stopLoss)
  {double d=MathAbs(entry-stopLoss);if(d<=0||lots<=0)return 0.0;double ts=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE),tv=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_VALUE);if(ts<=0||tv<=0)return 0.0;return d*(tv/ts)*lots;}

bool CRiskEngine::ValidateSetup(TradeSetup &setup,double minRR,double maxSLDistanceATR,double currentATR)
  {if(!setup.active)return false;double entry=ResolveExecutionEntry(setup),slDist=MathAbs(entry-setup.stop_loss),tpDist=MathAbs(setup.tp1-entry);if(slDist<=0||tpDist<=0)return false;if(tpDist/slDist<minRR)return false;if(currentATR>0&&slDist/currentATR>maxSLDistanceATR)return false;return true;}
#endif
//+------------------------------------------------------------------+
