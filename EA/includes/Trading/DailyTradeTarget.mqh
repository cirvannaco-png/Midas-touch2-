//+------------------------------------------------------------------+
//| Trading/DailyTradeTarget.mqh                                     |
//| Counts qualified CLOSED trades; never bypasses strategy gates.  |
//+------------------------------------------------------------------+
#ifndef DAILYTRADETARGET_MQH
#define DAILYTRADETARGET_MQH

class CDailyTradeTarget
  {
private:
   int      m_target;
   int      m_count;
   int      m_dateKey;
   bool     m_weekday;
   bool     m_reported;
   double   m_minQualifiedR;
   string   m_storageKey;
   string   m_lockKey;
   ulong    m_magic;

   int DateKey(datetime at)
     {
      MqlDateTime t;
      if(at<=0 || !TimeToStruct(at,t))return 0;
      return t.year*1000+t.day_of_year;
     }

   bool IsWeekday(datetime at)
     {
      MqlDateTime t;
      if(at<=0 || !TimeToStruct(at,t))return false;
      return t.day_of_week>=1 && t.day_of_week<=5;
     }

   string CounterKey(int dateKey)
     {
      // One counter per broker-server date avoids rollover writes clobbering another chart's count.
      return StringFormat("MTC.%I64d.%I64u.%d",AccountInfoInteger(ACCOUNT_LOGIN),m_magic,dateKey);
     }

   string QualifiedKey(ulong positionId)
     {
      return StringFormat("MT%I64d.%I64u.%I64u",AccountInfoInteger(ACCOUNT_LOGIN),m_magic,positionId);
     }

   bool EnsureLock()
     {
      if(GlobalVariableCheck(m_lockKey))return true;
      // GlobalVariableTemp creates the missing lock at zero without a check-then-set reset race.
      ResetLastError();
      bool created=GlobalVariableTemp(m_lockKey);
      if(!created && !GlobalVariableCheck(m_lockKey))
        {
         PrintFormat("Midas Touch daily target: cannot create shared lock (error %d).",GetLastError());
         return false;
        }
      return GlobalVariableCheck(m_lockKey);
     }

   bool AcquireLock(double &tokenOut)
     {
      tokenOut=0.0;
      if(!EnsureLock())return false;

      // A lease based on local wall-clock time allows recovery if a terminal/EA stops while holding the lock.
      for(int attempt=0;attempt<100;attempt++)
        {
         double observed=GlobalVariableGet(m_lockKey);
         double now=(double)TimeLocal();
         if(observed==0.0 && GlobalVariableSetOnCondition(m_lockKey,now,0.0))
           {
            tokenOut=now;
            return true;
           }
         if(observed>0.0 && now-observed>15.0 &&
            GlobalVariableSetOnCondition(m_lockKey,now,observed))
           {
            tokenOut=now;
            Print("Midas Touch daily target: reclaimed a stale shared counter lock.");
            return true;
           }
         Sleep(10);
        }
      Print("Midas Touch daily target: shared counter lock unavailable; qualified close was not counted.");
      return false;
     }

   void ReleaseLock(double token)
     {
      if(token<=0.0)return;
      if(!GlobalVariableSetOnCondition(m_lockKey,0.0,token))
         Print("Midas Touch daily target: shared counter lock release failed; stale-lock recovery will handle it.");
      GlobalVariablesFlush();
     }

   bool EnsureCounter(int dateKey)
     {
      string key=CounterKey(dateKey);
      if(GlobalVariableCheck(key))return true;
      ResetLastError();
      datetime created=GlobalVariableSet(key,0.0);
      if(created==0 && !GlobalVariableCheck(key))
        {
         PrintFormat("Midas Touch daily target: cannot create daily counter (error %d).",GetLastError());
         return false;
        }
      return GlobalVariableCheck(key);
     }

   int ReadCounter(int dateKey)
     {
      if(dateKey<=0)return 0;
      string key=CounterKey(dateKey);
      if(!GlobalVariableCheck(key))return 0;
      return MathMax(0,(int)GlobalVariableGet(key));
     }

   void InitializeCurrentDayState()
     {
      double token=0.0;
      if(!AcquireLock(token))return;

      // Migrate same-day state from the previous counter format, if present.
      string currentKey=CounterKey(m_dateKey);
      if(!GlobalVariableCheck(currentKey))
        {
         int initialCount=0;
         if(GlobalVariableCheck(m_storageKey+".D") &&
            (int)GlobalVariableGet(m_storageKey+".D")==m_dateKey &&
            GlobalVariableCheck(m_storageKey+".C"))
            initialCount=MathMax(0,(int)GlobalVariableGet(m_storageKey+".C"));

         ResetLastError();
         datetime created=GlobalVariableSet(currentKey,(double)initialCount);
         if(created==0 && !GlobalVariableCheck(currentKey))
            PrintFormat("Midas Touch daily target: initial counter migration failed (error %d).",GetLastError());
         else
            GlobalVariablesFlush();
        }
      ReleaseLock(token);
      m_count=ReadCounter(m_dateKey);
     }

   void Rollover()
     {
      datetime now=TimeCurrent();
      MqlDateTime t;
      if(now<=0 || !TimeToStruct(now,t))return;
      int nextKey=t.year*1000+t.day_of_year;

      if(nextKey==m_dateKey)
        {
         m_count=ReadCounter(m_dateKey);
         if(m_target>0 && m_weekday && m_count>=m_target)m_reported=true;
         return;
        }

      int previousCount=ReadCounter(m_dateKey);
      if(m_target>0 && m_weekday && m_dateKey>0 && previousCount<m_target)
         PrintFormat("Midas Touch daily qualified-trade target not met: prior weekday %d/%d. No trades were forced.",previousCount,m_target);

      m_dateKey=nextKey;
      m_weekday=(t.day_of_week>=1 && t.day_of_week<=5);
      m_count=ReadCounter(m_dateKey);
      m_reported=(m_target>0 && m_weekday && m_count>=m_target);
     }

public:
   CDailyTradeTarget():m_target(3),m_count(0),m_dateKey(0),m_weekday(false),
      m_reported(false),m_minQualifiedR(0.25),m_storageKey(""),m_lockKey(""),m_magic(0){}

   void Init(int target,double minQualifiedR,ulong magic)
     {
      m_target=MathMax(0,target);
      m_minQualifiedR=MathMax(0.0,minQualifiedR);
      m_magic=magic;
      m_storageKey=StringFormat("MT2DT.%I64d.%I64u",AccountInfoInteger(ACCOUNT_LOGIN),magic);
      m_lockKey=StringFormat("MTL.%I64d.%I64u",AccountInfoInteger(ACCOUNT_LOGIN),magic);
      m_count=0;
      m_dateKey=0;
      m_weekday=false;
      m_reported=false;

      datetime now=TimeCurrent();
      MqlDateTime t;
      if(now<=0 || !TimeToStruct(now,t))
        {
         Print("Midas Touch daily target: server time unavailable; target counter not initialized.");
         return;
        }
      m_dateKey=t.year*1000+t.day_of_year;
      m_weekday=(t.day_of_week>=1 && t.day_of_week<=5);
      InitializeCurrentDayState();
      if(m_target>0 && m_weekday && m_count>=m_target)
        {
         m_reported=true;
         PrintFormat("Midas Touch daily qualified-trade target restored: %d/%d.",m_count,m_target);
        }
     }

   // Call only after the whole tracked decision closes and aggregate realized R is known.
   void OnQualifiedClose(datetime at,double realizedR,ulong positionId)
     {
      Rollover();
      if(m_target<=0 || at<=0 || realizedR<=0.0 || realizedR+1e-9<m_minQualifiedR)return;
      if(!IsWeekday(at) || DateKey(at)<=0)return;
      if(positionId<=0)return;
      int eventDateKey=DateKey(at);

      double token=0.0;
      if(!AcquireLock(token))return;

      string countedKey=QualifiedKey(positionId);
      if(GlobalVariableCheck(countedKey))
        {
         ReleaseLock(token);
         m_count=ReadCounter(m_dateKey);
         return;
        }

      int dateKey=eventDateKey;
      if(!EnsureCounter(dateKey))
        {
         ReleaseLock(token);
         return;
        }

      // Under the shared lock, marker and counter writes are serialized across chart instances.
      ResetLastError();
      datetime markerWrite=GlobalVariableSet(countedKey,(double)dateKey);
      if(markerWrite==0)
        {
         PrintFormat("Midas Touch daily target: unable to record position %I64u idempotency marker (error %d); trade not counted.",positionId,GetLastError());
         ReleaseLock(token);
         return;
        }
      GlobalVariablesFlush();

      string dailyKey=CounterKey(dateKey);
      int currentCount=MathMax(0,(int)GlobalVariableGet(dailyKey));
      ResetLastError();
      datetime countWrite=GlobalVariableSet(dailyKey,(double)(currentCount+1));
      if(countWrite==0)
        {
         PrintFormat("Midas Touch daily target: failed to persist qualified count for position %I64u (error %d); count may be understated.",positionId,GetLastError());
         ReleaseLock(token);
         return;
        }
      GlobalVariablesFlush();
      int eventDayCount=currentCount+1;
      if(dateKey==m_dateKey)m_count=eventDayCount;
      ReleaseLock(token);

      if(dateKey==m_dateKey && !m_reported && m_count>=m_target)
        {
         m_reported=true;
         PrintFormat("Midas Touch daily qualified-trade target reached: %d/%d (minimum %.2fR per closed trade).",m_count,m_target,m_minQualifiedR);
        }
      else if(dateKey!=m_dateKey)
         PrintFormat("Midas Touch: recorded a delayed qualified close for broker date %d; current day counter is unchanged.",dateKey);
     }

   void OnTick(){Rollover();}
   int CountToday(){Rollover();return m_count;}
   int Target(){return m_target;}
   int Deficit(){Rollover();return MathMax(0,m_target-m_count);}
   bool Met(){Rollover();return !m_weekday || m_target<=0 || m_count>=m_target;}
  };

#endif
//+------------------------------------------------------------------+
