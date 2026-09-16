//+------------------------------------------------------------------+
//|                                      includes/StrategySelector.mqh |
//|  Public facade for the regime-aware strategy authority            |
//+------------------------------------------------------------------+
// The canonical implementation lives in Strategies/StrategySelector.mqh.
// It consumes already-computed strategy diagnostics and, together with
// the regime classifier, determines which strategy is permitted to own
// an executable setup. It never sums heterogeneous scores.
//
// This facade exists only to preserve the historical include path used by
// Scoring.mqh and other callers. The authoritative executable boundary is
// now:
//   market regime -> eligible strategy -> strategy-owned TradeSetup
//   -> structural validation -> decision/risk -> execution.
//
// A selected strategy that cannot construct a complete setup must fail
// closed; it must never silently fall back to SMC.
#ifndef STRATEGYSELECTOR_FACADE_MQH
#define STRATEGYSELECTOR_FACADE_MQH

#include "Strategies/StrategySelector.mqh"

#endif
//+------------------------------------------------------------------+
