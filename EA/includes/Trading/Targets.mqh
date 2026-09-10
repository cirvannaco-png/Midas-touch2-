//+------------------------------------------------------------------+
//|                                                Trading/Targets.mqh |
//+------------------------------------------------------------------+
#ifndef TARGETS_MQH
#define TARGETS_MQH
#include "../Core/Config.mqh"
#include "../Analysis/TFContext.mqh"

class CTargetSelector
  {
private:
   static bool NearestBeyond(CTFContext* liqCtx,bool wantInternal,bool forBuy,double entryPrice,double excludeBeyond,bool haveExclude,double &outPrice);
   static bool WeeklyLevel(string symbol,bool forBuy,double &outPrice);
public:
   static void AssignTargets(TradeSetup &setup,CTFContext* liqCtx,string symbol,double atr,double entryPrice);
  };

bool CTargetSelector::NearestBeyond(CTFContext* liqCtx,bool wantInternal,bool forBuy,double entryPrice,double excludeBeyond,bool haveExclude,double &outPrice)
  {
   outPrice=0.0;if(liqCtx==NULL)return false;double best=0.0;bool have=false;
   for(int i=0;i<liqCtx.liquidity.PoolCount();i++){LiquidityPool p=liqCtx.liquidity.GetPool(i);if(p.external==wantInternal)continue;double price=forBuy?p.price_top:p.price_bottom;bool right=forBuy?(price>entryPrice):(price<entryPrice);if(!right)continue;if(haveExclude){bool beyond=forBuy?(price>excludeBeyond):(price<excludeBeyond);if(!beyond)continue;}if(!have||(forBuy?price<best:price>best)){best=price;have=true;}}
   if(have)outPrice=best;return have;
  }
bool CTargetSelector::WeeklyLevel(string symbol,bool forBuy,double &outPrice){double v=forBuy?iHigh(symbol,PERIOD_W1,1):iLow(symbol,PERIOD_W1,1);if(v<=0)return false;outPrice=v;return true;}

void CTargetSelector::AssignTargets(TradeSetup &setup,CTFContext* liqCtx,string symbol,double atr,double entryPrice)
  {
   bool forBuy=(setup.type==ORDER_TYPE_BUY);double tp1,tp2,tp3;
   if(!NearestBeyond(liqCtx,true,forBuy,entryPrice,0.0,false,tp1))tp1=forBuy?entryPrice+2.0*atr:entryPrice-2.0*atr;
   if(!NearestBeyond(liqCtx,false,forBuy,entryPrice,tp1,true,tp2))tp2=forBuy?tp1+atr:tp1-atr;
   double weekly;if(WeeklyLevel(symbol,forBuy,weekly)&&(forBuy?weekly>tp2:weekly<tp2))tp3=weekly;else tp3=forBuy?tp2+atr:tp2-atr;
   setup.tp1=tp1;setup.tp2=tp2;setup.final_tp=tp3;
  }
#endif
//+------------------------------------------------------------------+
