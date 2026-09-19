//+------------------------------------------------------------------+
//| Trading/DailyTradeTarget.mqh                                     |
//| Qualified-trade target telemetry; never bypasses strategy gates. |
//+------------------------------------------------------------------+
#ifndef DAILYTRADETARGET_MQH
#define DAILYTRADETARGET_MQH
class CDailyTradeTarget
  {
private:
   int m_target;
   int m_count;
   int m_year;
   int m_dayOfYear;
   bool m_reported;
   void Rollover()
     {
      MqlDateTime t;
      TimeToStruct(TimeCurrent(),t);
      if(t.year!=m_year || t.day_of_year!=m_dayOfYear)
        {
         if(m_target>0 && m_count<m_target && m_year>0)
            PrintFormat("Midas Touch daily qualified-trade target: prior day %d/%d; target was not met. No trades were forced.",m_count,m_target);
         m_year=t.year;
         m_dayOfYear=t.day_of_year;
         m_count=0;
         m_reported=false;
        }
     }
public:
   CDailyTradeTarget():m_target(3),m_count(0),m_year(0),m_dayOfYear(0),m_reported(false){}
   void Init(int target)
     {
      m_target=MathMax(0,target);
      MqlDateTime t;
      TimeToStruct(TimeCurrent(),t);
      m_year=t.year;
      m_dayOfYear=t.day_of_year;
      m_count=0;
      m_reported=false;
     }
   void OnExecution(datetime at)
     {
      Rollover();
      if(m_target<=0 || at<=0)return;
      m_count++;
      if(!m_reported && m_count>=m_target)
        {
         m_reported=true;
         PrintFormat("Midas Touch daily qualified-trade target reached: %d/%d.",m_count,m_target);
        }
     }
   void OnTick(){Rollover();}
   int CountToday(){Rollover();return m_count;}
   int Target(){return m_target;}
   int Deficit(){Rollover();return MathMax(0,m_target-m_count);}
   bool Met(){Rollover();return m_target<=0 || m_count>=m_target;}
  };
#endif
//+------------------------------------------------------------------+
