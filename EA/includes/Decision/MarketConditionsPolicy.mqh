//+------------------------------------------------------------------+
//|                              Decision/MarketConditionsPolicy.mqh |
//| Independent market/session controls; disabled unless explicitly   |
//| configured and validated for the target broker and instrument.    |
//+------------------------------------------------------------------+
#ifndef MARKETCONDITIONSPOLICY_MQH
#define MARKETCONDITIONSPOLICY_MQH

#include "../Core/Config.mqh"
#include "../Core/BrokerMarketAvailability.mqh"

class CMarketConditionsPolicy
  {
private:
   bool m_enabled;
   bool m_configurationValid;
   bool m_requireMarketOpen;
   bool m_requireLiquiditySession;
   bool m_allowTokyo;
   bool m_allowLondon;
   bool m_allowNewYork;
   bool m_allowOverlap;
   double m_maxSpreadPoints;
   double m_maxSpreadToATR;
   bool m_blockRollover;
   bool m_rolloverConfigured;
   int m_rolloverStartMinute;
   int m_rolloverEndMinute;
   bool m_blockLowVolatility;
   bool m_blockUndefinedVolatility;
   CBrokerMarketAvailability m_marketAvailability;

   bool InRolloverWindow(datetime serverTime)
     {
      if(!m_rolloverConfigured || serverTime<=0) return false;
      MqlDateTime t;
      if(!TimeToStruct(serverTime,t)) return false;
      int minute=t.hour*60+t.min;
      if(m_rolloverStartMinute<m_rolloverEndMinute)
         return minute>=m_rolloverStartMinute && minute<m_rolloverEndMinute;
      return minute>=m_rolloverStartMinute || minute<m_rolloverEndMinute;
     }

   bool LiquiditySessionAllowed(ENUM_TRADING_SESSION session)
     {
      switch(session)
        {
         case SESSION_TOKYO: return m_allowTokyo;
         case SESSION_LONDON: return m_allowLondon;
         case SESSION_NEWYORK: return m_allowNewYork;
         case SESSION_LONDON_NY_OVERLAP: return m_allowOverlap;
         default: return false;
        }
     }

public:
                     CMarketConditionsPolicy() :
                        m_enabled(false),m_configurationValid(false),
                        m_requireMarketOpen(true),m_requireLiquiditySession(false),
                        m_allowTokyo(false),m_allowLondon(true),m_allowNewYork(true),m_allowOverlap(true),
                        m_maxSpreadPoints(0.0),m_maxSpreadToATR(0.0),
                        m_blockRollover(false),m_rolloverConfigured(false),
                        m_rolloverStartMinute(0),m_rolloverEndMinute(0),
                        m_blockLowVolatility(false),m_blockUndefinedVolatility(true) {}

   bool Configure(bool enabled,bool requireMarketOpen,bool requireLiquiditySession,
                  bool allowTokyo,bool allowLondon,bool allowNewYork,bool allowOverlap,
                  double maxSpreadPoints,double maxSpreadToATR,
                  bool blockRollover,bool rolloverConfigured,
                  int rolloverStartHour,int rolloverStartMinute,
                  int rolloverEndHour,int rolloverEndMinute,
                  bool blockLowVolatility,bool blockUndefinedVolatility)
     {
      m_enabled=enabled;
      m_requireMarketOpen=requireMarketOpen;
      m_requireLiquiditySession=requireLiquiditySession;
      m_allowTokyo=allowTokyo;
      m_allowLondon=allowLondon;
      m_allowNewYork=allowNewYork;
      m_allowOverlap=allowOverlap;
      m_maxSpreadPoints=maxSpreadPoints;
      m_maxSpreadToATR=maxSpreadToATR;
      m_blockRollover=blockRollover;
      m_rolloverConfigured=false;
      m_blockLowVolatility=blockLowVolatility;
      m_blockUndefinedVolatility=blockUndefinedVolatility;
      m_configurationValid=true;

      if(maxSpreadPoints<0.0 || maxSpreadToATR<0.0)
         m_configurationValid=false;
      if(blockRollover)
        {
         if(!rolloverConfigured ||
            rolloverStartHour<0 || rolloverStartHour>23 ||
            rolloverEndHour<0 || rolloverEndHour>23 ||
            rolloverStartMinute<0 || rolloverStartMinute>59 ||
            rolloverEndMinute<0 || rolloverEndMinute>59)
            m_configurationValid=false;
         else
           {
            int start=rolloverStartHour*60+rolloverStartMinute;
            int finish=rolloverEndHour*60+rolloverEndMinute;
            if(start==finish) m_configurationValid=false;
            else
              {
               m_rolloverStartMinute=start;
               m_rolloverEndMinute=finish;
               m_rolloverConfigured=true;
              }
           }
        }

      bool anyCriterion=requireMarketOpen || requireLiquiditySession ||
                        maxSpreadPoints>0.0 || maxSpreadToATR>0.0 ||
                        blockRollover || blockLowVolatility || blockUndefinedVolatility;
      if(enabled && !anyCriterion) m_configurationValid=false;
      return (!enabled || m_configurationValid);
     }

   bool IsEnabled() const { return m_enabled; }
   bool IsConfigurationValid() const { return m_configurationValid; }

   // Assessment is called after the existing setup and risk geometry checks.
   // It never sizes a position or places/retries an order.
   bool Allows(const string symbol,datetime serverTime,
               ENUM_TRADING_SESSION liquiditySession,
               double spreadPoints,double pointSize,double atrValue,
               ENUM_VOL_REGIME volatilityRegime,string &reason)
     {
      reason="POLICY_DISABLED";
      if(!m_enabled) return true;
      if(!m_configurationValid)
        {
         reason="BLOCK_INVALID_OR_INCOMPLETE_POLICY_CONFIGURATION";
         return false;
        }

      if(m_requireMarketOpen)
        {
         string scheduleReason="";
         string status=m_marketAvailability.Probe(symbol,serverTime,scheduleReason);
         if(status!="OPEN")
           {
            reason="BLOCK_MARKET_AVAILABILITY_"+status+":"+scheduleReason;
            return false;
           }
        }

      if(m_requireLiquiditySession && !LiquiditySessionAllowed(liquiditySession))
        {
         reason="BLOCK_LIQUIDITY_SESSION_POLICY";
         return false;
        }

      if(m_maxSpreadPoints>0.0)
        {
         if(!MathIsValidNumber(spreadPoints) || spreadPoints<0.0)
           {
            reason="BLOCK_SPREAD_POINTS_UNKNOWN";
            return false;
           }
         if(spreadPoints>m_maxSpreadPoints)
           {
            reason="BLOCK_MAX_SPREAD_POINTS";
            return false;
           }
        }

      if(m_maxSpreadToATR>0.0)
        {
         if(!MathIsValidNumber(spreadPoints) || !MathIsValidNumber(pointSize) ||
            !MathIsValidNumber(atrValue) || spreadPoints<0.0 || pointSize<=0.0 || atrValue<=0.0)
           {
            reason="BLOCK_SPREAD_TO_ATR_UNVERIFIABLE";
            return false;
           }
         double ratio=(spreadPoints*pointSize)/atrValue;
         if(!MathIsValidNumber(ratio) || ratio>m_maxSpreadToATR)
           {
            reason="BLOCK_MAX_SPREAD_TO_ATR";
            return false;
           }
        }

      if(m_blockRollover)
        {
         if(!m_rolloverConfigured || serverTime<=0)
           {
            reason="BLOCK_ROLLOVER_POLICY_UNCONFIGURED";
            return false;
           }
         if(InRolloverWindow(serverTime))
           {
            reason="BLOCK_CONFIGURED_ROLLOVER_WINDOW";
            return false;
           }
        }

      if(m_blockUndefinedVolatility && volatilityRegime==VOL_REGIME_UNDEFINED)
        {
         reason="BLOCK_UNDEFINED_VOLATILITY";
         return false;
        }
      if(m_blockLowVolatility && volatilityRegime==VOL_REGIME_LOW)
        {
         reason="BLOCK_LOW_VOLATILITY";
         return false;
        }

      reason="ALL_CONFIGURED_MARKET_CONDITIONS_PASSED";
      return true;
     }
  };
#endif
//+------------------------------------------------------------------+
