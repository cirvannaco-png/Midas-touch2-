//+------------------------------------------------------------------+
//| Trading/TradeZone.mqh                                             |
//| Strategy-aware setup construction and SMC baseline.               |
//+------------------------------------------------------------------+
#ifndef TRADEZONE_MQH
#define TRADEZONE_MQH
#include "../Core/Config.mqh"
#include "../Core/CandleData.mqh"
#include "../Analysis/TFContext.mqh"
#include "../Analysis/Scoring.mqh"
#include "StrategySetupBuilders.mqh"
#include "Targets.mqh"

// These are owned by the EA entry point. The explicit extern bindings keep
// strategy setup construction on the same contexts already used by the
// authoritative scoring/regime layer, without duplicating detectors.
extern CTFContext* g_chartCtx;
extern CTFContext* g_bosCtx;

class CTradeDecision
  {
private:
   CCandleData* m_priceRef;
   CTFContext* m_fvgCtx;
   CTFContext* m_liqCtx;
   CTFContext* m_srCtx;
   CTFContext* m_bosCtx;
   CScoringEngine* m_scoring;
   TradeSetup m_lastSetup;
   double m_slBufferATR;
   double m_minStopSpreadMult;
   double m_fvgMaxDistATR;
   bool FindEntryFVG(ENUM_FVG_DIR dir,FVGZone &out);
   double EnforceSpreadFloor(string symbol,double entry,double stopLoss,bool isBuy);
   TradeSetup BuildSMC(bool forBuy);
   TradeSetup BuildAuthoritativeStrategy(bool forBuy,const TradeSetup &smc);
public:
   CTradeDecision();
   void Init(CCandleData* priceRef,CTFContext* fvgCtx,CTFContext* liqCtx,CScoringEngine* scoring,
             double slBufferATR=0.25,double minStopSpreadMult=3.0,double fvgMaxDistATR=1.25,
             CTFContext* srCtx=NULL,CTFContext* bosCtx=NULL);
   TradeSetup GenerateBuySetup();
   TradeSetup GenerateSellSetup();
   TradeSetup GetLastSetup()const{return m_lastSetup;}
  };

CTradeDecision::CTradeDecision(){ZeroMemory(m_lastSetup);m_priceRef=NULL;m_fvgCtx=NULL;m_liqCtx=NULL;m_srCtx=NULL;m_bosCtx=NULL;
                                  m_scoring=NULL;m_slBufferATR=0.25;m_minStopSpreadMult=3.0;m_fvgMaxDistATR=1.25;}

void CTradeDecision::Init(CCandleData* priceRef,CTFContext* fvgCtx,CTFContext* liqCtx,CScoringEngine* scoring,
                          double slBufferATR,double minStopSpreadMult,double fvgMaxDistATR,
                          CTFContext* srCtx,CTFContext* bosCtx)
  {m_priceRef=priceRef;m_fvgCtx=fvgCtx;m_liqCtx=liqCtx;
   m_srCtx=(srCtx!=NULL?srCtx:g_chartCtx);m_bosCtx=(bosCtx!=NULL?bosCtx:g_bosCtx);
   m_scoring=scoring;m_slBufferATR=(slBufferATR>0?slBufferATR:0.25);m_minStopSpreadMult=(minStopSpreadMult>=0?minStopSpreadMult:3.0);
   m_fvgMaxDistATR=(fvgMaxDistATR>0?fvgMaxDistATR:1.25);}

double CTradeDecision::EnforceSpreadFloor(string symbol,double entry,double stopLoss,bool isBuy)
  {if(m_minStopSpreadMult<=0)return stopLoss;long sp=SymbolInfoInteger(symbol,SYMBOL_SPREAD);double pt=SymbolInfoDouble(symbol,SYMBOL_POINT);
   if(sp<=0||pt<=0)return stopLoss;double minDist=(double)sp*pt*m_minStopSpreadMult;double cur=MathAbs(entry-stopLoss);
   if(cur>=minDist)return stopLoss;return isBuy?(entry-minDist):(entry+minDist);}

bool CTradeDecision::FindEntryFVG(ENUM_FVG_DIR dir,FVGZone &out)
  {if(m_fvgCtx==NULL||m_priceRef==NULL||m_priceRef.Total()==0)return false;double price=m_priceRef.GetCandle(0).close;
   double atr=m_fvgCtx.candles.GetATR(0);if(price<=0||atr<=0)return false;bool found=false;double bestScore=-1.0;
   for(int i=0;i<m_fvgCtx.fvg.Count();i++)
     {FVGZone z=m_fvgCtx.fvg.GetZone(i);if(z.dir!=dir)continue;if(z.state!=FVG_FRESH&&z.state!=FVG_TESTED)continue;
      double mid=(z.top+z.bottom)/2.0;double distATR=MathAbs(price-mid)/atr;if(distATR>m_fvgMaxDistATR)continue;
      double base=(z.state==FVG_FRESH)?1.0:0.6;double proximity=MathMax(0.0,1.0-distATR/m_fvgMaxDistATR);
      double score=base*(0.5+0.5*proximity);if(!found||score>bestScore){found=true;bestScore=score;out=z;}}
   return found;}

TradeSetup CTradeDecision::BuildSMC(bool forBuy)
  {TradeSetup setup;ZeroMemory(setup);if(m_priceRef==NULL||m_fvgCtx==NULL||m_scoring==NULL)return setup;
   double conf=m_scoring.CalculateConfidence(forBuy);if(conf<60.0)return setup;FVGZone entryFVG;
   if(!FindEntryFVG(forBuy?FVG_BULL:FVG_BEAR,entryFVG))return setup;double atr=m_fvgCtx.candles.GetATR(0);if(atr<=0)return setup;
   setup.type=forBuy?ORDER_TYPE_BUY:ORDER_TYPE_SELL;setup.entry_top=entryFVG.top;setup.entry_bottom=entryFVG.bottom;
   setup.stop_loss=forBuy?(entryFVG.bottom-m_slBufferATR*atr):(entryFVG.top+m_slBufferATR*atr);
   setup.stop_loss=EnforceSpreadFloor(m_priceRef.Symbol(),forBuy?setup.entry_top:setup.entry_bottom,setup.stop_loss,forBuy);
   CTargetSelector::AssignTargets(setup,m_liqCtx,m_priceRef.Symbol(),atr,forBuy?setup.entry_bottom:setup.entry_top);
   setup.confidence=conf;setup.creation_time=TimeCurrent();setup.active=true;
   m_scoring.EvaluateReasons(forBuy,setup.reasons);m_scoring.PopulateConfidenceDiagnostics(setup.reasons,setup.confidence);
   m_scoring.PopulateStrategyDiagnostics(forBuy,setup.confidence,setup.reasons);
   return setup;}

TradeSetup CTradeDecision::BuildAuthoritativeStrategy(bool forBuy,const TradeSetup &smc)
  {TradeSetup out;ZeroMemory(out);if(!smc.active)return out;
   const ENUM_SELECTED_STRATEGY selected=smc.reasons.selected_strategy;const double score=smc.reasons.selected_strategy_score;bool built=false;
   if(selected==STRATEGY_MOMENTUM_BREAKOUT)
      built=CStrategySetupBuilders::BuildMomentum(forBuy,score,smc.reasons,m_priceRef,m_bosCtx,m_liqCtx,out);
   else if(selected==STRATEGY_MEAN_REVERSION)
      built=CStrategySetupBuilders::BuildMeanReversion(forBuy,score,smc.reasons,m_priceRef,m_srCtx,m_liqCtx,out);
   else if(selected==STRATEGY_KEY_LEVEL)
      built=CStrategySetupBuilders::BuildKeyLevel(forBuy,score,smc.reasons,m_priceRef,m_srCtx,m_liqCtx,out);
   if(!built)return out;
   out.stop_loss=EnforceSpreadFloor(m_priceRef.Symbol(),ResolveExecutionEntry(out),out.stop_loss,forBuy);
   return out;}

TradeSetup CTradeDecision::GenerateBuySetup()
  {TradeSetup smc=BuildSMC(true);if(smc.reasons.selected_strategy!=STRATEGY_SMC){TradeSetup owned=BuildAuthoritativeStrategy(true,smc);if(owned.active){m_lastSetup=owned;return owned;}}
   if(smc.reasons.selected_strategy==STRATEGY_SMC&&smc.active){m_lastSetup=smc;return smc;}
   ZeroMemory(smc);m_lastSetup=smc;return smc;}

TradeSetup CTradeDecision::GenerateSellSetup()
  {TradeSetup smc=BuildSMC(false);if(smc.reasons.selected_strategy!=STRATEGY_SMC){TradeSetup owned=BuildAuthoritativeStrategy(false,smc);if(owned.active){m_lastSetup=owned;return owned;}}
   if(smc.reasons.selected_strategy==STRATEGY_SMC&&smc.active){m_lastSetup=smc;return smc;}
   ZeroMemory(smc);m_lastSetup=smc;return smc;}

#endif
//+------------------------------------------------------------------+
