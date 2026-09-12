//+------------------------------------------------------------------+
//| Portfolio/EnvironmentPolicy.mqh                                 |
//| Regime-adaptive protection for transition and shock conditions    |
//+------------------------------------------------------------------+
#ifndef ENVIRONMENTPOLICY_MQH
#define ENVIRONMENTPOLICY_MQH

#include "../Core/Config.mqh"

enum ENUM_ENVIRONMENT_STATE
  {
   ENV_NORMAL,
   ENV_TRANSITION,
   ENV_SHOCK,
   ENV_RECOVERY
  };

// The policy acts on setup diagnostics without changing raw setup
// confidence. This preserves the calibration population: raw confidence
// remains the model output; environment thresholds control live exposure.
class CEnvironmentPolicy
  {
private:
   double m_transitionExecute;
   double m_transitionSignal;
   double m_recoveryExecute;
   double m_shockMinConfidence;

   bool IsHighVolNewsShock(const TradeSetup &setup) const
     {
      return setup.reasons.vol_regime == VOL_REGIME_HIGH &&
             setup.reasons.news_risk == NEWS_BLOCKED;
     }

public:
   CEnvironmentPolicy()
      : m_transitionExecute(80.0), m_transitionSignal(72.0),
        m_recoveryExecute(78.0), m_shockMinConfidence(92.0) {}

   void Configure(double transitionExecute, double transitionSignal,
                  double recoveryExecute, double shockMinConfidence)
     {
      m_transitionExecute = MathMax(0.0, MathMin(100.0, transitionExecute));
      m_transitionSignal = MathMax(0.0, MathMin(100.0, transitionSignal));
      m_recoveryExecute = MathMax(m_transitionExecute,
                                  MathMin(100.0, recoveryExecute));
      m_shockMinConfidence = MathMax(m_recoveryExecute,
                                     MathMin(100.0, shockMinConfidence));
     }

   ENUM_ENVIRONMENT_STATE Classify(const TradeSetup &setup) const
     {
      if(IsHighVolNewsShock(setup)) return ENV_SHOCK;
      if(setup.reasons.regime == REGIME_TRANSITION ||
         setup.reasons.vol_regime == VOL_REGIME_HIGH ||
         setup.reasons.news_risk == NEWS_WARNING)
         return ENV_TRANSITION;
      return ENV_NORMAL;
     }

   double ExecuteThreshold(const TradeSetup &setup, double base) const
     {
      ENUM_ENVIRONMENT_STATE state = Classify(setup);
      if(state == ENV_SHOCK) return MathMax(base, m_shockMinConfidence);
      if(state == ENV_TRANSITION) return MathMax(base, m_transitionExecute);
      if(state == ENV_RECOVERY) return MathMax(base, m_recoveryExecute);
      return base;
     }

   double SignalThreshold(const TradeSetup &setup, double base) const
     {
      ENUM_ENVIRONMENT_STATE state = Classify(setup);
      if(state == ENV_SHOCK) return MathMax(base, m_shockMinConfidence);
      if(state == ENV_TRANSITION) return MathMax(base, m_transitionSignal);
      if(state == ENV_RECOVERY) return MathMax(base, m_recoveryExecute);
      return base;
     }

   // High volatility alone does not stop trading. A shock requires both
   // high ATR percentile and a blocked high-impact-news window. This keeps
   // genuinely strong expansion regimes tradeable while protecting the
   // known transition/news failure mode.
   bool BlockExecution(const TradeSetup &setup, string &reason) const
     {
      reason = "";
      if(Classify(setup) != ENV_SHOCK) return false;
      reason = "new exposure blocked: high-volatility transition coincides with a blocked high-impact news window";
      return true;
     }

   bool ReduceRisk(const TradeSetup &setup) const
     {
      ENUM_ENVIRONMENT_STATE state = Classify(setup);
      return state == ENV_TRANSITION || state == ENV_RECOVERY;
     }

   string StateName(const TradeSetup &setup) const
     {
      switch(Classify(setup))
        {
         case ENV_TRANSITION: return "TRANSITION";
         case ENV_SHOCK:      return "SHOCK";
         case ENV_RECOVERY:   return "RECOVERY";
         default:             return "NORMAL";
        }
     }
  };

#endif
//+------------------------------------------------------------------+
