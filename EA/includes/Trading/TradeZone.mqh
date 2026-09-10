//+------------------------------------------------------------------+
//|                                              Trading/TradeZone.mqh |
//+------------------------------------------------------------------+
#ifndef TRADEZONE_MQH
#define TRADEZONE_MQH
#include "../Core/Config.mqh"
#include "../Core/CandleData.mqh"
#include "../Analysis/TFContext.mqh"
#include "../Analysis/Scoring.mqh"
#include "Targets.mqh"

class CTradeDecision
  {
private:
   CCandleData* m_priceRef;
   CTFContext* m_fvgCtx;
   CTFContext* m_liqCtx;
   CScoringEngine* m_scoring;
   TradeSetup m_lastSetup;
   double m_slBufferATR;
   double m_minStopSpreadMult;
   bool FindEntryFVG(ENUM_FVG_DIR dir,FVGZone &out);
   double EnforceSpreadFloor(string symbol,double entry,double stopLoss,bool isBuy);
public:
   CTradeDecision();
   void Init(CCandleData* priceRef,CTFContext* fvgCtx,CTFContext* liqCtx,CScoringEngine* scoring,double slBufferATR=0.25,double minStopSpreadMult=3.0);
   TradeSetup GenerateBuySetup();
   TradeSetup GenerateSellSetup();
   TradeSetup GetLastSetup() const{return m_lastSetup;}
  };

CTradeDecision::CTradeDecision(){ZeroMemory(m_lastSetup);m_slBufferATR=0.25;m_minStopSpreadMult=3.0;}
void CTradeDecision::Init(CCandleData* priceRef,CTFContext* fvgCtx,CTFContext* liqCtx,CScoringEngine* scoring,double slBufferATR,double minStopSpreadMult)
  {m_priceRef=priceRef;m_fvgCtx=fvgCtx;m_liqCtx=liqCtx;m_scoring=scoring;m_slBufferATR=(slBufferATR>0?slBufferATR:0.25);m_minStopSpreadMult=(minStopSpreadMult>=0?minStopSpreadMult:3.0);}

double CTradeDecision::EnforceSpreadFloor(string symbol,double entry,double stopLoss,bool isBuy)
  {if(m_minStopSpreadMult<=0)return stopLoss;long spreadPoints=SymbolInfoInteger(symbol,SYMBOL_SPREAD);double point=SymbolInfoDouble(symbol,SYMBOL_POINT);if(spreadPoints<=0||point<=0)return stopLoss;double minDist=spreadPoints*point*m_minStopSpreadMult;if(MathAbs(entry-stopLoss)>=minDist)return stopLoss;return isBuy?entry-minDist:entry+minDist;}

// Select the same FVG quality ordering used by CScoringEngine::FVGScore():
// fresh zones outrank tested zones and, within a state, nearer zones outrank
// farther ones. The old implementation took the first qualifying zone,
// allowing confidence to describe FVG A while execution used FVG B.
bool CTradeDecision::FindEntryFVG(ENUM_FVG_DIR dir,FVGZone &out)
  {
   if(m_fvgCtx==NULL||m_priceRef==NULL||m_priceRef.Total()==0)return false;double price=m_priceRef.GetCandle(0).close,atr=m_fvgCtx.candles.GetATR(0);if(atr<=0)return false;
   const double maxDistATR=1.25;double bestScore=-1.0;bool found=false;
   for(int i=0;i<m_fvgCtx.fvg.Count();i++)
     {FVGZone z=m_fvgCtx.fvg.GetZone(i);if(z.dir!=dir||(z.state!=FVG_FRESH&&z.state!=FVG_TESTED))continue;double mid=(z.top+z.bottom)/2.0,distATR=MathAbs(price-mid)/atr;if(distATR>maxDistATR)continue;double base=(z.state==FVG_FRESH)?1.0:0.6,proximity=MathMax(0.0,1.0-distATR/maxDistATR),score=base*(0.5+0.5*proximity);if(!found||score>bestScore){bestScore=score;out=z;found=true;}}
   return found;
  }

TradeSetup CTradeDecision::GenerateBuySetup()
  {
   TradeSetup setup;ZeroMemory(setup);if(m_priceRef==NULL||m_fvgCtx==NULL||m_scoring==NULL)return setup;double conf=m_scoring.CalculateConfidence(true);if(conf<60.0)return setup;FVGZone entryFVG;if(!FindEntryFVG(FVG_BULL,entryFVG))return setup;double atr=m_fvgCtx.candles.GetATR(0);if(atr<=0)return setup;
   setup.type=ORDER_TYPE_BUY;setup.entry_top=entryFVG.top;setup.entry_bottom=entryFVG.bottom;setup.stop_loss=EnforceSpreadFloor(m_priceRef.Symbol(),setup.entry_top,entryFVG.bottom-m_slBufferATR*atr,true);
   // Targets are now constructed from the exact execution entry, so the
   // TP/RR contract describes the price actually used by risk sizing/order placement.
   CTargetSelector::AssignTargets(setup,m_liqCtx,m_priceRef.Symbol(),atr,setup.entry_top);setup.confidence=conf;setup.creation_time=TimeCurrent();setup.active=true;m_scoring.EvaluateReasons(true,setup.reasons);m_scoring.PopulateConfidenceDiagnostics(setup.reasons,setup.confidence);m_scoring.PopulateStrategyDiagnostics(true,setup.confidence,setup.reasons);m_lastSetup=setup;return setup;
  }

TradeSetup CTradeDecision::GenerateSellSetup()
  {
   TradeSetup setup;ZeroMemory(setup);if(m_priceRef==NULL||m_fvgCtx==NULL||m_scoring==NULL)return setup;double conf=m_scoring.CalculateConfidence(false);if(conf<60.0)return setup;FVGZone entryFVG;if(!FindEntryFVG(FVG_BEAR,entryFVG))return setup;double atr=m_fvgCtx.candles.GetATR(0);if(atr<=0)return setup;
   setup.type=ORDER_TYPE_SELL;setup.entry_top=entryFVG.top;setup.entry_bottom=entryFVG.bottom;setup.stop_loss=EnforceSpreadFloor(m_priceRef.Symbol(),setup.entry_bottom,entryFVG.top+m_slBufferATR*atr,false);
   CTargetSelector::AssignTargets(setup,m_liqCtx,m_priceRef.Symbol(),atr,setup.entry_bottom);setup.confidence=conf;setup.creation_time=TimeCurrent();setup.active=true;m_scoring.EvaluateReasons(false,setup.reasons);m_scoring.PopulateConfidenceDiagnostics(setup.reasons,setup.confidence);m_scoring.PopulateStrategyDiagnostics(false,setup.confidence,setup.reasons);m_lastSetup=setup;return setup;
  }
#endif
//+------------------------------------------------------------------+
