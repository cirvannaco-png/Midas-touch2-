//+------------------------------------------------------------------+
//| Trading/StrategyTradeZone.mqh                                    |
//| Hierarchical decision construction and trade-quality admission.   |
//+------------------------------------------------------------------+
#ifndef STRATEGYTRADEZONE_MQH
#define STRATEGYTRADEZONE_MQH

#include "../Core/Config.mqh"
#include "../Core/CandleData.mqh"
#include "../Analysis/TFContext.mqh"
#include "../Analysis/Scoring.mqh"
#include "../Decision/DecisionQuality.mqh"
#include "StrategySetupBuilders.mqh"
#include "Targets.mqh"
#include "EnvironmentStrategyMemory.mqh"

extern CTFContext* g_chartCtx;
extern CTFContext* g_trendCtx;
extern CTFContext* g_bosCtx;

class CTradeDecision
  {
private:
   CCandleData*                m_priceRef;
   CTFContext*                 m_fvgCtx;
   CTFContext*                 m_liqCtx;
   CTFContext*                 m_srCtx;
   CTFContext*                 m_bosCtx;
   CScoringEngine*              m_scoring;
   CEnvironmentStrategyMemory*  m_environmentMemory;
   TradeSetup                   m_lastSetup;
   FVGZone                      m_lastEntryFVG;
   bool                         m_hasEntryFVG;

   double m_slBufferATR;
   double m_minStopSpreadMult;
   double m_fvgMaxDistATR;
   double m_minSelectionScore;

   bool   m_enableDecisionArchitecture;
   bool   m_enableStructuralValidator;
   bool   m_enableEnvironmentHardBlock;
   bool   m_requireCausalFVG;
   int    m_causalFVGMaxBars;
   double m_minQualityScore;
   double m_maxExecutionSpreadPoints;

   bool FindEntryFVG(ENUM_FVG_DIR dir,FVGZone &out);
   bool IsCausalFVG(const FVGZone &zone,const InducementResult &ind) const;
   double EnforceSpreadFloor(string symbol,double entry,double stopLoss,bool isBuy);
   void BuildRegimeVector(bool forBuy,SetupReasons &out);
   void PopulateFVGDiagnostics(bool forBuy,SetupReasons &out);
   void PopulateStrategyReads(bool forBuy,SetupReasons &out);
   void SelectPeerStrategy(bool forBuy,SetupReasons &reasons,ENUM_SELECTED_STRATEGY &selected,double &selectedScore);
   TradeSetup BuildSMC(bool forBuy,double confidence,const SetupReasons &reasons);
   bool BuildNonSMC(bool forBuy,ENUM_SELECTED_STRATEGY selected,double confidence,const SetupReasons &reasons,TradeSetup &out);
   bool ApplyQualityFirewall(TradeSetup &setup,bool isSMC);
   TradeSetup BuildRejected(bool forBuy,const SetupReasons &reasons,const string reason,ENUM_FIREWALL_LAYER layer);
   TradeSetup Generate(bool forBuy);

public:
   CTradeDecision();
   void Init(CCandleData* priceRef,CTFContext* fvgCtx,CTFContext* liqCtx,CScoringEngine* scoring,
             double slBufferATR=0.25,double minStopSpreadMult=3.0,double fvgMaxDistATR=1.25,
             double minSelectionScore=60.0,CTFContext* srCtx=NULL,CTFContext* bosCtx=NULL,
             CEnvironmentStrategyMemory* environmentMemory=NULL);

   void ConfigureDecisionArchitecture(bool enabled=true,bool enableStructuralValidator=true,
                                      bool enableEnvironmentHardBlock=false,bool requireCausalFVG=false,
                                      int causalFVGMaxBars=12,double minQualityScore=60.0,
                                      double maxExecutionSpreadPoints=0.0);

   void FinalizeWithCalibration(TradeSetup &setup,bool requireCalibratedProbability,
                                double minCalibratedProbability);

   TradeSetup GenerateBuySetup();
   TradeSetup GenerateSellSetup();
   TradeSetup GetLastSetup()const{return m_lastSetup;}
  };

CTradeDecision::CTradeDecision()
  {
   ZeroMemory(m_lastSetup);
   ZeroMemory(m_lastEntryFVG);
   m_priceRef=NULL;
   m_fvgCtx=NULL;
   m_liqCtx=NULL;
   m_srCtx=NULL;
   m_bosCtx=NULL;
   m_scoring=NULL;
   m_environmentMemory=NULL;
   m_hasEntryFVG=false;
   m_slBufferATR=0.25;
   m_minStopSpreadMult=3.0;
   m_fvgMaxDistATR=1.25;
   m_minSelectionScore=60.0;
   m_enableDecisionArchitecture=true;
   m_enableStructuralValidator=true;
   m_enableEnvironmentHardBlock=false;
   m_requireCausalFVG=false;
   m_causalFVGMaxBars=12;
   m_minQualityScore=60.0;
   m_maxExecutionSpreadPoints=0.0;
  }

void CTradeDecision::Init(CCandleData* priceRef,CTFContext* fvgCtx,CTFContext* liqCtx,CScoringEngine* scoring,
                          double slBufferATR,double minStopSpreadMult,double fvgMaxDistATR,double minSelectionScore,
                          CTFContext* srCtx,CTFContext* bosCtx,CEnvironmentStrategyMemory* environmentMemory)
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

void CTradeDecision::ConfigureDecisionArchitecture(bool enabled,bool enableStructuralValidator,
                                                    bool enableEnvironmentHardBlock,bool requireCausalFVG,
                                                    int causalFVGMaxBars,double minQualityScore,
                                                    double maxExecutionSpreadPoints)
  {
   m_enableDecisionArchitecture=enabled;
   m_enableStructuralValidator=enableStructuralValidator;
   m_enableEnvironmentHardBlock=enableEnvironmentHardBlock;
   m_requireCausalFVG=requireCausalFVG;
   m_causalFVGMaxBars=MathMax(1,causalFVGMaxBars);
   m_minQualityScore=MathMax(0.0,MathMin(100.0,minQualityScore));
   m_maxExecutionSpreadPoints=MathMax(0.0,maxExecutionSpreadPoints);
  }

double CTradeDecision::EnforceSpreadFloor(string symbol,double entry,double stopLoss,bool isBuy)
  {
   if(m_minStopSpreadMult<=0) return stopLoss;
   long sp=SymbolInfoInteger(symbol,SYMBOL_SPREAD);
   double pt=SymbolInfoDouble(symbol,SYMBOL_POINT);
   if(sp<=0||pt<=0) return stopLoss;
   double minDist=(double)sp*pt*m_minStopSpreadMult;
   double cur=MathAbs(entry-stopLoss);
   if(cur>=minDist) return stopLoss;
   return isBuy?(entry-minDist):(entry+minDist);
  }

bool CTradeDecision::FindEntryFVG(ENUM_FVG_DIR dir,FVGZone &out)
  {
   ZeroMemory(out);
   if(m_fvgCtx==NULL||m_priceRef==NULL||m_priceRef.Total()==0) return false;
   double price=m_priceRef.Total()>1 ? m_priceRef.GetCandle(1).close : 0.0;
   double atr=m_fvgCtx.candles.GetATR(1);
   if(price<=0||atr<=0) return false;

   bool found=false;
   double bestScore=-1.0;
   for(int i=0;i<m_fvgCtx.fvg.Count();i++)
     {
      FVGZone z=m_fvgCtx.fvg.GetZone(i);
      if(z.dir!=dir) continue;
      if(z.state!=FVG_FRESH&&z.state!=FVG_TESTED) continue;

      double mid=(z.top+z.bottom)/2.0;
      double distATR=MathAbs(price-mid)/atr;
      if(distATR>m_fvgMaxDistATR) continue;

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

bool CTradeDecision::IsCausalFVG(const FVGZone &zone,const InducementResult &ind) const
  {
   if(!ind.bosConfirmed||ind.bosBarIndex<0||zone.bar_index<0) return false;
   // BOS and FVG may be detected on different production timeframes.
   // Never compare raw bar indices across those series. Use event time and
   // convert the elapsed time into bars on the actual FVG timeframe.
   if(ind.bosTime<=0 || zone.time<=ind.bosTime || m_fvgCtx==NULL) return false;
   int tfSeconds=PeriodSeconds(m_fvgCtx.candles.Timeframe());
   if(tfSeconds<=0) return false;
   double elapsed=(double)(zone.time-ind.bosTime);
   int gap=(int)MathCeil(elapsed/(double)tfSeconds);
   return (gap>=1 && gap<=m_causalFVGMaxBars);
  }

void CTradeDecision::BuildRegimeVector(bool forBuy,SetupReasons &out)
  {
   string trend="UNDEFINED";
   if(g_trendCtx!=NULL)
      trend=EnumToString(g_trendCtx.trend.GetCurrentTrend());

   string va=EnumToString(out.va_zone);
   string structure=EnumToString(out.inducement_structure_type);
   out.regime_id=trend+"|"+EnumToString(out.regime)+"|"+EnumToString(out.vol_regime)+
                 "|"+EnumToString(out.session)+"|"+EnumToString(out.phase)+
                 "|VA:"+va+"|LIQ:"+EnumToString(out.liquidity_scope)+
                 "|ARCH:"+EnumToString(out.liquidity_archetype)+"|"+structure+
                 "|SW:"+EnumToString(out.sweep_grade)+"|PD:"+(out.premium_discount_ok?"1":"0");
  }

void CTradeDecision::PopulateFVGDiagnostics(bool forBuy,SetupReasons &out)
  {
   m_hasEntryFVG=FindEntryFVG(forBuy?FVG_BULL:FVG_BEAR,m_lastEntryFVG);
   if(!m_hasEntryFVG)
     {
      out.fvg_state=FVG_INVALIDATED;
      out.fvg_age_bars=-1;
      out.fvg_distance_atr=0.0;
      out.fvg_causal=false;
      out.fvg_bos_age_gap=0;
      return;
     }

   out.fvg_state=m_lastEntryFVG.state;
   out.fvg_age_bars=MathMax(0,iBarShift(m_priceRef.Symbol(),m_fvgCtx.candles.Timeframe(),m_lastEntryFVG.time,false));
   if(m_fvgCtx!=NULL&&m_fvgCtx.candles.Total()>0)
     {
      double price=m_priceRef.Total()>1 ? m_priceRef.GetCandle(1).close : 0.0;
      double atr=m_fvgCtx.candles.GetATR(1);
      double mid=(m_lastEntryFVG.top+m_lastEntryFVG.bottom)/2.0;
      out.fvg_distance_atr=(atr>0.0?MathAbs(price-mid)/atr:0.0);
     }

   InducementResult ind;
   ZeroMemory(ind);
   if(m_scoring!=NULL)
      ind=m_scoring.GetInducement(forBuy);
   out.fvg_causal=IsCausalFVG(m_lastEntryFVG,ind);
   out.fvg_bos_age_gap=0;
   if(ind.bosTime>0 && m_lastEntryFVG.time>ind.bosTime && m_fvgCtx!=NULL)
     {
      int tfSeconds=PeriodSeconds(m_fvgCtx.candles.Timeframe());
      if(tfSeconds>0)
         out.fvg_bos_age_gap=(int)MathCeil((double)(m_lastEntryFVG.time-ind.bosTime)/(double)tfSeconds);
     }
  }

void CTradeDecision::PopulateStrategyReads(bool forBuy,SetupReasons &out)
  {
   ZeroMemory(out);
   m_hasEntryFVG=false;
   if(m_scoring==NULL) return;

   m_scoring.EvaluateReasons(forBuy,out);
   m_scoring.PopulateStrategyDiagnostics(forBuy,0.0,out);
   m_scoring.PopulateConfidenceDiagnostics(out,0.0);
   PopulateFVGDiagnostics(forBuy,out);
   out.selected_strategy=STRATEGY_NONE;
   out.selected_strategy_score=0.0;

   if(m_priceRef!=NULL&&m_priceRef.Total()>0)
     {
      out.spread_points=(double)SymbolInfoInteger(m_priceRef.Symbol(),SYMBOL_SPREAD);
      out.point_size=SymbolInfoDouble(m_priceRef.Symbol(),SYMBOL_POINT);
      out.atr_value=m_priceRef.GetATR(1);
     }

   if(g_trendCtx!=NULL)
     {
      ENUM_TREND_STATE trend=g_trendCtx.trend.GetCurrentTrend();
      if(trend==TREND_BULL_STRONG||trend==TREND_BEAR_STRONG) out.trend_strength=1.0;
      else if(trend==TREND_BULL||trend==TREND_BEAR) out.trend_strength=0.6;
      else out.trend_strength=0.0;
     }

   if(m_liqCtx!=NULL&&m_liqCtx.liquidity.EventCount()>0)
     {
      LiquidityEvent ev=m_liqCtx.liquidity.GetEvent(0);
      bool supports=forBuy?(ev.type==LIQ_SELL_SIDE):(ev.type==LIQ_BUY_SIDE);
      if(supports&&ev.bar_index<=10)
        {
         out.liquidity_score=MathMin(MathMax(ev.strength,0.0),1.0);
         out.liquidity_bucket=out.liquidity_score>=0.75?3:(out.liquidity_score>=0.50?2:(out.liquidity_score>0.0?1:0));
         out.liquidity_event_price=ev.price;
         out.liquidity_event_strength=MathMax(0.0,MathMin(ev.strength,1.0));
         out.liquidity_event_external=ev.external;
        }
     }

   BuildRegimeVector(forBuy,out);
  }

void CTradeDecision::SelectPeerStrategy(bool forBuy,SetupReasons &reasons,
                                        ENUM_SELECTED_STRATEGY &selected,double &selectedScore)
  {
   selected=STRATEGY_NONE;
   selectedScore=0.0;
   if(m_scoring==NULL||reasons.regime==REGIME_UNDEFINED) return;

   bool smcPrecheck=reasons.inducement_valid &&
                    reasons.liquidity_swept &&
                    reasons.bos_confirmed &&
                    reasons.premium_discount_ok &&
                    m_hasEntryFVG;
   if(m_requireCausalFVG) smcPrecheck=smcPrecheck&&reasons.fvg_causal;

   ENUM_SELECTED_STRATEGY challenger=STRATEGY_NONE;
   double challengerScore=-1.0;

   if(reasons.regime==REGIME_TRENDING)
     {
      if(reasons.breakout_class!=BREAKOUT_FAILED&&
         reasons.breakout_class!=BREAKOUT_EXHAUSTION&&
         (reasons.breakout_class==BREAKOUT_EXPANSION||
          reasons.breakout_class==BREAKOUT_LIQUIDITY||
          reasons.momentum_score>0.0))
        {
         challengerScore=MathMax(reasons.momentum_score,reasons.breakout_score);
         challenger=STRATEGY_MOMENTUM_BREAKOUT;
        }
     }
   else if(reasons.regime==REGIME_RANGING)
     {
      if(reasons.reversion_class==REVERSION_VALUE_FADE||
         reasons.reversion_class==REVERSION_LEVEL_REJECTION)
        {
         challengerScore=reasons.reversion_score;
         challenger=STRATEGY_MEAN_REVERSION;
        }
     }
   else if(reasons.regime==REGIME_TRANSITION)
     {
      if(reasons.keylevel_reaction==REACTION_REJECTION||
         reasons.keylevel_reaction==REACTION_RETEST||
         reasons.keylevel_reaction==REACTION_FAILED_BREAK||
         reasons.keylevel_reaction==REACTION_ABSORPTION)
        {
         challengerScore=reasons.keylevel_score;
         challenger=STRATEGY_KEY_LEVEL;
        }
     }

   bool challengerEligible=(challenger!=STRATEGY_NONE);
   double challengerAdjusted=challengerScore;
   EnvironmentMemoryEvidence challengerEvidence;
   ZeroMemory(challengerEvidence);
   bool challengerMemory=false;

   if(challengerEligible&&m_environmentMemory!=NULL)
      challengerMemory=m_environmentMemory.GetEvidence(reasons,challenger,challengerEvidence);

   if(challengerEligible&&m_enableEnvironmentHardBlock&&m_environmentMemory!=NULL&&
      challengerMemory&&m_environmentMemory.IsDegraded(challengerEvidence))
      challengerEligible=false;

   if(challengerEligible&&challengerMemory)
      challengerAdjusted=challengerScore+challengerEvidence.adjustment;

   double smcScore=m_scoring.CalculateConfidence(forBuy);
   // Raw confidence is descriptive/ranking data. Structural admission is
   // decided by smcPrecheck, not by a confidence cutoff.
   bool smcEligible=m_enableStructuralValidator ? smcPrecheck : true;

   double smcAdjusted=smcScore;
   EnvironmentMemoryEvidence smcEvidence;
   ZeroMemory(smcEvidence);
   bool smcMemory=false;

   if(smcEligible&&m_environmentMemory!=NULL)
      smcMemory=m_environmentMemory.GetEvidence(reasons,STRATEGY_SMC,smcEvidence);

   if(smcEligible&&m_enableEnvironmentHardBlock&&m_environmentMemory!=NULL&&
      smcMemory&&m_environmentMemory.IsDegraded(smcEvidence))
      smcEligible=false;

   if(smcEligible&&smcMemory)
      smcAdjusted=smcScore+smcEvidence.adjustment;

   if(challengerEligible&&(!smcEligible||challengerAdjusted>smcAdjusted))
     {
      selected=challenger;
      selectedScore=challengerScore;
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
      selectedScore=smcScore;
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
   m_scoring.PopulateConfidenceDiagnostics(reasons,selectedScore);
  }

TradeSetup CTradeDecision::BuildSMC(bool forBuy,double confidence,const SetupReasons &reasons)
  {
   TradeSetup setup;
   ZeroMemory(setup);
   if(m_priceRef==NULL||m_fvgCtx==NULL) return setup;

   FVGZone entryFVG;
   if(m_hasEntryFVG) entryFVG=m_lastEntryFVG;
   else if(!FindEntryFVG(forBuy?FVG_BULL:FVG_BEAR,entryFVG)) return setup;

   double atr=m_fvgCtx.candles.GetATR(1);
   if(atr<=0.0) return setup;

   setup.reasons=reasons;
   if(setup.reasons.sweep_price<=0.0 || setup.reasons.sweep_time<=0)
      return setup;

   setup.type=forBuy?ORDER_TYPE_BUY:ORDER_TYPE_SELL;
   setup.entry_top=entryFVG.top;
   setup.entry_bottom=entryFVG.bottom;
   // Structural invalidation is tied to the authoritative liquidity sweep,
   // not merely the entry FVG boundary. This makes the thesis boundary
   // immutable to later execution management.
   setup.invalidation=forBuy?(setup.reasons.sweep_price-0.05*atr):(setup.reasons.sweep_price+0.05*atr);
   double entry=ResolveExecutionEntry(setup);
   setup.stop_loss=forBuy?(setup.invalidation-m_slBufferATR*atr):(setup.invalidation+m_slBufferATR*atr);
   setup.stop_loss=EnforceSpreadFloor(m_priceRef.Symbol(),entry,setup.stop_loss,forBuy);

   if((forBuy&&setup.stop_loss>=setup.invalidation)||(!forBuy&&setup.stop_loss<=setup.invalidation))
      return setup;

   setup.reasons.invalidation_distance_atr=MathAbs(entry-setup.invalidation)/atr;

   CTargetSelector::AssignTargets(setup,m_liqCtx,m_priceRef.Symbol(),atr,entry);
   setup.confidence=MathMax(0.0,MathMin(confidence,100.0));
   setup.creation_time=TimeCurrent();
   setup.active=true;
   setup.decision_state=DECISION_TRADE;
   setup.risk_class=RISK_CLASS_MINIMAL;
   setup.setup_lifecycle=SETUP_DETECTED;
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

   if(!built) return false;

   out.stop_loss=EnforceSpreadFloor(m_priceRef.Symbol(),ResolveExecutionEntry(out),out.stop_loss,forBuy);
   if((forBuy&&out.stop_loss>=out.invalidation)||(!forBuy&&out.stop_loss<=out.invalidation))
     {
      ZeroMemory(out);
      return false;
     }

   out.reasons=reasons;
   out.reasons.selected_strategy=selected;
   out.reasons.selected_strategy_score=confidence;
   out.reasons.structural_state=STRUCTURE_NOT_APPLICABLE;
   out.reasons.structural_stage=STRUCTURE_STAGE_NO_STRUCTURE;
   out.active=true;
   out.confidence=MathMax(0.0,MathMin(confidence,100.0));
   out.creation_time=TimeCurrent();
   out.decision_state=DECISION_TRADE;
   out.risk_class=RISK_CLASS_MINIMAL;
   out.setup_lifecycle=SETUP_DETECTED;
   return true;
  }

bool CTradeDecision::ApplyQualityFirewall(TradeSetup &setup,bool isSMC)
  {
   if(!m_enableDecisionArchitecture) return setup.active;
   if(!setup.active) return false;

   CTradeQualityFirewall firewall;
   int degradedMinSample=(m_environmentMemory!=NULL?m_environmentMemory.DegradedMinimumSample():0);
   TradeQualityResult q=firewall.Evaluate(setup,isSMC,m_enableStructuralValidator,m_enableEnvironmentHardBlock,
                                          degradedMinSample,m_minQualityScore,m_maxExecutionSpreadPoints,
                                          m_requireCausalFVG,m_requireFullyValidSMC);
   setup.decision_state=q.decision;
   setup.risk_class=q.riskClass;
   setup.setup_lifecycle=(q.decision==DECISION_WAIT?SETUP_WAITING_RETEST:(q.decision==DECISION_TRADE?SETUP_ENTRY_ELIGIBLE:SETUP_EXPIRED));
   setup.reasons.decision_state=q.decision;
   setup.reasons.decision_reason=q.reason;
   setup.reasons.decision_blocking_layer=q.layer;
   setup.reasons.risk_class=q.riskClass;
   setup.reasons.quality_score=q.qualityScore;
   return true;
  }

void CTradeDecision::FinalizeWithCalibration(TradeSetup &setup,bool requireCalibratedProbability,
                                              double minCalibratedProbability)
  {
   if(!m_enableDecisionArchitecture||!setup.active) return;
   CTradeQualityFirewall firewall;
   firewall.FinalizeWithCalibration(setup,requireCalibratedProbability,minCalibratedProbability);
   setup.reasons.decision_state=setup.decision_state;
  }

TradeSetup CTradeDecision::BuildRejected(bool forBuy,const SetupReasons &reasons,const string reason,ENUM_FIREWALL_LAYER layer)
  {
   TradeSetup out;
   ZeroMemory(out);
   out.type=forBuy?ORDER_TYPE_BUY:ORDER_TYPE_SELL;
   out.creation_time=TimeCurrent();
   out.active=true;
   out.decision_state=DECISION_REJECT;
   out.risk_class=RISK_CLASS_NONE;
   out.setup_lifecycle=SETUP_EXPIRED;
   out.reasons=reasons;
   out.reasons.decision_state=DECISION_REJECT;
   out.reasons.decision_blocking_layer=layer;
   out.reasons.decision_reason=reason;
   return out;
  }

TradeSetup CTradeDecision::Generate(bool forBuy)
  {
   TradeSetup out;
   ZeroMemory(out);
   if(m_scoring==NULL||m_priceRef==NULL)
      return out;

   SetupReasons reasons;
   PopulateStrategyReads(forBuy,reasons);

   ENUM_SELECTED_STRATEGY selected=STRATEGY_NONE;
   double selectedScore=0.0;
   SelectPeerStrategy(forBuy,reasons,selected,selectedScore);

   if(selected==STRATEGY_NONE)
     {
      out=BuildRejected(forBuy,reasons,"no strategy satisfied the current market/regime admission conditions",FIREWALL_STRUCTURE);
      m_lastSetup=out;
      return out;
     }

   reasons.selected_strategy=selected;
   reasons.selected_strategy_score=selectedScore;

   if(selected==STRATEGY_SMC)
      out=BuildSMC(forBuy,selectedScore,reasons);
   else if(!BuildNonSMC(forBuy,selected,selectedScore,reasons,out))
     {
      out=BuildRejected(forBuy,reasons,"selected strategy could not construct a valid executable setup",FIREWALL_RISK);
      m_lastSetup=out;
      return out;
     }

   if(!out.active)
     {
      out=BuildRejected(forBuy,reasons,"selected strategy produced an incomplete setup",FIREWALL_RISK);
      m_lastSetup=out;
      return out;
     }

   out.reasons.selected_strategy=selected;
   out.reasons.selected_strategy_score=selectedScore;
   bool firewallOK=ApplyQualityFirewall(out,selected==STRATEGY_SMC);
   if(!firewallOK) ZeroMemory(out);

   m_lastSetup=out;
   return out;
  }

TradeSetup CTradeDecision::GenerateBuySetup(){return Generate(true);}
TradeSetup CTradeDecision::GenerateSellSetup(){return Generate(false);}

#endif
//+------------------------------------------------------------------+
