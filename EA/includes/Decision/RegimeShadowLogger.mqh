//+------------------------------------------------------------------+
//|                                  Decision/RegimeShadowLogger.mqh  |
//| Passive regime/selection telemetry; never participates in routing. |
//+------------------------------------------------------------------+
#ifndef REGIMESHADOWLOGGER_MQH
#define REGIMESHADOWLOGGER_MQH

#include "../Core/Config.mqh"
#include "../Core/BrokerMarketAvailability.mqh"

class CRegimeShadowLogger
  {
private:
   bool                       m_enabled;
   string                     m_lastBuyKey;
   string                     m_lastSellKey;
   CBrokerMarketAvailability  m_marketAvailability;

   string SafeFilePart(string value)
     {
      StringReplace(value,"/","_");
      StringReplace(value,"\\","_");
      StringReplace(value,":","_");
      StringReplace(value,"*","_");
      StringReplace(value,"?","_");
      StringReplace(value,"\"","_");
      StringReplace(value,"<","_");
      StringReplace(value,">","_");
      StringReplace(value,"|","_");
      return value;
     }

   string FileName(const string symbol,ENUM_TIMEFRAMES timeframe)
     {
      return "MidasTouch_RegimeShadow_"+SafeFilePart(symbol)+"_"+EnumToString(timeframe)+".csv";
     }

   string SessionStatus(bool allowed)
     {
      return allowed ? "ALLOWED" : "BLOCKED_BY_LIQUIDITY_SESSION_POLICY";
     }

public:
                        CRegimeShadowLogger() : m_enabled(false),m_lastBuyKey(""),m_lastSellKey("") {}
   void                 Configure(bool enabled) { m_enabled=enabled; }

   // Records the already-computed live decision path. No value returned by
   // this method can affect selected strategy, setup construction, risk, or orders.
   bool Log(const string symbol,ENUM_TIMEFRAMES timeframe,datetime barTime,bool isBuy,
            const SetupReasons &reasons,ENUM_SELECTED_STRATEGY selected,double selectedScore,
            const string status,const string rejectionReason,const string signalId="",
            double entry=0.0,double invalidation=0.0,double stopLoss=0.0,
            double tp1=0.0,double tp2=0.0,double finalTp=0.0)
     {
      if(!m_enabled) return true;
      string direction=isBuy ? "BUY" : "SELL";
      string eventId=StringFormat("%s_%d_%I64d_%s",symbol,(int)timeframe,(long)barTime,direction);
      string key=eventId+"|"+EnumToString(reasons.regime)+"|"+
                 EnumToString(reasons.vol_regime)+"|"+EnumToString(reasons.phase)+"|"+
                 EnumToString(selected)+"|"+status+"|"+rejectionReason;
      if(isBuy && key==m_lastBuyKey) return true;
      if(!isBuy && key==m_lastSellKey) return true;

      datetime serverNow=TimeTradeServer();
      string scheduleReason="";
      string availability=m_marketAvailability.Probe(symbol,serverNow,scheduleReason);
      double spreadAtr=0.0;
      if(reasons.atr_value>0.0 && reasons.point_size>0.0)
         spreadAtr=(reasons.spread_points*reasons.point_size)/reasons.atr_value;

      int flags=FILE_CSV|FILE_READ|FILE_WRITE|FILE_SHARE_READ|FILE_ANSI;
      string filename=FileName(symbol,timeframe);
      int handle=FileOpen(filename,flags,',');
      if(handle==INVALID_HANDLE)
        {
         Print("MedisTouch RegimeShadowLogger: cannot open ",filename," err=",GetLastError());
         return false;
        }
      if(FileSize(handle)==0)
         FileWrite(handle,"SchemaVersion","EventID","SignalID","UtcTime","BrokerServerTime",
                   "Symbol","Timeframe","BarTime","BarEpoch","Direction",
                   "Regime","VolatilityRegime","MarketPhase","TrendStrength",
                   "SelectedStrategy","SelectedScore","MomentumScore","BreakoutScore","BreakoutClass",
                   "ReversionScore","ReversionClass","KeyLevelSource","KeyLevelReaction","KeyLevelScore",
                   "SelectionStatus","RejectionReason","LiquiditySession","LiquidityPolicy",
                   "SpreadPoints","PointSize","ATR","SpreadToATR",
                   "BrokerMarketAvailability","BrokerScheduleReason","RolloverPolicy",
                   "EntryReference","ThesisInvalidation","ProtectiveStop","TP1","TP2","FinalTP");
      FileSeek(handle,0,SEEK_END);
      FileWrite(handle,1,eventId,signalId,
                TimeToString(TimeGMT(),TIME_DATE|TIME_SECONDS),
                serverNow>0 ? TimeToString(serverNow,TIME_DATE|TIME_SECONDS) : "UNKNOWN",
                symbol,EnumToString(timeframe),TimeToString(barTime,TIME_DATE|TIME_SECONDS),(long)barTime,direction,
                EnumToString(reasons.regime),EnumToString(reasons.vol_regime),EnumToString(reasons.phase),
                DoubleToString(reasons.trend_strength,3),EnumToString(selected),DoubleToString(selectedScore,2),
                DoubleToString(reasons.momentum_score,2),DoubleToString(reasons.breakout_score,2),
                EnumToString(reasons.breakout_class),DoubleToString(reasons.reversion_score,2),
                EnumToString(reasons.reversion_class),EnumToString(reasons.keylevel_source),
                EnumToString(reasons.keylevel_reaction),DoubleToString(reasons.keylevel_score,2),
                status,rejectionReason,EnumToString(reasons.session),SessionStatus(reasons.session_ok),
                DoubleToString(reasons.spread_points,2),DoubleToString(reasons.point_size,10),
                DoubleToString(reasons.atr_value,10),DoubleToString(spreadAtr,6),
                availability,scheduleReason,"NOT_CONFIGURED",
                DoubleToString(entry,_Digits),DoubleToString(invalidation,_Digits),
                DoubleToString(stopLoss,_Digits),DoubleToString(tp1,_Digits),
                DoubleToString(tp2,_Digits),DoubleToString(finalTp,_Digits));
      bool ok=(GetLastError()==0);
      FileClose(handle);
      if(isBuy) m_lastBuyKey=key; else m_lastSellKey=key;
      return ok;
     }
  };
#endif
//+------------------------------------------------------------------+
