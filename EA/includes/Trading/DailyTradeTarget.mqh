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
   double   m_lockValue;

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

   string PositionMarker(ulong positionId)
     {
      // Full ID is encoded in the name; it is never rounded through a double.
      return m_storageKey+".X."+StringFormat("%I64u",positionId);
     }

   string CountKey(int dateKey)
     {
      return m_storageKey+".C."+IntegerToString(dateKey);
     }

   string BaselineKey(int dateKey)
     {
      return m_storageKey+".B."+IntegerToString(dateKey);
     }

   bool AcquireLock()
     {
      if(StringLen(m_lockKey)<=0)return false;
      bool created=GlobalVariableTemp(m_lockKey);
      // GlobalVariableTemp returns false when another EA already created the lock.
      if(!created && !GlobalVariableCheck(m_lockKey))return false;
      for(int attempt=0;attempt<250;attempt++)
        {
         double token=(double)GetTickCount64()+1.0;
         if(GlobalVariableSetOnCondition(m_lockKey,token,0.0))
           {
            m_lockValue=token;
            return true;
           }
         double held=GlobalVariableGet(m_lockKey);
         double now=(double)GetTickCount64();
         // Recover a lease left behind by an interrupted EA event. CAS ensures
         // an old owner cannot release a lock already acquired by another owner.
         if(held>0.0 && (now-held>30000.0 || (held==1.0 && now>30000.0)))
           {
            GlobalVariableSetOnCondition(m_lockKey,0.0,held);
            continue;
           }
         Sleep(1);
        }
      Print("Midas Touch daily target: timed out acquiring shared counter lock.");
      return false;
     }

   void ReleaseLock()
     {
      if(StringLen(m_lockKey)>0 && m_lockValue>0.0)
         GlobalVariableSetOnCondition(m_lockKey,0.0,m_lockValue);
      m_lockValue=0.0;
     }

   // Migrate the previous single-day counter once, then keep a stable baseline.
   bool EnsureBaselineLocked(int dateKey)
     {
      string baselineKey=BaselineKey(dateKey);
      if(GlobalVariableCheck(baselineKey))return true;

      double baseline=0.0;
      string legacyDateKey=m_storageKey+".D";
      string legacyCountKey=m_storageKey+".C";
      if(GlobalVariableCheck(legacyDateKey) &&
         (int)GlobalVariableGet(legacyDateKey)==dateKey &&
         GlobalVariableCheck(legacyCountKey))
         baseline=MathMax(0.0,GlobalVariableGet(legacyCountKey));

      return GlobalVariableSet(baselineKey,baseline)>0;
     }

   void MigrateLegacyLastPositionLocked()
     {
      // The previous version persisted only the last position ID as a double.
      // Preserve that one deduplication record during upgrade when it is exact.
      string legacyKey=m_storageKey+".P";
      if(!GlobalVariableCheck(legacyKey))return;
      double raw=GlobalVariableGet(legacyKey);
      if(raw<=0.0 || raw>=9007199254740992.0)return; // Beyond exact IEEE-754 integer range.
      ulong positionId=(ulong)raw;
      string marker=PositionMarker(positionId);
      if(!GlobalVariableCheck(marker))GlobalVariableSet(marker,1.0);
     }

   int CountMarkersForDateLocked(int dateKey)
     {
      int count=0;
      string prefix=m_storageKey+".X.";
      int total=GlobalVariablesTotal();
      for(int i=0;i<total;i++)
        {
         string name=GlobalVariableName(i);
         if(StringFind(name,prefix)!=0)continue;
         double storedAt=GlobalVariableGet(name);
         // The previous implementation stored 1.0 as a claim flag. New entries
         // store their broker close timestamp, allowing crash recovery by date.
         if(storedAt<1000000000.0)continue;
         if(DateKey((datetime)storedAt)==dateKey)count++;
        }
      return count;
     }

   void PruneOldMarkersLocked(datetime now)
     {
      // Keep a 90-day deduplication window without growing terminal globals forever.
      double cutoff=(double)(now-90*86400);
      string prefix=m_storageKey+".X.";
      for(int i=GlobalVariablesTotal()-1;i>=0;i--)
        {
         string name=GlobalVariableName(i);
         if(StringFind(name,prefix)!=0)continue;
         double storedAt=GlobalVariableGet(name);
         if(storedAt>=1000000000.0 && storedAt<cutoff)
            GlobalVariableDel(name);
        }
     }

   bool ReconcileDate(int dateKey,bool pruneOldMarkers)
     {
      if(dateKey<=0 || !AcquireLock())return false;
      bool baselineReady=EnsureBaselineLocked(dateKey);
      if(baselineReady)MigrateLegacyLastPositionLocked();
      if(!baselineReady)
        {
         ReleaseLock();
         Print("Midas Touch daily target: could not initialize persistent baseline.");
         return false;
        }

      double baseline=GlobalVariableGet(BaselineKey(dateKey));
      int markerCount=CountMarkersForDateLocked(dateKey);
      int currentCount=(int)MathMax(0.0,baseline)+(int)MathMax(0,markerCount);
      bool saved=(GlobalVariableSet(CountKey(dateKey),(double)currentCount)>0);
      if(pruneOldMarkers)PruneOldMarkersLocked(TimeCurrent());
      ReleaseLock();

      if(!saved)
         Print("Midas Touch daily target: could not reconcile persisted daily count.");
      return saved;
     }

   void SyncStoredState()
     {
      string key=CountKey(m_dateKey);
      if(!GlobalVariableCheck(key))
        {
         ReconcileDate(m_dateKey,false);
        }
      if(GlobalVariableCheck(key))
         m_count=MathMax(0,(int)GlobalVariableGet(key));
      if(m_target>0 && m_weekday && m_count>=m_target)m_reported=true;
     }

   void Rollover()
     {
      datetime now=TimeCurrent();
      MqlDateTime t;
      if(now<=0 || !TimeToStruct(now,t))return;
      int nextKey=t.year*1000+t.day_of_year;
      if(nextKey==m_dateKey)
        {
         SyncStoredState();
         return;
        }

      if(m_target>0 && m_weekday && m_count<m_target && m_dateKey>0)
         PrintFormat("Midas Touch daily qualified-trade target not met: prior weekday %d/%d. No trades were forced.",m_count,m_target);

      m_dateKey=nextKey;
      m_weekday=(t.day_of_week>=1 && t.day_of_week<=5);
      m_count=0;
      m_reported=false;
      ReconcileDate(m_dateKey,true);
      SyncStoredState();
     }

public:
   CDailyTradeTarget():m_target(3),m_count(0),m_dateKey(0),m_weekday(false),
      m_reported(false),m_minQualifiedR(0.25),m_storageKey(""),m_lockKey(""),m_lockValue(0.0){}

   void Init(int target,double minQualifiedR,ulong magic)
     {
      m_target=MathMax(0,target);
      m_minQualifiedR=MathMax(0.0,minQualifiedR);
      // Keep the prior namespace for transparent migration of its current-day count.
      m_storageKey=StringFormat("MT2DT.%I64d.%I64u",AccountInfoInteger(ACCOUNT_LOGIN),magic);
      m_lockKey=m_storageKey+".L";
      m_count=0;
      m_dateKey=0;
      m_weekday=false;
      m_reported=false;

      datetime now=TimeCurrent();
      MqlDateTime t;
      if(now<=0 || !TimeToStruct(now,t))return;
      m_dateKey=t.year*1000+t.day_of_year;
      m_weekday=(t.day_of_week>=1 && t.day_of_week<=5);

      if(!ReconcileDate(m_dateKey,false))
        {
         // Best effort read preserves visibility if another terminal-global operation
         // temporarily prevents reconciliation; next tick retries if the key is absent.
         string countKey=CountKey(m_dateKey);
         if(GlobalVariableCheck(countKey))m_count=MathMax(0,(int)GlobalVariableGet(countKey));
         return;
        }
      SyncStoredState();
      if(m_target>0 && m_weekday && m_count>=m_target)
         PrintFormat("Midas Touch daily qualified-trade target restored: %d/%d.",m_count,m_target);
     }

   // A count is added only after a complete tracked decision closes profitably
   // and meets the configured realized-R threshold. Deal time defines the day.
   void OnQualifiedClose(datetime at,double realizedR,ulong positionId)
     {
      if(m_target<=0 || at<=0 || positionId==0 || realizedR<=0.0 ||
         realizedR+1e-9<m_minQualifiedR || !IsWeekday(at))return;

      int closeDateKey=DateKey(at);
      if(closeDateKey<=0 || !AcquireLock())return;

      string marker=PositionMarker(positionId);
      if(GlobalVariableCheck(marker))
        {
         ReleaseLock();
         return; // Already accounted for, including a repeated event after restart.
        }

      // The marker is the durable idempotency record. Reconciliation can rebuild
      // the counter if the terminal stops between this write and the count update.
      if(GlobalVariableSet(marker,(double)at)<=0)
        {
         ReleaseLock();
         Print("Midas Touch daily target: failed to persist qualified-position marker.");
         return;
        }

      if(!EnsureBaselineLocked(closeDateKey))
        {
         GlobalVariableDel(marker);
         ReleaseLock();
         Print("Midas Touch daily target: failed to initialize close-date baseline.");
         return;
        }

      double baseline=GlobalVariableGet(BaselineKey(closeDateKey));
      int markerCount=CountMarkersForDateLocked(closeDateKey);
      int reconciled=(int)MathMax(0.0,baseline)+(int)MathMax(0,markerCount);
      bool saved=(GlobalVariableSet(CountKey(closeDateKey),(double)reconciled)>0);
      ReleaseLock();

      if(!saved)
         Print("Midas Touch daily target: marker was saved but daily count needs reconciliation.");

      if(closeDateKey==m_dateKey)
        {
         m_count=reconciled;
         if(!m_reported && m_target>0 && m_weekday && m_count>=m_target)
           {
            m_reported=true;
            PrintFormat("Midas Touch daily qualified-trade target reached: %d/%d (minimum %.2fR per closed trade).",m_count,m_target,m_minQualifiedR);
           }
        }
     }

   void OnTick(){Rollover();}
   int CountToday(){Rollover();return m_count;}
   int Target(){return m_target;}
   int Deficit(){Rollover();return MathMax(0,m_target-m_count);}
   bool Met(){Rollover();return !m_weekday || m_target<=0 || m_count>=m_target;}
  };

#endif
//+------------------------------------------------------------------+
