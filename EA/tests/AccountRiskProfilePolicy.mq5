#property strict
#include "../includes/Portfolio/AccountRiskProfilePolicy.mqh"

int failures=0;

void AssertTrue(bool value,string label)
  {
   if(value) PrintFormat("PASS: %s",label);
   else { PrintFormat("FAIL: %s",label); failures++; }
  }

void SetLimits(AccountRiskLimits &v,ENUM_ACCOUNT_RISK_PROFILE profile,string name,
               double risk,int openTrades,double daily,double drawdown,
               double derisk,double floor,double portfolio,int perSymbol,int perGroup)
  {
   v.profile=profile;
   v.profileName=name;
   v.riskPercentPerTrade=risk;
   v.maxOpenTrades=openTrades;
   v.maxDailyLossPercent=daily;
   v.maxDrawdownPercent=drawdown;
   v.deriskStartPercent=derisk;
   v.deriskFloor=floor;
   v.maxPortfolioRiskPercent=portfolio;
   v.maxPositionsPerSymbol=perSymbol;
   v.maxPositionsPerGroup=perGroup;
  }

int OnInit()
  {
   AccountRiskLimits legacy,smallAccount,largeAccount,propFirm,selected,unsafeRisk;
   SetLimits(legacy,ACCOUNT_RISK_PROFILE_LEGACY_INPUTS,"legacy_inputs",
             0.50,3,3.0,10.0,5.0,0.25,3.0,3,3);
   SetLimits(smallAccount,ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT,"small_account",
             0.50,1,1.5,5.0,2.0,0.25,0.5,1,1);
   SetLimits(largeAccount,ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT,"large_account",
             20.0,3,25.0,35.0,10.0,0.75,20.0,3,3);
   SetLimits(propFirm,ACCOUNT_RISK_PROFILE_PROP_FIRM,"prop_firm",
             0.25,3,1.5,5.0,2.0,0.25,1.0,2,2);
   string reason="";

   SetLimits(unsafeRisk,ACCOUNT_RISK_PROFILE_LEGACY_INPUTS,"unsafe",
             30.0,3,40.0,60.0,20.0,0.25,35.0,3,3);
   AssertTrue(!ValidateAccountRiskLimits(unsafeRisk,reason),
              "30 percent per-trade risk is rejected by the shared hard ceiling");
   AssertTrue(StringFind(reason,"hard safety ceiling")>=0,
              "excessive risk reports the hard-ceiling remediation");

   reason="";
   AssertTrue(ValidateAccountRiskLimits(legacy,reason),"legacy profile resolves with baseline limits");

   reason="";
   AssertTrue(ResolveAccountRiskLimits(ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT,
       legacy,smallAccount,largeAccount,propFirm,selected,reason),
       "small-account profile resolves");
   AssertTrue(selected.profileName=="small_account" &&
              selected.riskPercentPerTrade==0.50 && selected.maxOpenTrades==1 &&
              selected.maxDailyLossPercent==1.5 && selected.maxDrawdownPercent==5.0 &&
              selected.maxPortfolioRiskPercent==0.5,
              "small-account profile selects conservative limits only");

   reason="";
   SetLimits(unsafeRisk,ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT,"small_account",
             0.51,1,1.5,5.0,2.0,0.25,0.51,1,1);
   AssertTrue(!ValidateAccountRiskLimits(unsafeRisk,reason),
              "small-account risk above 0.5 percent is rejected");

   reason="";
   SetLimits(unsafeRisk,ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT,"small_account",
             0.50,2,1.5,5.0,2.0,0.25,0.5,2,2);
   AssertTrue(!ValidateAccountRiskLimits(unsafeRisk,reason),
              "small-account configuration allowing two positions is rejected");

   reason="";
   SetLimits(unsafeRisk,ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT,"small_account",
             0.50,1,1.6,5.0,2.0,0.25,0.5,1,1);
   AssertTrue(!ValidateAccountRiskLimits(unsafeRisk,reason),
              "small-account daily-loss cap above 1.5 percent is rejected");

   reason="";
   AssertTrue(ResolveAccountRiskLimits(ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT,
       legacy,smallAccount,largeAccount,propFirm,selected,reason),
       "large-account profile resolves");
   AssertTrue(selected.profileName=="large_account" &&
              selected.riskPercentPerTrade==20.0 && selected.maxOpenTrades==3 &&
              selected.maxDailyLossPercent==25.0 && selected.maxDrawdownPercent==35.0 &&
              selected.maxPortfolioRiskPercent==20.0,
              "large-account profile selects independent 15-20 percent risk settings");

   reason="";
   SetLimits(unsafeRisk,ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT,"large_account",
             14.99,3,25.0,35.0,10.0,0.75,20.0,3,3);
   AssertTrue(!ValidateAccountRiskLimits(unsafeRisk,reason),
              "large-account base risk below the 15 percent profile floor is rejected");

   reason="";
   SetLimits(unsafeRisk,ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT,"large_account",
             20.01,3,30.0,40.0,10.0,0.75,20.01,3,3);
   AssertTrue(!ValidateAccountRiskLimits(unsafeRisk,reason),
              "large-account risk above shared 20 percent ceiling is rejected");

   reason="";
   AssertTrue(ResolveConfiguredAccountRiskLimits(ACCOUNT_RISK_PROFILE_LEGACY_INPUTS,
       legacy,smallAccount,largeAccount,propFirm,false,false,false,selected,reason),
       "legacy profile remains available without non-legacy config flags");
   reason="";
   AssertTrue(!ResolveConfiguredAccountRiskLimits(ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT,
       legacy,smallAccount,largeAccount,propFirm,false,false,false,selected,reason),
       "unconfigured small-account profile fails closed");
   reason="";
   AssertTrue(!ResolveConfiguredAccountRiskLimits(ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT,
       legacy,smallAccount,largeAccount,propFirm,true,false,false,selected,reason),
       "unconfigured large-account profile fails closed");
   AssertTrue(StringFind(reason,"large-account risk inputs")>=0,
              "large-account configuration failure is explicit");
   reason="";
   AssertTrue(!ResolveConfiguredAccountRiskLimits(ACCOUNT_RISK_PROFILE_PROP_FIRM,
       legacy,smallAccount,largeAccount,propFirm,true,true,false,selected,reason),
       "unconfigured prop-firm profile fails closed");
   reason="";
   AssertTrue(ResolveConfiguredAccountRiskLimits(ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT,
       legacy,smallAccount,largeAccount,propFirm,true,true,false,selected,reason),
       "configured small-account profile resolves");
   reason="";
   AssertTrue(ResolveConfiguredAccountRiskLimits(ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT,
       legacy,smallAccount,largeAccount,propFirm,true,true,false,selected,reason),
       "configured large-account profile resolves");
   reason="";
   AssertTrue(ResolveConfiguredAccountRiskLimits(ACCOUNT_RISK_PROFILE_PROP_FIRM,
       legacy,smallAccount,largeAccount,propFirm,true,true,true,selected,reason),
       "configured prop-firm profile resolves");

   reason="";
   smallAccount.deriskStartPercent=smallAccount.maxDrawdownPercent;
   AssertTrue(!ResolveAccountRiskLimits(ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT,
       legacy,smallAccount,largeAccount,propFirm,selected,reason),
       "profile fails closed when de-risking starts at hard drawdown");

   PrintFormat("AccountRiskProfilePolicy tests: %d failure(s)",failures);
   return failures==0 ? INIT_SUCCEEDED : INIT_FAILED;
  }
