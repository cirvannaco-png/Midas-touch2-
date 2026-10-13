//+------------------------------------------------------------------+
//| Portfolio/AccountRiskProfilePolicy.mqh                            |
//| Explicit risk-profile selection with fail-closed validation.      |
//+------------------------------------------------------------------+
#ifndef ACCOUNTRISKPROFILEPOLICY_MQH
#define ACCOUNTRISKPROFILEPOLICY_MQH

enum ENUM_ACCOUNT_RISK_PROFILE
  {
   ACCOUNT_RISK_PROFILE_LEGACY_INPUTS = 0, // existing EA inputs; default preserves prior behavior
   ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT = 1,
   ACCOUNT_RISK_PROFILE_PROP_FIRM     = 2
  };

struct AccountRiskLimits
  {
   ENUM_ACCOUNT_RISK_PROFILE profile;
   string profileName;
   double riskPercentPerTrade;
   int    maxOpenTrades;
   double maxDailyLossPercent;
   double maxDrawdownPercent;
   double deriskStartPercent;
   double deriskFloor;
   double maxPortfolioRiskPercent;
   int    maxPositionsPerSymbol;
   int    maxPositionsPerGroup;
  };

bool ValidateAccountRiskLimits(const AccountRiskLimits &limits,string &reason)
  {
   reason="";
   if(!MathIsValidNumber(limits.riskPercentPerTrade) || limits.riskPercentPerTrade<=0.0)
      { reason="riskPercentPerTrade must be finite and positive"; return false; }
   if(limits.maxOpenTrades<1)
      { reason="maxOpenTrades must be at least one"; return false; }
   if(!MathIsValidNumber(limits.maxDailyLossPercent) || limits.maxDailyLossPercent<=0.0)
      { reason="maxDailyLossPercent must be finite and positive"; return false; }
   if(!MathIsValidNumber(limits.maxDrawdownPercent) || limits.maxDrawdownPercent<=limits.maxDailyLossPercent)
      { reason="maxDrawdownPercent must exceed maxDailyLossPercent"; return false; }
   if(limits.riskPercentPerTrade>=limits.maxDailyLossPercent)
      { reason="per-trade risk must be below the daily-loss cap"; return false; }
   if(!MathIsValidNumber(limits.deriskStartPercent) || limits.deriskStartPercent<0.0 ||
      limits.deriskStartPercent>=limits.maxDrawdownPercent)
      { reason="deriskStartPercent must be non-negative and below the hard drawdown cap"; return false; }
   if(!MathIsValidNumber(limits.deriskFloor) || limits.deriskFloor<=0.0 || limits.deriskFloor>1.0)
      { reason="deriskFloor must be in (0, 1]"; return false; }
   if(!MathIsValidNumber(limits.maxPortfolioRiskPercent) ||
      limits.maxPortfolioRiskPercent<limits.riskPercentPerTrade)
      { reason="portfolio open-risk cap must be at least one base trade risk"; return false; }
   if(limits.maxPositionsPerSymbol<1 || limits.maxPositionsPerGroup<1)
      { reason="per-symbol and per-group position limits must be at least one"; return false; }
   return true;
  }

// Select exactly one complete profile. The caller constructs all three from
// the EA inputs and validates the selected profile before any order routing.
// Global account-wide RiskGuard persistence remains account-scoped across restarts.
bool ResolveAccountRiskLimits(ENUM_ACCOUNT_RISK_PROFILE selected,
                              const AccountRiskLimits &legacy,
                              const AccountRiskLimits &smallAccount,
                              const AccountRiskLimits &propFirm,
                              AccountRiskLimits &out,
                              string &reason)
  {
   if(selected==ACCOUNT_RISK_PROFILE_LEGACY_INPUTS)
      out=legacy;
   else if(selected==ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT)
      out=smallAccount;
   else if(selected==ACCOUNT_RISK_PROFILE_PROP_FIRM)
      out=propFirm;
   else
     { reason="unknown account risk profile"; return false; }

   out.profile=selected;
   if(selected==ACCOUNT_RISK_PROFILE_LEGACY_INPUTS) out.profileName="legacy_inputs";
   else if(selected==ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT) out.profileName="small_account";
   else out.profileName="prop_firm";

   if(!ValidateAccountRiskLimits(out,reason))
      return false;
   return true;
  }

#endif
//+------------------------------------------------------------------+
