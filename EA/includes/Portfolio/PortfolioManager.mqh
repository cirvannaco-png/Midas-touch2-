//+------------------------------------------------------------------+
//|                                     Portfolio/PortfolioManager.mqh |
//+------------------------------------------------------------------+
#ifndef PORTFOLIOMANAGER_MQH
#define PORTFOLIOMANAGER_MQH
#include "../Trading/RiskEngine.mqh"
class CPortfolioManager
  {
private:
   double m_maxPortfolioRiskPercent; int m_maxPositionsPerSymbol; int m_maxPositionsPerGroup; ulong m_magic; CRiskEngine* m_risk;
   string CorrelationGroup(string symbol); double OpenRiskAmount(ulong ticket); double PendingOrderRiskAmount(ulong ticket);
public:
   void Init(double maxPortfolioRiskPercent,int maxPositionsPerSymbol,int maxPositionsPerGroup,ulong magic,CRiskEngine* risk);
   bool AllowNewTrade(string symbol,double proposedRiskAmount,string &reasonOut);
   bool AllowNewTradeBatch(string symbol,double proposedRiskAmount,int proposedPositions,string &reasonOut);
  };
void CPortfolioManager::Init(double maxPortfolioRiskPercent,int maxPositionsPerSymbol,int maxPositionsPerGroup,ulong magic,CRiskEngine* risk)
  {
   m_maxPortfolioRiskPercent=MathMax(0.0,maxPortfolioRiskPercent); m_maxPositionsPerSymbol=MathMax(1,maxPositionsPerSymbol);
   m_maxPositionsPerGroup=MathMax(1,maxPositionsPerGroup); m_magic=magic; m_risk=risk;
  }
string CPortfolioManager::CorrelationGroup(string symbol)
  {
   if(StringFind(symbol,"BTC")>=0 || StringFind(symbol,"ETH")>=0 || StringFind(symbol,"XRP")>=0) return "CRYPTO";
   if(StringFind(symbol,"XAU")>=0 || StringFind(symbol,"XAG")>=0) return "METALS";
   if(StringFind(symbol,"US30")>=0 || StringFind(symbol,"NAS100")>=0 || StringFind(symbol,"SPX")>=0 || StringFind(symbol,"GER40")>=0 || StringFind(symbol,"UK100")>=0 || StringFind(symbol,"JPN225")>=0) return "INDICES";
   return "FX";
  }
double CPortfolioManager::OpenRiskAmount(ulong ticket)
  {
   if(m_risk==NULL || !PositionSelectByTicket(ticket)) return -1.0;

   string symbol=PositionGetString(POSITION_SYMBOL);
   ENUM_POSITION_TYPE type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   double entry=PositionGetDouble(POSITION_PRICE_OPEN);
   double sl=PositionGetDouble(POSITION_SL);
   double volume=PositionGetDouble(POSITION_VOLUME);

   // Missing protection is unknown risk, so the portfolio gate must fail closed.
   if(sl<=0.0 || entry<=0.0 || volume<=0.0) return -1.0;

   // Use the remaining adverse distance to the actual stop. A stop at or
   // beyond entry locks out price-based loss at the stop, so its planned
   // stop risk is zero rather than "unknown". Gaps, slippage and broker
   // execution can still make a realized loss exceed this stop-based estimate.
   if(type==POSITION_TYPE_BUY && sl>=entry) return 0.0;
   if(type==POSITION_TYPE_SELL && sl<=entry) return 0.0;

   // Any nonstandard/invalid position geometry is not safe to estimate.
   if(type!=POSITION_TYPE_BUY && type!=POSITION_TYPE_SELL) return -1.0;

   double risk=m_risk.RiskAmountForLots(symbol,volume,entry,sl);
   return risk>0.0 ? risk : -1.0; // Invalid tick metadata remains unknown, not zero risk.
  }
double CPortfolioManager::PendingOrderRiskAmount(ulong ticket)
  {
   if(m_risk==NULL || ticket==0 || !OrderSelect(ticket)) return -1.0;

   string symbol=OrderGetString(ORDER_SYMBOL);
   ENUM_ORDER_TYPE type=(ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
   double entry=OrderGetDouble(ORDER_PRICE_OPEN);
   double sl=OrderGetDouble(ORDER_SL);
   double volume=OrderGetDouble(ORDER_VOLUME_CURRENT);

   // An active order without a protective stop is unknown exposure. Unlike
   // an already-open position, a pending order with a stop on the wrong side
   // must not be interpreted as zero risk: the pending order has not yet
   // earned any locked-in protection.
   if(symbol=="" || entry<=0.0 || sl<=0.0 || volume<=0.0) return -1.0;

   bool isBuy=(type==ORDER_TYPE_BUY || type==ORDER_TYPE_BUY_LIMIT ||
               type==ORDER_TYPE_BUY_STOP || type==ORDER_TYPE_BUY_STOP_LIMIT);
   bool isSell=(type==ORDER_TYPE_SELL || type==ORDER_TYPE_SELL_LIMIT ||
                type==ORDER_TYPE_SELL_STOP || type==ORDER_TYPE_SELL_STOP_LIMIT);
   if(!isBuy && !isSell) return -1.0;
   if(isBuy && sl>=entry) return -1.0;
   if(isSell && sl<=entry) return -1.0;

   double risk=m_risk.RiskAmountForLots(symbol,volume,entry,sl);
   return risk>0.0 ? risk : -1.0;
  }

bool CPortfolioManager::AllowNewTradeBatch(string symbol,double proposedRiskAmount,int proposedPositions,string &reasonOut)
  {
   reasonOut="";
   if(m_risk==NULL){reasonOut="portfolio risk engine unavailable";return false;}
   if(proposedRiskAmount<=0.0){reasonOut="proposed trade risk is non-positive or cannot be calculated";return false;}
   if(proposedPositions<=0){reasonOut="proposed position count is invalid";return false;}
   if(m_maxPortfolioRiskPercent<=0.0){reasonOut="portfolio risk cap is zero; refusing new exposure";return false;}

   string group=CorrelationGroup(symbol);
   double totalRisk=proposedRiskAmount;
   int symbolCount=0;
   int groupCount=0;
   bool unknown=false;

   for(int i=0;i<PositionsTotal();i++)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=m_magic) continue;
      string posSymbol=PositionGetString(POSITION_SYMBOL);
      if(posSymbol==symbol) symbolCount++;
      if(CorrelationGroup(posSymbol)==group) groupCount++;
      double risk=OpenRiskAmount(ticket);
      if(risk<0.0) unknown=true;
      else totalRisk+=risk;
     }

   // Include live pending orders as contingent exposure. Otherwise an
   // EA instance could reserve a portfolio budget with a pending limit
   // order and another instance could spend the same budget before fill.
   for(int i=0;i<OrdersTotal();i++)
     {
      ulong ticket=OrderGetTicket(i); // Selects this active order.
      if(ticket==0) continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC)!=m_magic) continue;
      string orderSymbol=OrderGetString(ORDER_SYMBOL);
      if(orderSymbol==symbol) symbolCount++;
      if(CorrelationGroup(orderSymbol)==group) groupCount++;
      double risk=PendingOrderRiskAmount(ticket);
      if(risk<0.0) unknown=true;
      else totalRisk+=risk;
     }

   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity<=0.0){reasonOut="account equity unavailable/non-positive";return false;}

   double maxRiskAmount=equity*(m_maxPortfolioRiskPercent/100.0);
   if(symbolCount+proposedPositions>m_maxPositionsPerSymbol)
     {
      reasonOut=StringFormat("%s would have %d position(s), above the per-symbol limit %d",
                             symbol,symbolCount+proposedPositions,m_maxPositionsPerSymbol);
      return false;
     }
   if(groupCount+proposedPositions>m_maxPositionsPerGroup)
     {
      reasonOut=StringFormat("correlation group %s would have %d position(s), above the group limit %d",
                             group,groupCount+proposedPositions,m_maxPositionsPerGroup);
      return false;
     }
   if(unknown)
     {
      reasonOut="an existing position or pending order under this magic number has uncomputable risk — refusing new exposure until its stop/risk can be verified";
      return false;
     }
   if(totalRisk>maxRiskAmount)
     {
      reasonOut=StringFormat("adding this trade batch would bring total open risk to %.2f, above the %.2f%% portfolio cap (%.2f)",
                             totalRisk,m_maxPortfolioRiskPercent,maxRiskAmount);
      return false;
     }
   return true;
  }

bool CPortfolioManager::AllowNewTrade(string symbol,double proposedRiskAmount,string &reasonOut)
  {
   return AllowNewTradeBatch(symbol,proposedRiskAmount,1,reasonOut);
  }
#endif
//+------------------------------------------------------------------+
