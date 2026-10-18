//+------------------------------------------------------------------+
//|                                  Core/BrokerMarketAvailability.mqh |
//| Read-only probe of the broker's symbol-specific trade schedule.   |
//+------------------------------------------------------------------+
#ifndef BROKERMARKETAVAILABILITY_MQH
#define BROKERMARKETAVAILABILITY_MQH

// This class is intentionally observational. It does not place orders and
// does not replace CSessionFilter: broker market availability, liquidity
// windows, spread, rollover, and volatility are separate dimensions.
class CBrokerMarketAvailability
  {
private:
   long SecondsOfDay(datetime value)
     {
      long seconds=((long)value)%86400;
      if(seconds<0) seconds+=86400;
      return seconds;
     }

   bool Contains(datetime from,datetime to,long nowSeconds)
     {
      long start=SecondsOfDay(from);
      long finish=SecondsOfDay(to);
      // A broker that returns equal boundaries may be describing an all-day
      // session. This remains telemetry until verified on the target broker.
      if(start==finish) return true;
      if(start<finish) return (nowSeconds>=start && nowSeconds<finish);
      // Overnight interval, e.g. 22:00-02:00.
      return (nowSeconds>=start || nowSeconds<finish);
     }

public:
   string Probe(const string symbol,datetime serverTime,string &reason)
     {
      reason="UNKNOWN";
      if(StringLen(symbol)==0)
        {
         reason="EMPTY_SYMBOL";
         return "UNKNOWN";
        }
      if(serverTime<=0)
        {
         reason="SERVER_TIME_UNAVAILABLE";
         return "UNKNOWN";
        }

      MqlDateTime now;
      if(!TimeToStruct(serverTime,now))
        {
         reason="SERVER_TIME_INVALID";
         return "UNKNOWN";
        }
      long nowSeconds=(long)now.hour*3600+(long)now.min*60+(long)now.sec;
      int previousDay=(now.day_of_week+6)%7;
      bool anySchedule=false;
      bool matched=false;
      int matchedDay=-1;
      uint matchedSession=0;

      // Scan the broker's weekly symbol schedule. The previous weekday must
      // also be checked for sessions that cross midnight.
      for(int day=0;day<7;day++)
        {
         for(uint session=0;session<24;session++)
           {
            datetime from=0,to=0;
            if(!SymbolInfoSessionTrade(symbol,(ENUM_DAY_OF_WEEK)day,session,from,to))
               break;
            anySchedule=true;
            if(day!=now.day_of_week && day!=previousDay)
               continue;
            if(Contains(from,to,nowSeconds))
              {
               matched=true;
               matchedDay=day;
               matchedSession=session;
               break;
              }
           }
         if(matched) break;
        }

      if(matched)
        {
         reason=StringFormat("SCHEDULE_MATCH_DAY_%d_SESSION_%d",matchedDay,matchedSession);
         return "OPEN";
        }
      if(anySchedule)
        {
         reason="WEEKLY_SCHEDULE_FOUND_BUT_NO_CURRENT_INTERVAL_MATCHED";
         return "CLOSED";
        }
      reason="BROKER_SCHEDULE_NOT_EXPOSED_BY_TERMINAL";
      return "UNKNOWN";
     }
  };
#endif
//+------------------------------------------------------------------+
