//+------------------------------------------------------------------+
//| Decision/DecisionTraceLogger.mqh                                 |
//| Append-only signal-to-decision evidence, including rejected paths|
//+------------------------------------------------------------------+
#ifndef MIDAS_DECISIONTRACELOGGER_MQH
#define MIDAS_DECISIONTRACELOGGER_MQH

#include "../Core/Config.mqh"
#include "TradeDecision.mqh"

class CDecisionTraceLogger
  {
private:
   string m_symbol;
   string m_filename;

   string SignalIdFor(const TradeSetup &setup,const string symbol)
     {
      string direction=(setup.type==ORDER_TYPE_BUY)?"BUY":"SELL";
      return StringFormat("%s_%s_%d",symbol,direction,(long)setup.creation_time);
     }

public:
   void Init(const string symbol)
     {
      m_symbol=(symbol=="")?_Symbol:symbol;
      string safe=m_symbol;
      StringReplace(safe,"/","_");
      StringReplace(safe,"\\","_");
      m_filename="MidasTouch_DecisionTrace_"+safe+".csv";
     }

   bool Log(const TradeSetup &setup,const TradeDecisionRecord &decision)
     {
      if(!setup.active || setup.creation_time<=0)
         return false;

      ResetLastError();
      int flags=FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ;
      int handle=FileOpen(m_filename,flags,',');
      if(handle==INVALID_HANDLE)
        {
         PrintFormat("MidasTouch DecisionTrace: cannot open %s (error %d).",m_filename,GetLastError());
         return false;
        }

      if(FileSize(handle)==0)
        {
         FileWrite(handle,"SignalID","DecisionID","Decision","DecisionValid","DecisionTime",
                   "SignalTime","Symbol","Direction","EntryTF","Confidence","SpreadPoints",
                   "EntryTop","EntryBottom","Invalidation","StopLoss","TP1","TP2","FinalTP",
                   "ReduceRisk","ExecutionAuthorized","Reason","DecisionFingerprint",
                   "SelectedStrategy","Regime","WeightVersion","StrategyVersion",
                   "ModelVersion","CalibrationVersion","EnvironmentKey");
        }

      FileSeek(handle,0,SEEK_END);
      string direction=(setup.type==ORDER_TYPE_BUY)?"BUY":"SELL";
      bool execute=(decision.action==POLICY_EXECUTE_ONLY || decision.action==POLICY_EXECUTE_AND_SIGNAL);
      FileWrite(handle,SignalIdFor(setup,m_symbol),
                decision.decision_id,
                TradePolicyToString(decision.action),
                decision.valid?"true":"false",
                TimeToString(decision.decided_time,TIME_DATE|TIME_SECONDS),
                TimeToString(setup.creation_time,TIME_DATE|TIME_SECONDS),
                m_symbol,direction,EnumToString(decision.timeframe),
                DoubleToString(decision.confidence,2),
                DoubleToString(decision.spread_points,2),
                DoubleToString(setup.entry_top,_Digits),
                DoubleToString(setup.entry_bottom,_Digits),
                DoubleToString(setup.invalidation,_Digits),
                DoubleToString(setup.stop_loss,_Digits),
                DoubleToString(setup.tp1,_Digits),
                DoubleToString(setup.tp2,_Digits),
                DoubleToString(setup.final_tp,_Digits),
                decision.reduce_risk?"true":"false",
                execute?"true":"false",
                decision.reason,
                decision.decision_fingerprint,
                EnumToString(setup.reasons.selected_strategy),
                EnumToString(setup.reasons.regime),
                decision.weight_version,decision.strategy_version,
                decision.model_version,decision.calibration_version,
                decision.environment_key);
      FileFlush(handle);
      FileClose(handle);
      return true;
     }
  };

#endif
//+------------------------------------------------------------------+
