//+------------------------------------------------------------------+
//| Portfolio/AccountRiskProfilePolicy.mqh                            |
//| Explicit risk-profile selection with fail-closed validation.      |
//+------------------------------------------------------------------+
#ifndef ACCOUNTRISKPROFILEPOLICY_MQH
#define ACCOUNTRISKPROFILEPOLICY_MQH

// Shared hard ceiling; the small-account profile has stricter local ceilings.
#define MIDAS_MAX_RISK_PERCENT_PER_TRADE 20.0
#define MIDAS_SMALL_ACCOUNT_MAX_RISK_PERCENT_PER_TRADE 0.5
#define MIDAS_SMALL_ACCOUNT_MAX_DAILY_LOSS_PERCENT 1.5
#define MIDAS_SMALL_ACCOUNT_MAX_DRAWDOWN_PERCENT 5.0
#define MIDAS_SMALL_ACCOUNT_MAX_PORTFOLIO_RISK_PERCENT 0.5
#define MIDAS_SMALL_ACCOUNT_MAX_OPEN_TRADES 1
#define MIDAS_LARGE_ACCOUNT_MIN_RISK_PERCENT_PER_TRADE 15.0

enum ENUM_ACCOUNT_RISK_PROFILE
  {
   ACCOUNT_RISK_PROFILE_LEGACY_INPUTS = 0, // existing EA inputs; default preserves prior behavior
   ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT = 1,
   ACCOUNT_RISK_PROFILE_PROP_FIRM     = 2, // preserve legacy enum value for existing .set files
   ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT  = 3
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
   if(limits.riskPercentPerTrade>MIDAS_MAX_RISK_PERCENT_PER_TRADE)
      {
       reason=StringFormat("riskPercentPerTrade %.2f%% exceeds the hard safety ceiling of %.2f%%; risk above the configured ceiling is unsupported",
                           limits.riskPercentPerTrade,MIDAS_MAX_RISK_PERCENT_PER_TRADE);
       return false;
      }
   if(limits.profile==ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT)
     {
      if(limits.riskPercentPerTrade>MIDAS_SMALL_ACCOUNT_MAX_RISK_PERCENT_PER_TRADE)
        { reason="small-account per-trade risk exceeds the 0.5% safety ceiling"; return false; }
      if(limits.maxOpenTrades>MIDAS_SMALL_ACCOUNT_MAX_OPEN_TRADES)
        { reason="small-account max open trades exceeds the one-position safety ceiling"; return false; }
      if(limits.maxDailyLossPercent>MIDAS_SMALL_ACCOUNT_MAX_DAILY_LOSS_PERCENT)
        { reason="small-account daily-loss cap exceeds the 1.5% safety ceiling"; return false; }
      if(limits.maxDrawdownPercent>MIDAS_SMALL_ACCOUNT_MAX_DRAWDOWN_PERCENT)
        { reason="small-account hard drawdown exceeds the 5% safety ceiling"; return false; }
      if(limits.maxPortfolioRiskPercent>MIDAS_SMALL_ACCOUNT_MAX_PORTFOLIO_RISK_PERCENT)
        { reason="small-account portfolio open risk exceeds the 0.5% safety ceiling"; return false; }
     }
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
   if(limits.maxPortfolioRiskPercent>limits.maxDailyLossPercent)
      { reason="portfolio open-risk cap must not exceed the daily-loss cap"; return false; }
   if(limits.maxPositionsPerSymbol<1 || limits.maxPositionsPerGroup<1)
      { reason="per-symbol and per-group position limits must be at least one"; return false; }
   if(limits.maxPositionsPerSymbol>limits.maxOpenTrades ||
      limits.maxPositionsPerGroup>limits.maxOpenTrades)
      { reason="per-symbol and per-group limits must not exceed the account-wide open-trade cap"; return false; }
   return true;
  }

// Select exactly one complete profile. The caller constructs each from the EA inputs.
// Existing saved .set files retain the legacy enum number for prop-firm mode.
bool ResolveAccountRiskLimits(ENUM_ACCOUNT_RISK_PROFILE selected,
                              const AccountRiskLimits &legacy,
                              const AccountRiskLimits &smallAccount,
                              const AccountRiskLimits &largeAccount,
                              const AccountRiskLimits &propFirm,
                              AccountRiskLimits &out,
                              string &reason)
  {
   if(selected==ACCOUNT_RISK_PROFILE_LEGACY_INPUTS)
      out=legacy;
   else if(selected==ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT)
      out=smallAccount;
   else if(selected==ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT)
      out=largeAccount;
   else if(selected==ACCOUNT_RISK_PROFILE_PROP_FIRM)
      out=propFirm;
   else
     { reason="unknown account risk profile"; return false; }

   out.profile=selected;
   if(selected==ACCOUNT_RISK_PROFILE_LEGACY_INPUTS) out.profileName="legacy_inputs";
   else if(selected==ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT) out.profileName="small_account";
   else if(selected==ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT) out.profileName="large_account";
   else out.profileName="prop_firm";

   if(!ValidateAccountRiskLimits(out,reason))
      return false;
   return true;
  }

// Non-legacy profiles have separately editable inputs. Fail closed until each
// profile has been marked configured against its intended account rules.
bool ResolveConfiguredAccountRiskLimits(ENUM_ACCOUNT_RISK_PROFILE selected,
                                        const AccountRiskLimits &legacy,
                                        const AccountRiskLimits &smallAccount,
                                        const AccountRiskLimits &largeAccount,
                                        const AccountRiskLimits &propFirm,
                                        bool smallProfileConfigured,
                                        bool largeProfileConfigured,
                                        bool propProfileConfigured,
                                        AccountRiskLimits &out,
                                        string &reason)
  {
   reason="";
   if(selected==ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT && !smallProfileConfigured)
     {
      reason="small-account risk inputs must be configured before selecting this profile";
      return false;
     }
   if(selected==ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT && !largeProfileConfigured)
     {
      reason="large-account risk inputs must be configured before selecting this profile";
      return false;
     }
   if(selected==ACCOUNT_RISK_PROFILE_PROP_FIRM && !propProfileConfigured)
     {
      reason="exact prop-firm limits must be configured before selecting this profile";
      return false;
     }
   return ResolveAccountRiskLimits(selected,legacy,smallAccount,largeAccount,propFirm,out,reason);
  }

#endif
//+------------------------------------------------------------------+
