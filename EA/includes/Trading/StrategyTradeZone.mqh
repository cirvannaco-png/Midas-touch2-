//+------------------------------------------------------------------+
//| Trading/StrategyTradeZone.mqh                                    |
//| Regime-first peer strategy routing and setup construction.        |
//+------------------------------------------------------------------+
#ifndef STRATEGYTRADEZONE_MQH
#define STRATEGYTRADEZONE_MQH

#include "../Core/Config.mqh"
#include "../Core/CandleData.mqh"
#include "../Analysis/TFContext.mqh"
#include "../Analysis/Scoring.mqh"
#include "StrategySetupBuilders.mqh"
#include "Targets.mqh"
#include "EnvironmentStrategyMemory.mqh"

extern CTFContext* g_chartCtx;
extern CTFContext* g_bosCtx;

class CTradeDecision
  {
private:
   CCandleData*                    m_priceRef;
   CTFContext*                     m_fvgCtx;
   CTFContext*                     m_liqCtx;
   CTFContext*                     m_srCtx;
   CTFContext*                     m_bosCtx;
   CScoringEngine*                 m_scoring;
   CEnvironmentStrategyMemory*     m_environmentMemory;
   TradeSetup                      m_lastSetup;
   double                          m_slBufferATR;
   double                          m_minStopSpreadMult;
   double                          m_fvgMaxDistATR;
   double                          m_minSelectionScore;

   bool FindEntryFVG(ENUM_FVG_DIR dir,FVGZone &out);
   double EnforceSpreadFloor(string symbol,double entry,double stopLoss,bool isBuy);
   void PopulateStrategyReads(bool forBuy,SetupReasons &out);
   void SelectPeerStrategy(bool forBuy,SetupReasons &reasons,
                           ENUM_SELECTED_STRATEGY &selected,double &selectedScore);
   TradeSetup BuildSMC(bool forBuy,double confidence,const SetupReasons &reasons);
   bool BuildNonSMC(bool forBuy,ENUM_SELECTED_STRATEGY selected,double confidence,
                    const SetupReasons &reasons,TradeSetup &out);
   TradeSetup Generate(bool forBuy);

public:
   CTradeDecision();
   void Init(CCandleData* priceRef,CTFContext* fvgCtx,CTFContext* liqCtx,
             CScoringEngine* scoring,double slBufferATR=0.25,
             double minStopSpreadMult=3.0,double fvgMaxDistATR=1.25,
             double minSelectionScore=60.0,CTFContext* srCtx=NULL,
             CTFContext* bosCtx=NULL,CEnvironmentStrategyMemory* environmentMemory=NULL);
   TradeSetup GenerateBuySetup();
   TradeSetup GenerateSellSetup();
   TradeSetup GetLastSetup()const{return m_lastSetup;}
  };

CTradeDecision::CTradeDecision()
  {
   ZeroMemory(m_lastSetup);
   m_priceRef=NULL;
   m_fvgCtx=NULL;
   m_liqCtx=NULL;
   m_srCtx=NULL;
   m_bosCtx=NULL;
   m_scoring=NULL;
   m_environmentMemory=NULL;
   m_slBufferATR=0.25;
   m_minStopSpreadMult=3.0;
   m_fvgMaxDistATR=1.25;
   m_minSelectionScore=60.0;
  }

void CTradeDecision::Init(CCandleData* priceRef,CTFContext* fvgCtx,CTFContext* liqCtx,
                          CScoringEngine* scoring,double slBufferATR,double minStopSpreadMult,
                          double fvgMaxDistATR,double minSelectionScore,
                          CTFContext* srCtx,CTFContext* bosCtx,
                          CEnvironmentStrategyMemory* environmentMemory)
  {
   m_priceRef=priceRef;
   m_fvgCtx=fvgCtx;
   m_liqCtx=liqCtx;
   m_srCtx=(srCtx!=NULL?srCtx:g_chartCtx);
   m_bosCtx=(bosCtx!=NULL?bosCtx:g_bosCtx);
   m_scoring=scoring;
   m_environmentMemory=environmentMemory;
   m_slBufferATR=(slBufferATR>0?slBufferATR:0.25);
   m_minStopSpreadMult=(minStopSpreadMult>=0?minStopSpreadMult:3.0);
   m_fvgMaxDistATR=(fvgMaxDistATR>0?fvgMaxDistATR:1.25);
   m_minSelectionScore=(minSelectionScore>=0.0&&minSelectionScore<=100.0)?minSelectionScore:60.0;
  }

double CTradeDecision::EnforceSpreadFloor(string symbol,double entry,double stopLoss,bool isBuy)
  {
   if(m_minStopSpreadMult<=0)return stopLoss;
   long sp=SymbolInfoInteger(symbol,SYMBOL_SPREAD);
   double pt=SymbolInfoDouble(symbol,SYMBOL_POINT);
   if(sp<=0||pt<=0)return stopLoss;
   double minDist=(double)sp*pt*m_minStopSpreadMult;
   double cur=MathAbs(entry-stopLoss);
   if(cur>=minDist)return stopLoss;
   return isBuy?(entry-minDist):(entry+minDist);
  }

bool CTradeDecision::FindEntryFVG(ENUM_FVG_DIR dir,FVGZone &out)
  {
   if(m_fvgCtx==NULL||m_priceRef==NULL||m_priceRef.Total()==0)return false;
   double price=m_priceRef.GetCandle(0).close;
   double atr=m_fvgCtx.candles.GetATR(0);
   if(price<=0||atr<=0)return false;
   bool found=false;
   double bestScore=-1.0;
   for(int i=0;i<m_fvgCtx.fvg.Count();i++)
     {
      FVGZone z=m_fvgCtx.fvg.GetZone(i);
      if(z.dir!=dir)continue;
      if(z.state!=FVG_FRESH&&z.state!=FVG_TESTED)continue;
      double mid=(z.top+z.bottom)/2.0;
      double distATR=MathAbs(price-mid)/atr;
      if(distATR>m_fvgMaxDistATR)continue;
      double base=(z.state==FVG_FRESH)?1.0:0.6;
      double proximity=MathMax(0.0,1.0-distATR/m_fvgMaxDistATR);
      double score=base*(0.5+0.5*proximity);
      if(!found||score>bestScore)
        {
         found=true;
         bestScore=score;
         out=z;
        }
     }
   return found;
  }

void CTradeDecision::PopulateStrategyReads(bool forBuy,SetupReasons &out)
  {
   ZeroMemory(out);
   if(m_scoring==NULL)return;
   // SMC-neutral read pass: regime and independent strategy diagnostics are
   // populated before any SMC candidate is allowed to compete.
   m_scoring.EvaluateReasons(forBuy,out);
   m_scoring.PopulateStrategyDiagnostics(forBuy,0.0,out);
   out.selected_strategy=STRATEGY_NONE;
   out.selected_strategy_score=0.0;

   // Snapshot the execution environment at decision time. These fields are
   // telemetry/memory keys only; they do not independently gate a trade.
   if(m_priceRef!=NULL&&m_priceRef.Total()>0)
     {
      out.spread_points=(double)SymbolInfoInteger(m_priceRef.Symbol(),SYMBOL_SPREAD);
      out.point_size=SymbolInfoDouble(m_priceRef.Symbol(),SYMBOL_POINT);
      out.atr_value=m_priceRef.GetATR(0);
     }
   out.trend_strength=out.trend_aligned?1.0:0.0;
   out.liquidity_score=out.liquidity_swept?1.0:0.0;
   out.liquidity_bucket=out.liquidity_swept?2:0;
  }

void CTradeDecision::SelectPeerStrategy(bool forBuy,SetupReasons &reasons,
                                        ENUM_SELECTED_STRATEGY &selected,double &selectedScore)
  {
   selected=STRATEGY_NONE;
   selectedScore=0.0;
   if(m_scoring==NULL||reasons.regime==REGIME_UNDEFINED)return;

   ENUM_SELECTED_STRATEGY challenger=STRATEGY_NONE;
   double challengerScore=-1.0;
   if(reasons.regime==REGIME_TRENDING)
     {
      if(reasons.breakout_class!=BREAKOUT_FAILED&&reasons.breakout_class!=BREAKOUT_EXHAUSTION&&
         (reasons.breakout_class==BREAKOUT_EXPANSION||reasons.breakout_class==BREAKOUT_LIQUIDITY||
          reasons.momentum_score>=m_minSelectionScore))
        {
         challengerScore=MathMax(reasons.momentum_score,reasons.breakout_score);
         challenger=STRATEGY_MOMENTUM_BREAKOUT;
        }
     }
   else if(reasons.regime==REGIME_RANGING)
     {
      if(reasons.reversion_class==REVERSION_VALUE_FADE||reasons.reversion_class==REVERSION_LEVEL_REJECTION)
        {
         challengerScore=reasons.reversion_score;
         challenger=STRATEGY_MEAN_REVERSION;
        }
     }
   else if(reasons.regime==REGIME_TRANSITION)
     {
      if(reasons.keylevel_reaction==REACTION_REJECTION||reasons.keylevel_reaction==REACTION_RETEST||
         reasons.keylevel_reaction==REACTION_FAILED_BREAK||reasons.keylevel_reaction==REACTION_ABSORPTION)
        {
         challengerScore=reasons.keylevel_score;
         challenger=STRATEGY_KEY_LEVEL;
        }
     }

   bool challengerEligible=(challenger!=STRATEGY_NONE&&challengerScore>=m_minSelectionScore);
   double challengerAdjusted=challengerScore;
   EnvironmentMemoryEvidence challengerEvidence;ZeroMemory(challengerEvidence);
   bool challengerMemory=false;
   if(challengerEligible&&m_environmentMemory!=NULL)
      challengerMemory=m_environmentMemory.GetEvidence(reasons,challenger,challengerEvidence);
   if(challengerEligible&&challengerMemory)challengerAdjusted=challengerScore+challengerEvidence.adjustment;

   // SMC is a peer candidate, not a prerequisite. Its own confidence may
   // still be zero because the SMC engine did not validate its sequence;
   // that does not invalidate a non-SMC challenger.
   double smcScore=m_scoring.CalculateConfidence(forBuy);
   bool smcEligible=(smcScore>=m_minSelectionScore);
   double smcAdjusted=smcScore;
   EnvironmentMemoryEvidence smcEvidence;ZeroMemory(smcEvidence);
   bool smcMemory=false;
   if(smcEligible&&m_environmentMemory!=NULL)
      smcMemory=m_environmentMemory.GetEvidence(reasons,STRATEGY_SMC,smcEvidence);
   if(smcEligible&&smcMemory)smcAdjusted=smcScore+smcEvidence.adjustment;

   if(challengerEligible&&(!smcEligible||challengerAdjusted>smcAdjusted))
     {
      selected=challenger;
      selectedScore=challengerScore; // raw score remains authoritative in telemetry
      if(challengerMemory)
        {
         reasons.environment_memory_status=challengerEvidence.status;
         reasons.environment_memory_sample=challengerEvidence.sample_size;
         reasons.environment_memory_win_rate=challengerEvidence.win_rate*100.0;
         reasons.environment_memory_avg_r=challengerEvidence.avg_r;
         reasons.environment_memory_profit_factor=challengerEvidence.profit_factor;
         reasons.environment_memory_adjustment=challengerEvidence.adjustment;
        }
      else reasons.environment_memory_status="UNKNOWN";
     }
   else if(smcEligible)
     {
      selected=STRATEGY_SMC;
      selectedScore=smcScore; // raw score remains authoritative in telemetry
      if(smcMemory)
        {
         reasons.environment_memory_status=smcEvidence.status;
         reasons.environment_memory_sample=smcEvidence.sample_size;
         reasons.environment_memory_win_rate=smcEvidence.win_rate*100.0;
         reasons.environment_memory_avg_r=smcEvidence.avg_r;
         reasons.environment_memory_profit_factor=smcEvidence.profit_factor;
         reasons.environment_memory_adjustment=smcEvidence.adjustment;
        }
      else reasons.environment_memory_status="UNKNOWN";
     }

   reasons.selected_strategy=selected;
   reasons.selected_strategy_score=selectedScore;
  }

TradeSetup CTradeDecision::BuildSMC(bool forBuy,double confidence,const SetupReasons &reasons)
  {
   TradeSetup setup;
   ZeroMemory(setup);
   if(m_priceRef==NULL||m_fvgCtx==NULL)return setup;

   FVGZone entryFVG;
   if(!FindEntryFVG(forBuy?FVG_BULL:FVG_BEAR,entryFVG))return setup;
   double atr=m_fvgCtx.candles.GetATR(0);
   if(atr<=0)return setup;

   setup.type=forBuy?ORDER_TYPE_BUY:ORDER_TYPE_SELL;
   setup.entry_top=entryFVG.top;
   setup.entry_bottom=entryFVG.bottom;
   setup.invalidation=forBuy?(entryFVG.bottom-0.05*atr):(entryFVG.top+0.05*atr);
   setup.stop_loss=forBuy?(entryFVG.bottom-m_slBufferATR*atr):(entryFVG.top+m_slBufferATR*atr);
   setup.stop_loss=EnforceSpreadFloor(m_priceRef.Symbol(),forBuy?setup.entry_top:setup.entry_bottom,setup.stop_loss,forBuy);
   if((forBuy&&setup.stop_loss>=setup.invalidation)||(!forBuy&&setup.stop_loss<=setup.invalidation))return setup;

   CTargetSelector::AssignTargets(setup,m_liqCtx,m_priceRef.Symbol(),atr,forBuy?setup.entry_bottom:setup.entry_top);
   setup.confidence=MathMax(0.0,MathMin(confidence,100.0));
   setup.creation_time=TimeCurrent();
   setup.active=true;
   setup.reasons=reasons;
   return setup;
  }

bool CTradeDecision::BuildNonSMC(bool forBuy,ENUM_SELECTED_STRATEGY selected,double confidence,
                                 const SetupReasons &reasons,TradeSetup &out)
  {
   ZeroMemory(out);
   bool built=false;
   if(selected==STRATEGY_MOMENTUM_BREAKOUT)
      built=CStrategySetupBuilders::BuildMomentum(forBuy,confidence,reasons,m_priceRef,m_bosCtx,m_liqCtx,out);
   else if(selected==STRATEGY_MEAN_REVERSION)
      built=CStrategySetupBuilders::BuildMeanReversion(forBuy,confidence,reasons,m_priceRef,m_srCtx,m_liqCtx,out);
   else if(selected==STRATEGY_KEY_LEVEL)
      built=CStrategySetupBuilders::BuildKeyLevel(forBuy,confidence,reasons,m_priceRef,m_srCtx,m_liqCtx,out);
   if(!built)return false;

   out.stop_loss=EnforceSpreadFloor(m_priceRef.Symbol(),ResolveExecutionEntry(out),out.stop_loss,forBuy);
   if((forBuy&&out.stop_loss>=out.invalidation)||(!forBuy&&out.stop_loss<=out.invalidation))
     {
      ZeroMemory(out);
      return false;
     }
   out.reasons.selected_strategy=selected;
   out.reasons.selected_strategy_score=confidence;
   return true;
  }

TradeSetup CTradeDecision::Generate(bool forBuy)
  {
   TradeSetup out;
   ZeroMemory(out);
   if(m_scoring==NULL||m_priceRef==NULL)return out;

   SetupReasons reasons;
   PopulateStrategyReads(forBuy,reasons);

   ENUM_SELECTED_STRATEGY selected=STRATEGY_NONE;
   double selectedScore=0.0;
   SelectPeerStrategy(forBuy,reasons,selected,selectedScore);
   if(selected==STRATEGY_NONE||selectedScore<m_minSelectionScore)
     {
      m_lastSetup=out;
      return out;
     }

   reasons.selected_strategy=selected;
   reasons.selected_strategy_score=selectedScore;
   if(selected==STRATEGY_SMC)
      out=BuildSMC(forBuy,selectedScore,reasons);
   else if(!BuildNonSMC(forBuy,selected,selectedScore,reasons,out))
     {
      ZeroMemory(out);
      m_lastSetup=out;
      return out;
     }

   if(!out.active)
      {
       ZeroMemory(out);
       m_lastSetup=out;
       return out;
      }
   out.reasons.selected_strategy=selected;
   out.reasons.selected_strategy_score=selectedScore;
   m_lastSetup=out;
   return out;
  }

TradeSetup CTradeDecision::GenerateBuySetup(){ return Generate(true); }
TradeSetup CTradeDecision::GenerateSellSetup(){ return Generate(false); }

#endif
//+------------------------------------------------------------------+
