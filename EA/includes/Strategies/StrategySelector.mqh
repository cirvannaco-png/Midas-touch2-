//+------------------------------------------------------------------+
//|                                  Strategies/StrategySelector.mqh  |
//+------------------------------------------------------------------+
#ifndef STRATEGYSELECTOR_MQH
#define STRATEGYSELECTOR_MQH

#include "../Core/Config.mqh"

// Regime-aware strategy authority. This layer deliberately does not
// manufacture a setup: it decides whether a diagnostic strategy read is
// eligible to own the next executable setup. A selected strategy that has
// no dedicated builder must fail closed at the strategy/setup boundary.
//
// The selector never adds heterogeneous scores together. It compares a
// strategy's score with the SMC baseline only after applying strategy-
// specific eligibility rules. This keeps "strength of evidence" separate
// from "permission to act".
class CStrategySelector
  {
private:
   double m_minSelectionScore;

   bool MomentumEligible(const SetupReasons &r) const
     {
      // A failed breakout has explicitly invalidated its broken level.
      // Exhaustion is a chase condition, not continuation evidence. Do not
      // let a large raw score override either structural warning.
      if(r.breakout_class == BREAKOUT_FAILED || r.breakout_class == BREAKOUT_EXHAUSTION)
         return false;
      return (r.breakout_class == BREAKOUT_EXPANSION || r.breakout_class == BREAKOUT_LIQUIDITY ||
              r.momentum_score >= m_minSelectionScore);
     }

   bool ReversionEligible(const SetupReasons &r) const
     {
      // Mean reversion already exposes a structural trend-conflict class.
      // It must never become the owner while fading a confirmed opposing BOS.
      return r.reversion_class == REVERSION_VALUE_FADE ||
             r.reversion_class == REVERSION_LEVEL_REJECTION;
     }

   bool KeyLevelEligible(const SetupReasons &r) const
     {
      // A bare break/acceptance is not a reaction entry. Require evidence
      // that price actually rejected, retested, failed the break, or showed
      // absorption at the level before this strategy can challenge SMC.
      return r.keylevel_reaction == REACTION_REJECTION ||
             r.keylevel_reaction == REACTION_RETEST ||
             r.keylevel_reaction == REACTION_FAILED_BREAK ||
             r.keylevel_reaction == REACTION_ABSORPTION;
     }

public:
                     CStrategySelector() : m_minSelectionScore(60.0) {}

   void Configure(double minSelectionScore = 60.0)
     {
      m_minSelectionScore = (minSelectionScore >= 0.0 && minSelectionScore <= 100.0) ? minSelectionScore : 60.0;
     }

   void Select(const SetupReasons &r, double smcConfidence,
               ENUM_SELECTED_STRATEGY &selected, double &selectedScore);
  };
//+------------------------------------------------------------------+
void CStrategySelector::Select(const SetupReasons &r, double smcConfidence,
                               ENUM_SELECTED_STRATEGY &selected, double &selectedScore)
  {
   selected = STRATEGY_NONE;
   selectedScore = 0.0;

   // The regime classifier is authoritative for which challenger family is
   // allowed to compete. An undefined regime is an explicit abstention.
   if(r.regime == REGIME_UNDEFINED)
      return;

   // SMC remains the baseline only when it has a real candidate. The caller
   // is responsible for ensuring that its executable SMC setup is complete.
   if(smcConfidence > 0.0)
     {
      selected = STRATEGY_SMC;
      selectedScore = smcConfidence;
     }

   double challengerScore = -1.0;
   ENUM_SELECTED_STRATEGY challenger = STRATEGY_NONE;

   if(r.regime == REGIME_TRENDING)
     {
      if(MomentumEligible(r))
        {
         challengerScore = MathMax(r.momentum_score, r.breakout_score);
         challenger = STRATEGY_MOMENTUM_BREAKOUT;
        }
     }
   else if(r.regime == REGIME_RANGING)
     {
      if(ReversionEligible(r))
        {
         challengerScore = r.reversion_score;
         challenger = STRATEGY_MEAN_REVERSION;
        }
     }
   else if(r.regime == REGIME_TRANSITION)
     {
      if(KeyLevelEligible(r))
        {
         challengerScore = r.keylevel_score;
         challenger = STRATEGY_KEY_LEVEL;
        }
     }

   // No SMC candidate means a challenger can still be diagnostically
   // selected, but it remains non-executable until its own setup builder
   // exists. If SMC exists, the challenger must clear both the minimum
   // evidence threshold and the SMC baseline.
   if(challenger != STRATEGY_NONE && challengerScore >= m_minSelectionScore &&
      (selected == STRATEGY_NONE || challengerScore > smcConfidence))
     {
      selected = challenger;
      selectedScore = challengerScore;
     }

   if(selected == STRATEGY_NONE)
      selectedScore = 0.0;
  }
#endif
//+------------------------------------------------------------------+
