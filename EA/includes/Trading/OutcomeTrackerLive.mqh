//+------------------------------------------------------------------+
//| Trading/OutcomeTrackerLive.mqh                                  |
//+------------------------------------------------------------------+
#ifndef OUTCOMETRACKERLIVE_MQH
#define OUTCOMETRACKERLIVE_MQH
#include "../Core/Config.mqh"
#include "../Core/SignalLogger.mqh"
#include "CalibrationEngine.mqh"
#include "../Signals/SignalPublisher.mqh"

class COutcomeTrackerLive
  {
private:
   PendingSetup m_pending[]; int m_count; int m_maxBars; CSignalLogger* m_logger; CSignalPublisher* m_publisher; CCalibrationEngine m_calibration;
   bool m_calibrationEnabled; string m_symbol; ENUM_TIMEFRAMES m_entryTF; ENUM_FILL_POLICY m_fillPolicy; ENUM_TIMEFRAMES m_replayTF; OutcomeStats m_stats;
   double m_breakEvenAtR,m_partialAtR,m_partialFraction,m_trailATRMult,m_riskPercent; bool m_allowMinLotOverride,m_liveExecution;
   double m_commissionPerLot,m_spreadPoints,m_slippagePoints,m_decayHalfLifeBars; string m_weightVersion;
   int Find(long id){for(int i=0;i<m_count;i++)if(m_pending[i].decisionId==id)return i;return -1;}
   double RValue(const PendingSetup &p) const{if(p.mgmtRiskDist<=0.0||p.lots<=0.0)return 0.0;double ts=SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_SIZE),tv=SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_VALUE);if(ts<=0.0||tv<=0.0)return 0.0;double oneR=p.mgmtRiskDist*(tv/ts)*p.lots;return oneR>0.0?p.realizedPnL/oneR:0.0;}
   void Finalize(int idx,string outcome,double exitPrice)
     {
      if(idx<0||idx>=m_count)return;PendingSetup p=m_pending[idx];double rr=RValue(p);bool sized=p.filled&&p.lots>0.0;
      if(sized&&outcome!="ambiguous"&&outcome!="no_fill")
        {if(p.realizedPnL>0.0000001)m_stats.wins++;else if(p.realizedPnL<-0.0000001)m_stats.losses++;else m_stats.scratches++;m_stats.resolvedCount++;m_stats.netPnL+=p.realizedPnL;if(p.realizedPnL>0)m_stats.grossProfit+=p.realizedPnL;if(p.realizedPnL<0)m_stats.grossLoss+=-p.realizedPnL;m_stats.totalCommission+=p.totalCommission;m_stats.totalSpreadCost+=p.totalSpreadCost;m_stats.totalSlippageCost+=p.totalSlippageCost;m_stats.sumRMultiple+=rr;if(m_calibrationEnabled)m_calibration.Record(p.confidenceAtSignal,p.realizedPnL);}
      else if(outcome=="ambiguous")m_stats.ambiguous++;
      if(m_logger!=NULL)m_logger.LogOutcome(p,m_symbol,m_entryTF,outcome,exitPrice,m_fillPolicy);
      if(m_publisher!=NULL&&p.decisionId>0){bool buy=p.setup.type==ORDER_TYPE_BUY;double mfeR=0.0,maeR=0.0;if(p.filled&&p.riskDist>0){double mfe=buy?(p.mfePrice-p.entryRef):(p.entryRef-p.mfePrice);double mae=buy?(p.entryRef-p.maePrice):(p.maePrice-p.entryRef);mfeR=mfe/p.riskDist;maeR=mae/p.riskDist;}m_publisher.PublishOutcome(m_publisher.SignalIdForDecision(p.decisionId),m_symbol,buy?"BUY":"SELL",outcome,rr,mfeR,maeR,p.barsElapsed,p.barsToFill,p.filled,EnumToString(p.setup.reasons.regime),EnumToString(p.setup.reasons.session),EnumToString(p.setup.reasons.sweep_grade),p.setup.reasons.htf_ob_confluence,p.confidenceAtSignal,p.confidenceDecayed,p.decayBars);}
      for(int j=idx;j<m_count-1;j++)m_pending[j]=m_pending[j+1];m_count--;ArrayResize(m_pending,m_count);
     }
   void SimFill(int i,double price,datetime t){if(i<0||i>=m_count||m_pending[i].filled)return;PendingSetup p=m_pending[i];p.filled=true;p.fillTime=t;p.barsToFill=0;p.entryRef=price;p.entryFillPrice=price;p.mfePrice=price;p.maePrice=price;p.riskDist=MathAbs(price-p.setup.stop_loss);p.mgmtRiskDist=p.riskDist;m_pending[i]=p;}
public:
   COutcomeTrackerLive():m_count(0),m_maxBars(100),m_logger(NULL),m_publisher(NULL),m_calibrationEnabled(false),m_symbol(""),m_entryTF(PERIOD_CURRENT),m_fillPolicy(FILL_CONSERVATIVE),m_replayTF(PERIOD_M1),m_breakEvenAtR(1.0),m_partialAtR(2.0),m_partialFraction(0.5),m_trailATRMult(1.5),m_riskPercent(0.5),m_allowMinLotOverride(true),m_liveExecution(true),m_commissionPerLot(7.0),m_spreadPoints(10.0),m_slippagePoints(2.0),m_decayHalfLifeBars(12.0),m_weightVersion(""){ZeroMemory(m_stats);}
   void Init(CSignalLogger* logger,string symbol,ENUM_TIMEFRAMES tf,int maxBars,ENUM_FILL_POLICY fp=FILL_CONSERVATIVE,ENUM_TIMEFRAMES replayTF=PERIOD_M1){m_logger=logger;m_symbol=symbol;m_entryTF=tf;m_maxBars=MathMax(5,maxBars);m_fillPolicy=fp;m_replayTF=replayTF;m_count=0;ArrayResize(m_pending,0);ZeroMemory(m_stats);}
   void ConfigureExecutionMode(bool live){m_liveExecution=live;}
   void ConfigureSimulation(double risk,bool allow,double be,double partial,double frac,double trail,double comm,double spread,double slip){m_riskPercent=risk;m_allowMinLotOverride=allow;m_breakEvenAtR=be;m_partialAtR=partial;m_partialFraction=MathMax(0.0,MathMin(1.0,frac));m_trailATRMult=trail;m_commissionPerLot=MathMax(0.0,comm);m_spreadPoints=MathMax(0.0,spread);m_slippagePoints=MathMax(0.0,slip);}
   void ConfigureCalibration(bool enabled,int minSample=30){m_calibrationEnabled=enabled;m_calibration.Init(m_symbol,minSample);}
   void ConfigureConfidenceDecay(double halfLife=12.0){m_decayHalfLifeBars=halfLife;}
   void ConfigurePublishing(CSignalPublisher* p,string version){m_publisher=p;m_weightVersion=version;}
   int ActiveCount()const{return m_count;} OutcomeStats GetStats()const{return m_stats;}
   double GetCalibratedProbability(double confidence,int &sample,bool &enough)const{return m_calibration.GetCalibratedProbability(confidence,sample,enough);}
   void AddSetup(TradeSetup &setup,long decisionId=-1){if(!setup.active||decisionId<=0||Find(decisionId)>=0)return;PendingSetup p;ZeroMemory(p);p.setup=setup;p.decisionId=decisionId;p.entryRef=ResolveExecutionEntry(setup);p.riskDist=MathAbs(p.entryRef-setup.stop_loss);p.sizingEntryPrice=p.entryRef;p.mgmtRiskDist=p.riskDist;p.mfePrice=p.entryRef;p.maePrice=p.entryRef;p.currentSL=setup.stop_loss;p.confidenceAtSignal=setup.confidence;p.confidenceDecayed=setup.confidence;int n=m_count++;ArrayResize(m_pending,m_count);m_pending[n]=p;}
   bool MarkExecuted(long id,double fill,datetime t,double volume){int i=Find(id);if(i<0||fill<=0.0)return false;PendingSetup p=m_pending[i];if(p.filled)return true;p.filled=true;p.entryFillPrice=fill;p.entryRef=fill;p.fillTime=t;p.barsToFill=0;p.lots=volume;p.remainingLots=volume;p.riskDist=MathAbs(fill-p.setup.stop_loss);p.mgmtRiskDist=p.riskDist;p.mfePrice=fill;p.maePrice=fill;p.currentSL=p.setup.stop_loss;m_pending[i]=p;return true;}
   bool RestoreExecuted(TradeSetup &setup,long id,double fill,datetime t,double volume){AddSetup(setup,id);return MarkExecuted(id,fill,t,volume);}
   bool MarkClosed(long id,double exitPrice,datetime t,double netPnl,double commission,double swap,double fee,bool stillOpen,string outcome){int i=Find(id);if(i<0)return false;PendingSetup p=m_pending[i];if(!p.filled)return false;p.realizedPnL+=netPnl;p.totalCommission+=commission;p.totalSpreadCost+=swap;p.totalSlippageCost+=fee;if(stillOpen){m_pending[i]=p;return true;}m_pending[i]=p;Finalize(i,outcome,exitPrice);return true;}
   void Update(CTFContext* ctx)
     {
      if(ctx==NULL||ctx.candles.Total()<3||ctx.candles.Timeframe()!=m_entryTF)return;CandleData bar=ctx.candles.GetCandle(1);if(bar.time<=0)return;
      for(int i=m_count-1;i>=0;i--){PendingSetup p=m_pending[i];int shift=iBarShift(m_symbol,m_entryTF,p.setup.creation_time,false);datetime creationBar=shift>=0?iTime(m_symbol,m_entryTF,shift):p.setup.creation_time;
       if(!p.filled&&!m_liveExecution&&bar.time>creationBar){bool buy=p.setup.type==ORDER_TYPE_BUY;bool touched=buy?(bar.low<=p.entryRef):(bar.high>=p.entryRef);if(touched){SimFill(i,p.entryRef,bar.time);p=m_pending[i];}}
       if(!p.filled){p.barsElapsed++;p.lastBarTime=bar.time;m_pending[i]=p;if(p.barsElapsed>=m_maxBars)Finalize(i,"no_fill",bar.close);continue;}
       p=m_pending[i];int fshift=iBarShift(m_symbol,m_entryTF,p.fillTime,false);datetime fillBar=fshift>=0?iTime(m_symbol,m_entryTF,fshift):p.fillTime;if(bar.time<=fillBar)continue;if(p.lastBarTime==bar.time)continue;p.barsElapsed++;p.lastBarTime=bar.time;bool buy=p.setup.type==ORDER_TYPE_BUY;if(buy){if(bar.high>p.mfePrice)p.mfePrice=bar.high;if(bar.low<p.maePrice)p.maePrice=bar.low;}else{if(bar.low<p.mfePrice)p.mfePrice=bar.low;if(bar.high>p.maePrice)p.maePrice=bar.high;}if(m_decayHalfLifeBars>0){p.decayBars=p.barsElapsed;p.confidenceDecayed=p.confidenceAtSignal*MathPow(0.5,(double)p.decayBars/m_decayHalfLifeBars);}m_pending[i]=p;if(p.barsElapsed>=m_maxBars)Finalize(i,"timeout",bar.close);
      }
     }
   bool GetFillState(datetime creationTime,long id,bool &filled,double &fillPrice,datetime &fillTime,int &barsToFill){for(int i=0;i<m_count;i++)if(m_pending[i].setup.creation_time==creationTime&&(id<0||m_pending[i].decisionId==id)){filled=m_pending[i].filled;fillPrice=m_pending[i].entryFillPrice;fillTime=m_pending[i].fillTime;barsToFill=m_pending[i].barsToFill;return true;}return false;}
  };
#endif
//+------------------------------------------------------------------+
