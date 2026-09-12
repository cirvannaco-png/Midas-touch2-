//+------------------------------------------------------------------+
//|                                        Portfolio/RiskGuard.mqh    |
//+------------------------------------------------------------------+
#ifndef RISKGUARD_MQH
#define RISKGUARD_MQH

// Account-level circuit breaker. The daily baseline and peak-equity halt
// state are persisted in terminal GlobalVariables so restarting MT5 cannot
// silently reset a risk limit.
class CRiskGuard
  {
private:
   double   m_maxDailyLossPercent;
   double   m_maxDrawdownPercent;
   double   m_deriskStartPercent;
   double   m_deriskFloor;

   double   m_dayStartEquity;
   int      m_dayStartDayOfYear;
   int      m_dayStartYear;

   double   m_peakEquity;
   bool     m_hardHalted;

   string   m_symbol;
   string   m_gvPeakKey;
   string   m_gvHaltedKey;
   string   m_gvDayStartEquityKey;
   string   m_gvDayKey;

   void     RolloverIfNewDay();
   void     PersistDayBaseline();

public:
   void     Init(string symbol, double maxDailyLossPercent, double maxDrawdownPercent,
                  double deriskStartPercent, double deriskFloor);
   void     OnTick();

   bool     IsDailyLossLimitHit(string &reasonOut);
   bool     IsHardHalted(string &reasonOut);
   double   SizeMultiplier();
   double   CurrentDrawdownPercent();

   void     ManualReset();
  };
//+------------------------------------------------------------------+
void CRiskGuard::PersistDayBaseline()
  {
   GlobalVariableSet(m_gvDayStartEquityKey, m_dayStartEquity);
   GlobalVariableSet(m_gvDayKey, (double)m_dayStartYear * 1000.0 + m_dayStartDayOfYear);
  }
//+------------------------------------------------------------------+
void CRiskGuard::Init(string symbol, double maxDailyLossPercent, double maxDrawdownPercent,
                       double deriskStartPercent, double deriskFloor)
  {
   m_symbol = symbol;
   m_maxDailyLossPercent = MathMax(0.0, maxDailyLossPercent);
   m_maxDrawdownPercent = MathMax(0.0, maxDrawdownPercent);
   m_deriskStartPercent = MathMax(0.0, deriskStartPercent);
   m_deriskFloor = MathMax(0.05, MathMin(1.0, deriskFloor));

   string prefix = "MedisTouch_RiskGuard_" + IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN)) + "_" + symbol;
   m_gvPeakKey = prefix + "_PeakEquity";
   m_gvHaltedKey = prefix + "_HardHalted";
   m_gvDayStartEquityKey = prefix + "_DayStartEquity";
   m_gvDayKey = prefix + "_DayKey";

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(GlobalVariableCheck(m_gvPeakKey))
      m_peakEquity = MathMax(GlobalVariableGet(m_gvPeakKey), equity);
   else
      m_peakEquity = equity;
   GlobalVariableSet(m_gvPeakKey, m_peakEquity);

   m_hardHalted = GlobalVariableCheck(m_gvHaltedKey) && (GlobalVariableGet(m_gvHaltedKey) > 0.5);

   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   m_dayStartYear = t.year;
   m_dayStartDayOfYear = t.day_of_year;

   double persistedDay = 0.0;
   if(GlobalVariableCheck(m_gvDayKey))
      persistedDay = GlobalVariableGet(m_gvDayKey);
   double currentDayKey = (double)t.year * 1000.0 + t.day_of_year;

   if(GlobalVariableCheck(m_gvDayStartEquityKey) && MathAbs(persistedDay - currentDayKey) < 0.1)
      m_dayStartEquity = GlobalVariableGet(m_gvDayStartEquityKey);
   else
     {
      m_dayStartEquity = equity;
      PersistDayBaseline();
     }
  }
//+------------------------------------------------------------------+
void CRiskGuard::RolloverIfNewDay()
  {
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   if(t.year != m_dayStartYear || t.day_of_year != m_dayStartDayOfYear)
     {
      m_dayStartYear = t.year;
      m_dayStartDayOfYear = t.day_of_year;
      m_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      PersistDayBaseline();
      PrintFormat("MedisTouch RiskGuard: new trading day, daily loss cap reset (start equity %.2f)", m_dayStartEquity);
     }
  }
//+------------------------------------------------------------------+
void CRiskGuard::OnTick()
  {
   RolloverIfNewDay();
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > m_peakEquity)
     {
      m_peakEquity = equity;
      GlobalVariableSet(m_gvPeakKey, m_peakEquity);
     }

   if(!m_hardHalted && m_maxDrawdownPercent > 0 && CurrentDrawdownPercent() >= m_maxDrawdownPercent)
     {
      m_hardHalted = true;
      GlobalVariableSet(m_gvHaltedKey, 1.0);
      PrintFormat("MedisTouch RiskGuard: HARD HALT — drawdown %.2f%% reached %.2f%% cap. No new trades until ManualReset().",
                  CurrentDrawdownPercent(), m_maxDrawdownPercent);
     }
  }
//+------------------------------------------------------------------+
double CRiskGuard::CurrentDrawdownPercent()
  {
   if(m_peakEquity <= 0) return 0.0;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   return MathMax(0.0, (m_peakEquity - equity) / m_peakEquity * 100.0);
  }
//+------------------------------------------------------------------+
bool CRiskGuard::IsDailyLossLimitHit(string &reasonOut)
  {
   reasonOut = "";
   if(m_maxDailyLossPercent <= 0 || m_dayStartEquity <= 0) return false;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double lossPercent = MathMax(0.0, (m_dayStartEquity - equity) / m_dayStartEquity * 100.0);
   if(lossPercent >= m_maxDailyLossPercent)
     {
      reasonOut = StringFormat("daily loss cap hit: down %.2f%% from today's persisted start equity %.2f (cap %.2f%%)",
                                lossPercent, m_dayStartEquity, m_maxDailyLossPercent);
      return true;
     }
   return false;
  }
//+------------------------------------------------------------------+
bool CRiskGuard::IsHardHalted(string &reasonOut)
  {
   reasonOut = "";
   if(!m_hardHalted) return false;
   reasonOut = StringFormat("hard drawdown halt active — %.2f%% below peak equity %.2f (cap %.2f%%). Call ManualReset() after review.",
                             CurrentDrawdownPercent(), m_peakEquity, m_maxDrawdownPercent);
   return true;
  }
//+------------------------------------------------------------------+
double CRiskGuard::SizeMultiplier()
  {
   if(m_maxDrawdownPercent <= m_deriskStartPercent || m_maxDrawdownPercent <= 0) return 1.0;
   double dd = CurrentDrawdownPercent();
   if(dd <= m_deriskStartPercent) return 1.0;
   if(dd >= m_maxDrawdownPercent) return m_deriskFloor;
   double span = m_maxDrawdownPercent - m_deriskStartPercent;
   double progress = (dd - m_deriskStartPercent) / span;
   return 1.0 - progress * (1.0 - m_deriskFloor);
  }
//+------------------------------------------------------------------+
void CRiskGuard::ManualReset()
  {
   m_hardHalted = false;
   GlobalVariableSet(m_gvHaltedKey, 0.0);
   Print("MedisTouch RiskGuard: hard halt manually cleared by operator.");
  }
//+------------------------------------------------------------------+
#endif
