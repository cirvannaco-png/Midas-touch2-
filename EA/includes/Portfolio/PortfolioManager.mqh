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
   bool m_enableCorrelationGuard; int m_correlationLookback; double m_correlationThreshold;
   string CorrelationGroup(string symbol); double OpenRiskAmount(ulong ticket);
   double RollingCorrelation(string symbolA,string symbolB);
public:
   void Init(double maxPortfolioRiskPercent,int maxPositionsPerSymbol,int maxPositionsPerGroup,ulong magic,CRiskEngine* risk);
   void ConfigureCorrelationGuard(bool enabled,int lookbackBars=60,double threshold=0.80)
     {
      m_enableCorrelationGuard=enabled;
      m_correlationLookback=MathMax(20,lookbackBars);
      m_correlationThreshold=MathMax(0.50,MathMin(0.99,threshold));
     }
   bool AllowNewTrade(string symbol,double proposedRiskAmount,string &reasonOut);
   bool AllowNewTradeBatch(string symbol,double proposedRiskAmount,int proposedPositions,string &reasonOut);
  };
void CPortfolioManager::Init(double maxPortfolioRiskPercent,int maxPositionsPerSymbol,int maxPositionsPerGroup,ulong magic,CRiskEngine* risk)
  {
   m_maxPortfolioRiskPercent=MathMax(0.0,maxPortfolioRiskPercent); m_maxPositionsPerSymbol=MathMax(1,maxPositionsPerSymbol);
   m_maxPositionsPerGroup=MathMax(1,maxPositionsPerGroup); m_magic=magic; m_risk=risk;
   m_enableCorrelationGuard=false; m_correlationLookback=60; m_correlationThreshold=0.80;
  }
string CPortfolioManager::CorrelationGroup(string symbol)
  {
   if(StringFind(symbol,"BTC")>=0 || StringFind(symbol,"ETH")>=0 || StringFind(symbol,"XRP")>=0) return "CRYPTO";
   if(StringFind(symbol,"XAU")>=0 || StringFind(symbol,"XAG")>=0) return "METALS";
   if(StringFind(symbol,"US30")>=0 || StringFind(symbol,"NAS100")>=0 || StringFind(symbol,"SPX")>=0 || StringFind(symbol,"GER40")>=0 || StringFind(symbol,"UK100")>=0 || StringFind(symbol,"JPN225")>=0) return "INDICES";
   return "FX";
  }
double CPortfolioManager::RollingCorrelation(string symbolA,string symbolB)
  {
   if(!m_enableCorrelationGuard || symbolA=="" || symbolB=="") return 0.0;
   if(symbolA==symbolB) return 1.0;

   int nTarget=MathMax(20,m_correlationLookback);
   double a[]; double b[];
   ArrayResize(a,nTarget);
   ArrayResize(b,nTarget);
   int n=0;
   for(int shift=1;shift<=nTarget;shift++)
     {
      double a0=iClose(symbolA,PERIOD_H1,shift);
      double a1=iClose(symbolA,PERIOD_H1,shift+1);
      double b0=iClose(symbolB,PERIOD_H1,shift);
      double b1=iClose(symbolB,PERIOD_H1,shift+1);
      if(a0<=0.0||a1<=0.0||b0<=0.0||b1<=0.0) continue;
      a[n]=(a0/a1)-1.0;
      b[n]=(b0/b1)-1.0;
      n++;
     }
   if(n<MathMax(20,nTarget/2)) return 0.0;

   double meanA=0.0,meanB=0.0;
   for(int i=0;i<n;i++){meanA+=a[i];meanB+=b[i];}
   meanA/=n; meanB/=n;

   double cov=0.0,varA=0.0,varB=0.0;
   for(int i=0;i<n;i++)
     {
      double da=a[i]-meanA;
      double db=b[i]-meanB;
      cov+=da*db; varA+=da*da; varB+=db*db;
     }
   double denom=MathSqrt(varA*varB);
   return denom>0.0?cov/denom:0.0;
  }

//+------------------------------------------------------------------+
double CPortfolioManager::OpenRiskAmount(ulong ticket)
  {
   if(m_risk==NULL || !PositionSelectByTicket(ticket)) return -1.0;
   string symbol=PositionGetString(POSITION_SYMBOL); double entry=PositionGetDouble(POSITION_PRICE_OPEN);
   double sl=PositionGetDouble(POSITION_SL); double volume=PositionGetDouble(POSITION_VOLUME);
   if(sl<=0.0 || entry<=0.0 || volume<=0.0) return -1.0;
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
   if(m_enableCorrelationGuard)
     {
      for(int i=0;i<PositionsTotal();i++)
        {
         ulong ticket=PositionGetTicket(i);
         if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
         if((ulong)PositionGetInteger(POSITION_MAGIC)!=m_magic) continue;
         string posSymbol=PositionGetString(POSITION_SYMBOL);
         if(posSymbol==symbol) continue;
         double corr=RollingCorrelation(symbol,posSymbol);
         if(MathAbs(corr)>=m_correlationThreshold)
           {
            reasonOut=StringFormat("rolling H1 correlation %.2f between %s and existing %s exceeds %.2f; refusing additional correlated exposure",
                                   corr,symbol,posSymbol,m_correlationThreshold);
            return false;
           }
        }
     }
   if(unknown)
     {
      reasonOut="an existing open position under this magic number has uncomputable risk — refusing new exposure until its stop/risk can be verified";
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
