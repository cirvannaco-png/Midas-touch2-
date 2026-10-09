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
      // Include the full integer in the name; do not round ulong IDs through double.
      return m_storageKey+".X."+StringFormat("%I64u",positionId);
     }

   void Persist()
     {
      if(StringLen(m_storageKey)<=0 || m_dateKey<=0)return;
      // Store the count before publishing its date key during rollover.
      GlobalVariableSet(m_storageKey+".C",(double)m_count);
      GlobalVariableSet(m_storageKey+".D",(double)m_dateKey);
     }

   void SyncStoredState()
     {
      if(StringLen(m_storageKey)<=0 || !GlobalVariableCheck(m_storageKey+".D"))return;
      if((int)GlobalVariableGet(m_storageKey+".D")!=m_dateKey)return;
      if(GlobalVariableCheck(m_storageKey+".C"))
         m_count=MathMax(m_count,MathMax(0,(int)GlobalVariableGet(m_storageKey+".C")));
      if(m_target>0 && m_weekday && m_count>=m_target)m_reported=true;
     }

   void Rollover()
     {
      datetime now=TimeCurrent();
      MqlDateTime t;
      if(now<=0 || !TimeToStruct(now,t))return;
      int nextKey=t.year*1000+t.day_of_year;
      if(nextKey==m_dateKey){SyncStoredState();return;}

      if(m_target>0 && m_weekday && m_count<m_target && m_dateKey>0)
         PrintFormat("Midas Touch daily qualified-trade target not met: prior weekday %d/%d. No trades were forced.",m_count,m_target);

      m_dateKey=nextKey;
      m_weekday=(t.day_of_week>=1 && t.day_of_week<=5);
      m_count=0;
      m_reported=false;
      Persist();
     }

   bool TryClaimPosition(ulong positionId)
     {
      if(positionId==0)return true; // No stable ID: caller's tracking is the only deduplication.
      string marker=PositionMarker(positionId);
      if(!GlobalVariableCheck(marker))
         GlobalVariableSet(marker,0.0);
      // Atomic claim prevents repeated close notifications from counting the same position
      // when the marker already exists and is claimed.
      return GlobalVariableSetOnCondition(marker,1.0,0.0);
     }

   int IncrementPersistedCount()
     {
      string countKey=m_storageKey+".C";
      if(!GlobalVariableCheck(countKey))GlobalVariableSet(countKey,(double)m_count);
      // CAS avoids lost increments when multiple chart instances qualify trades together.
      for(int attempt=0;attempt<100;attempt++)
        {
         double observed=GlobalVariableGet(countKey);
         if(observed<0.0)observed=0.0;
         if(GlobalVariableSetOnCondition(countKey,observed+1.0,observed))
            return (int)(observed+1.0);
        }
      Print("Midas Touch: daily counter update deferred after concurrent update contention.");
      return -1;
     }

public:
   CDailyTradeTarget():m_target(3),m_count(0),m_dateKey(0),m_weekday(false),
      m_reported(false),m_minQualifiedR(0.25),m_storageKey(""){}

   void Init(int target,double minQualifiedR,ulong magic)
     {
      m_target=MathMax(0,target);
      m_minQualifiedR=MathMax(0.0,minQualifiedR);
      // Shared account+magic state aggregates chart-symbol instances in this terminal.
      m_storageKey=StringFormat("MT2DT.%I64d.%I64u",AccountInfoInteger(ACCOUNT_LOGIN),magic);
      m_count=0;
      m_dateKey=0;
      m_weekday=false;
      m_reported=false;

      datetime now=TimeCurrent();
      MqlDateTime t;
      if(now<=0 || !TimeToStruct(now,t))return;
      m_dateKey=t.year*1000+t.day_of_year;
      m_weekday=(t.day_of_week>=1 && t.day_of_week<=5);

      if(GlobalVariableCheck(m_storageKey+".D") &&
         (int)GlobalVariableGet(m_storageKey+".D")==m_dateKey &&
         GlobalVariableCheck(m_storageKey+".C"))
         m_count=MathMax(0,(int)GlobalVariableGet(m_storageKey+".C"));

      Persist();
      if(m_target>0 && m_weekday && m_count>=m_target)
        {
         m_reported=true;
         PrintFormat("Midas Touch daily qualified-trade target restored: %d/%d.",m_count,m_target);
        }
     }

   // Call only after the complete decision is closed and aggregate realized R is known.
   void OnQualifiedClose(datetime at,double realizedR,ulong positionId)
     {
      Rollover();
      if(m_target<=0 || at<=0 || realizedR<=0.0 || realizedR+1e-9<m_minQualifiedR)return;
      if(!IsWeekday(at) || DateKey(at)!=m_dateKey)return;
      if(!TryClaimPosition(positionId))return;

      int updated=IncrementPersistedCount();
      if(updated<0)return;
      m_count=updated;
      GlobalVariableSet(m_storageKey+".D",(double)m_dateKey);
      if(!m_reported && m_count>=m_target)
        {
         m_reported=true;
         PrintFormat("Midas Touch daily qualified-trade target reached: %d/%d (minimum %.2fR per closed trade).",m_count,m_target,m_minQualifiedR);
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
