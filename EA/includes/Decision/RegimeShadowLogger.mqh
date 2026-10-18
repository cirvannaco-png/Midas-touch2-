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
   bool                       m_rolloverConfigured;
   int                        m_rolloverStartMinute;
   int                        m_rolloverEndMinute;

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

   string RolloverStatus(datetime serverNow)
     {
      if(!m_rolloverConfigured) return "NOT_CONFIGURED";
      if(serverNow<=0) return "UNKNOWN_SERVER_TIME";
      MqlDateTime t;
      if(!TimeToStruct(serverNow,t)) return "UNKNOWN_SERVER_TIME";
      int nowMinute=t.hour*60+t.min;
      bool inWindow=false;
      if(m_rolloverStartMinute==m_rolloverEndMinute)
         return "INVALID_EQUAL_BOUNDARIES";
      if(m_rolloverStartMinute<m_rolloverEndMinute)
         inWindow=(nowMinute>=m_rolloverStartMinute && nowMinute<m_rolloverEndMinute);
      else
         inWindow=(nowMinute>=m_rolloverStartMinute || nowMinute<m_rolloverEndMinute);
      return inWindow ? "IN_CONFIGURED_WINDOW_TELEMETRY_ONLY" : "OUTSIDE_CONFIGURED_WINDOW";
     }

   string SpreadStatus(double spreadToAtr,double spreadPoints)
     {
      if(spreadPoints<0.0 || spreadToAtr<0.0) return "UNKNOWN_SPREAD";
      // Telemetry label only. It never blocks or changes an order.
      if(spreadToAtr>=0.15) return "HIGH_SPREAD_TO_ATR_REVIEW";
      return "OBSERVED_WITHOUT_GATE";
     }

public:
                        CRegimeShadowLogger() : m_enabled(false),m_lastBuyKey(""),m_lastSellKey(""),
                                                 m_rolloverConfigured(false),m_rolloverStartMinute(0),
                                                 m_rolloverEndMinute(0) {}
   void                 Configure(bool enabled) { m_enabled=enabled; }
   bool                 ConfigureRolloverTelemetry(bool enabled,int startHour,int startMinute,int endHour,int endMinute)
     {
      if(!enabled)
        {
         m_rolloverConfigured=false;
         return true;
        }
      if(startHour<0 || startHour>23 || endHour<0 || endHour>23 ||
         startMinute<0 || startMinute>59 || endMinute<0 || endMinute>59)
        {
         m_rolloverConfigured=false;
         return false;
        }
      int start=startHour*60+startMinute;
      int finish=endHour*60+endMinute;
      if(start==finish)
        {
         m_rolloverConfigured=false;
         return false;
        }
      m_rolloverStartMinute=start;
      m_rolloverEndMinute=finish;
      m_rolloverConfigured=true;
      return true;
     }

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
                   "SpreadPoints","PointSize","ATR","SpreadToATR","SpreadAssessment",
                   "BrokerMarketAvailability","BrokerScheduleReason","RolloverStatus",
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
                SpreadStatus(spreadAtr,reasons.spread_points),availability,scheduleReason,RolloverStatus(serverNow),
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
