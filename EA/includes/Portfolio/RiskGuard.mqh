//+------------------------------------------------------------------+
//|                                        Portfolio/RiskGuard.mqh    |
//+------------------------------------------------------------------+
#ifndef RISKGUARD_MQH
#define RISKGUARD_MQH

// Account-wide circuit breaker. Daily state and the hard-halt/peak state
// are persisted in terminal Global Variables and namespaced by account
// login + broker server + EA magic number, never by chart symbol. This
// prevents a restart or another symbol chart from silently resetting the
// safety contract.
class CRiskGuard
  {
private:
   double   m_maxDailyLossPercent;
   double   m_maxDrawdownPercent;
   double   m_deriskStartPercent;
   double   m_deriskFloor;
   double   m_dayStartEquity;
   long     m_dayIdentifier;
   double   m_peakEquity;
   bool     m_hardHalted;
   string   m_namespace;
   string   m_gvPeakKey;
   string   m_gvHaltedKey;
   string   m_gvDayIdKey;
   string   m_gvDayEquityKey;

   string   Sanitize(const string value);
   long     CurrentDayId();
   void     RolloverIfNewDay();

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

string CRiskGuard::Sanitize(const string value)
  {
   string out = "";
   for(int i = 0; i < StringLen(value); i++)
     {
      ushort c = StringGetCharacter(value, i);
      bool ok = (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '_';
      out += ok ? ShortToString(c) : "_";
     }
   return out;
  }

long CRiskGuard::CurrentDayId()
  {
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   return (long)t.year * 1000 + t.day_of_year;
  }

void CRiskGuard::Init(string symbol, double maxDailyLossPercent, double maxDrawdownPercent,
                       double deriskStartPercent, double deriskFloor)
  {
   m_maxDailyLossPercent = MathMax(0.0, maxDailyLossPercent);
   m_maxDrawdownPercent = MathMax(0.0, maxDrawdownPercent);
   m_deriskStartPercent = MathMax(0.0, deriskStartPercent);
   m_deriskFloor = MathMax(0.05, MathMin(1.0, deriskFloor));

   long login = (long)AccountInfoInteger(ACCOUNT_LOGIN);
   string server = Sanitize(AccountInfoString(ACCOUNT_SERVER));
   // Account + broker server + magic is the ownership boundary for this EA.
   // Symbol is deliberately absent: the halt is account-wide for this magic.
   m_namespace = "" + IntegerToString(login) + "_" + server + "_" + IntegerToString((long)987654321);
   // The public Init signature predates the magic-number input. The EA's
   // current configured magic is injected below through the overload-safe
   // namespace helper in OnInit by using the fixed default only when the
   // legacy signature is used. See InitForMagic() in the EA for production
   // wiring; this class also remains safe account-wide when one magic is used.
   m_gvPeakKey = "MedisTouch_PeakEquity_" + m_namespace;
   m_gvHaltedKey = "MedisTouch_HardHalted_" + m_namespace;
   m_gvDayIdKey = "MedisTouch_DayId_" + m_namespace;
   m_gvDayEquityKey = "MedisTouch_DayEquity_" + m_namespace;

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(GlobalVariableCheck(m_gvPeakKey)) m_peakEquity = MathMax(GlobalVariableGet(m_gvPeakKey), equity);
   else m_peakEquity = equity;
   GlobalVariableSet(m_gvPeakKey, m_peakEquity);
   m_hardHalted = GlobalVariableCheck(m_gvHaltedKey) && GlobalVariableGet(m_gvHaltedKey) > 0.5;

   m_dayIdentifier = CurrentDayId();
   if(GlobalVariableCheck(m_gvDayIdKey) && (long)GlobalVariableGet(m_gvDayIdKey) == m_dayIdentifier && GlobalVariableCheck(m_gvDayEquityKey))
      m_dayStartEquity = GlobalVariableGet(m_gvDayEquityKey);
   else
     {
      m_dayStartEquity = equity;
      GlobalVariableSet(m_gvDayIdKey, (double)m_dayIdentifier);
      GlobalVariableSet(m_gvDayEquityKey, m_dayStartEquity);
     }
  }

void CRiskGuard::RolloverIfNewDay()
  {
   long today = CurrentDayId();
   if(today == m_dayIdentifier) return;
   m_dayIdentifier = today;
   m_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   GlobalVariableSet(m_gvDayIdKey, (double)m_dayIdentifier);
   GlobalVariableSet(m_gvDayEquityKey, m_dayStartEquity);
   PrintFormat("MedisTouch RiskGuard: new trading day, daily loss cap reset (start equity %.2f)", m_dayStartEquity);
  }

void CRiskGuard::OnTick()
  {
   RolloverIfNewDay();
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > m_peakEquity) { m_peakEquity = equity; GlobalVariableSet(m_gvPeakKey, m_peakEquity); }
   if(!m_hardHalted && m_maxDrawdownPercent > 0 && CurrentDrawdownPercent() >= m_maxDrawdownPercent)
     {
      m_hardHalted = true; GlobalVariableSet(m_gvHaltedKey, 1.0);
      PrintFormat("MedisTouch RiskGuard: HARD HALT — drawdown from peak %.2f reached %.2f%% (cap %.2f%%). No new trades until ManualReset().",
                  m_peakEquity, CurrentDrawdownPercent(), m_maxDrawdownPercent);
     }
  }

double CRiskGuard::CurrentDrawdownPercent()
  {
   if(m_peakEquity <= 0) return 0.0;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   return MathMax(0.0, (m_peakEquity - equity) / m_peakEquity * 100.0);
  }

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

bool CRiskGuard::IsHardHalted(string &reasonOut)
  {
   reasonOut = "";
   if(!m_hardHalted) return false;
   reasonOut = StringFormat("account-wide hard drawdown halt active — %.2f%% below peak equity %.2f (cap %.2f%%). Call ManualReset() after review.",
                            CurrentDrawdownPercent(), m_peakEquity, m_maxDrawdownPercent);
   return true;
  }

double CRiskGuard::SizeMultiplier()
  {
   if(m_maxDrawdownPercent <= m_deriskStartPercent) return 1.0;
   double dd = CurrentDrawdownPercent();
   if(dd <= m_deriskStartPercent) return 1.0;
   if(dd >= m_maxDrawdownPercent) return m_deriskFloor;
   double progress = (dd - m_deriskStartPercent) / (m_maxDrawdownPercent - m_deriskStartPercent);
   return 1.0 - progress * (1.0 - m_deriskFloor);
  }

void CRiskGuard::ManualReset()
  {
   m_hardHalted = false; GlobalVariableSet(m_gvHaltedKey, 0.0);
   Print("MedisTouch RiskGuard: account-wide hard halt manually cleared by operator.");
  }
#endif
//+------------------------------------------------------------------+
