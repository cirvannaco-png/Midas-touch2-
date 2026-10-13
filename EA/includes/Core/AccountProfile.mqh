//+------------------------------------------------------------------+
//| Core/AccountProfile.mqh                                          |
//| Explicit, fail-closed account risk profile contract.              |
//+------------------------------------------------------------------+
#ifndef MIDAS_ACCOUNT_PROFILE_MQH
#define MIDAS_ACCOUNT_PROFILE_MQH

enum ENUM_MIDAS_ACCOUNT_PROFILE
  {
   MIDAS_PROFILE_PROP_FIRM=0,
   MIDAS_PROFILE_MICRO_RESEARCH=1
  };

struct MidasAccountProfileConfig
  {
   string profileName;
   double riskPercentPerTrade;
   int    maxOpenTrades;
   double maxPortfolioRiskPercent;
   int    maxPositionsPerSymbol;
   int    maxPositionsPerGroup;
   double maxDailyLossPercent;
   double maxDrawdownPercent;
   double deriskStartPercent;
   double deriskFloor;
   bool   allowMinLotOverride;
  };

bool ValidateMidasAccountProfile(const MidasAccountProfileConfig &cfg,string &reasonOut)
  {
   reasonOut="";
   if(cfg.profileName=="")
     { reasonOut="profile name is empty"; return false; }
   if(!MathIsValidNumber(cfg.riskPercentPerTrade) ||
      cfg.riskPercentPerTrade<=0.0 || cfg.riskPercentPerTrade>100.0)
     { reasonOut="risk percent must be finite and in (0,100]"; return false; }
   if(cfg.maxOpenTrades<1 || cfg.maxOpenTrades>100)
     { reasonOut="max open trades must be in [1,100]"; return false; }
   if(!MathIsValidNumber(cfg.maxPortfolioRiskPercent) ||
      cfg.maxPortfolioRiskPercent<=0.0 || cfg.maxPortfolioRiskPercent>100.0)
     { reasonOut="portfolio risk cap must be finite and in (0,100]"; return false; }
   if(cfg.maxPositionsPerSymbol<1 || cfg.maxPositionsPerSymbol>100 ||
      cfg.maxPositionsPerGroup<1 || cfg.maxPositionsPerGroup>100)
     { reasonOut="symbol/group position limits must be in [1,100]"; return false; }
   if(!MathIsValidNumber(cfg.maxDailyLossPercent) ||
      cfg.maxDailyLossPercent<=0.0 || cfg.maxDailyLossPercent>100.0)
     { reasonOut="daily loss cap must be finite and in (0,100]"; return false; }
   if(!MathIsValidNumber(cfg.maxDrawdownPercent) ||
      cfg.maxDrawdownPercent<=0.0 || cfg.maxDrawdownPercent>100.0)
     { reasonOut="hard drawdown cap must be finite and in (0,100]"; return false; }
   if(!MathIsValidNumber(cfg.deriskStartPercent) ||
      cfg.deriskStartPercent<0.0 || cfg.deriskStartPercent>=cfg.maxDrawdownPercent)
     { reasonOut="de-risk start must be finite and below hard drawdown cap"; return false; }
   if(!MathIsValidNumber(cfg.deriskFloor) ||
      cfg.deriskFloor<0.05 || cfg.deriskFloor>1.0)
     { reasonOut="de-risk floor must be finite and in [0.05,1.0]"; return false; }
   // Risk-budget integrity takes priority over legacy minimum-lot behavior.
   if(cfg.allowMinLotOverride)
     { reasonOut="minimum-lot override is prohibited by account-profile risk policy"; return false; }
   return true;
  }

#endif
//+------------------------------------------------------------------+
