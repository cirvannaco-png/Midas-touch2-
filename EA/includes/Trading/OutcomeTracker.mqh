//+------------------------------------------------------------------+
//| Trading/OutcomeTracker.mqh                                      |
//+------------------------------------------------------------------+
#ifndef OUTCOMETRACKER_MQH
#define OUTCOMETRACKER_MQH

#include "../Core/Config.mqh"
#include "../Core/SignalLogger.mqh"
#include "../Analysis/TFContext.mqh"
#include "RiskEngine.mqh"
#include "CalibrationEngine.mqh"
#include "../Signals/SignalPublisher.mqh"

class COutcomeTracker
  {
private:
   PendingSetup      m_pending[];
   int               m_count;
   int               m_maxBars;
   CSignalLogger*    m_logger;
   string            m_symbol;
   ENUM_TIMEFRAMES   m_entryTF;
   ENUM_FILL_POLICY  m_fillPolicy;
   ENUM_TIMEFRAMES   m_replayTF;
   OutcomeStats      m_stats;
   CRiskEngine       m_risk;
   double            m_riskPercent;
   bool              m_allowMinLotOverride;
   double            m_breakEvenAtR;
   double            m_partialAtR;
   double            m_partialFraction;
   double            m_trailAtrMult;
   double            m_commissionPerLot;
   double            m_spreadPoints;
   double            m_slippagePoints;
   CCalibrationEngine m_calibration;
   bool              m_calibrationEnabled;
   double            m_decayHalfLifeBars;
   CSignalPublisher* m_publisher;
   string            m_weightVersion;

   void              RemoveAt(int idx);
   void              Resolve(int idx, string outcome, double exitPrice);
   double            PointSize() const;
   double            ValuePerUnitDistance() const;
   double            ApplyEntryCosts(double rawPrice, bool isBuy) const;
   double            ApplyExitCosts(double rawPrice, bool isBuy) const;
   string            SLHitLabel(const PendingSetup &p) const;
   void              CloseSlice(PendingSetup &p, double closeLots, double rawExitPrice, bool isBuy);
   void              ApplyPartial(PendingSetup &p, double triggerPrice, bool isBuy);
   bool              ResolveOrder(bool isBuy, CandleData &bar0, double adverseLevel, double favorableLevel, bool &ambiguous);
   bool              IntrabarReplayGeneric(bool isBuy, CandleData &bar0, double adverseLevel, double favorableLevel, bool &favorableFirst);
   string            ResolveCollision(bool isBuy, CandleData &bar0, double adverseLevel, double favorableLevel,
                                      double &outExitPrice, bool &ambiguous);
   void              ProcessFilledBar(int idx, CandleData &bar0);
   void              ApplyDecay(PendingSetup &p) const;
   void              PublishIfConfigured(const PendingSetup &p, string coarseOutcome, bool ambiguous);
   void              FinalizeExit(int idx, PendingSetup &p, string outcome, double rawExitPrice,
                                  bool sameBarCollision, bool ambiguous);

public:
                     COutcomeTracker();
   void              Init(CSignalLogger* logger, string symbol, ENUM_TIMEFRAMES entryTF, int maxBars,
                          ENUM_FILL_POLICY fillPolicy = FILL_CONSERVATIVE, ENUM_TIMEFRAMES replayTF = PERIOD_M1);
   void              ConfigureSimulation(double riskPercent, bool allowMinLotOverride,
                                         double breakEvenAtR, double partialAtR, double partialFraction,
                                         double trailAtrMult, double commissionPerLot,
                                         double spreadPoints, double slippagePoints);
   void              AddSetup(TradeSetup &setup, long decisionId = -1);
   void              Update(CTFContext* executionCtx);
   int               ActiveCount() const { return m_count; }
   OutcomeStats      GetStats() const { return m_stats; }
   bool              GetFillState(datetime creation_time, long decisionId, bool &filled, double &fillPrice,
                                  datetime &fillTime, int &barsToFill);
   void              ConfigureConfidenceDecay(double halfLifeBars = 12.0) { m_decayHalfLifeBars = halfLifeBars; }
   void              ConfigureCalibration(bool enabled, int minSample = 30) { m_calibrationEnabled = enabled; m_calibration.Init(m_symbol, minSample); }
   void              ConfigurePublishing(CSignalPublisher* publisher, string weightVersion)
     { m_publisher = publisher; m_weightVersion = weightVersion; }
   double            GetCalibratedProbability(double confidence, int &sampleSizeOut, bool &hasEnoughDataOut) const
     { return m_calibration.GetCalibratedProbability(confidence, sampleSizeOut, hasEnoughDataOut); }
   const CCalibrationEngine* CalibrationEngine() const { return GetPointer(m_calibration); }
  };

COutcomeTracker::COutcomeTracker() : m_count(0), m_maxBars(100), m_logger(NULL),
                                      m_fillPolicy(FILL_CONSERVATIVE), m_replayTF(PERIOD_M1),
                                      m_riskPercent(0.5), m_allowMinLotOverride(true),
                                      m_breakEvenAtR(1.0), m_partialAtR(2.0), m_partialFraction(0.5),
                                      m_trailAtrMult(1.5), m_commissionPerLot(7.0),
                                      m_spreadPoints(10.0), m_slippagePoints(2.0), m_calibrationEnabled(false),
                                      m_decayHalfLifeBars(12.0), m_publisher(NULL), m_weightVersion("")
  { ZeroMemory(m_stats); }

void COutcomeTracker::Init(CSignalLogger* logger, string symbol, ENUM_TIMEFRAMES entryTF, int maxBars,
                           ENUM_FILL_POLICY fillPolicy, ENUM_TIMEFRAMES replayTF)
  {
   m_logger = logger;
   m_symbol = symbol;
   m_entryTF = entryTF;
   m_maxBars = MathMax(5, maxBars);
   m_fillPolicy = fillPolicy;
   m_replayTF = replayTF;
   m_count = 0;
   ZeroMemory(m_stats);
   ArrayFree(m_pending);
  }

void COutcomeTracker::ConfigureSimulation(double riskPercent, bool allowMinLotOverride,
                                          double breakEvenAtR, double partialAtR, double partialFraction,
                                          double trailAtrMult, double commissionPerLot,
                                          double spreadPoints, double slippagePoints)
  {
   m_riskPercent = (riskPercent > 0) ? riskPercent : 0.5;
   m_allowMinLotOverride = allowMinLotOverride;
   m_breakEvenAtR = breakEvenAtR;
   m_partialAtR = partialAtR;
   m_partialFraction = MathMax(0.0, MathMin(1.0, partialFraction));
   m_trailAtrMult = trailAtrMult;
   m_commissionPerLot = MathMax(0.0, commissionPerLot);
   m_spreadPoints = MathMax(0.0, spreadPoints);
   m_slippagePoints = MathMax(0.0, slippagePoints);
  }

double COutcomeTracker::PointSize() const { return SymbolInfoDouble(m_symbol, SYMBOL_POINT); }

double COutcomeTracker::ValuePerUnitDistance() const
  {
   double tickSize = SymbolInfoDouble(m_symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(m_symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0 || tickValue <= 0) return 0.0;
   return tickValue / tickSize;
  }

double COutcomeTracker::ApplyEntryCosts(double rawPrice, bool isBuy) const
  {
   double costPoints = (m_spreadPoints / 2.0 + m_slippagePoints) * PointSize();
   return isBuy ? rawPrice + costPoints : rawPrice - costPoints;
  }

double COutcomeTracker::ApplyExitCosts(double rawPrice, bool isBuy) const
  {
   double costPoints = (m_spreadPoints / 2.0 + m_slippagePoints) * PointSize();
   return isBuy ? rawPrice - costPoints : rawPrice + costPoints;
  }

string COutcomeTracker::SLHitLabel(const PendingSetup &p) const
  {
   if(!p.beDone) return "SL_Hit";
   if(!p.partialDone) return "BreakEven_Hit";
   return "Trail_Hit";
  }

void COutcomeTracker::CloseSlice(PendingSetup &p, double closeLots, double rawExitPrice, bool isBuy)
  {
   if(closeLots <= 0 || p.lots <= 0) return;
   double exitPrice = ApplyExitCosts(rawExitPrice, isBuy);
   double valuePerUnit = ValuePerUnitDistance();
   double direction = isBuy ? 1.0 : -1.0;
   double grossPnL = direction * (exitPrice - p.entryFillPrice) * closeLots * valuePerUnit;
   double commission = m_commissionPerLot * closeLots;
   p.realizedPnL += (grossPnL - commission);
   p.totalCommission += commission;
   p.totalSpreadCost += (m_spreadPoints / 2.0) * PointSize() * closeLots * valuePerUnit;
   p.totalSlippageCost += m_slippagePoints * PointSize() * closeLots * valuePerUnit;
   p.remainingLots -= closeLots;
   if(p.remainingLots < 0) p.remainingLots = 0;
  }

void COutcomeTracker::ApplyPartial(PendingSetup &p, double triggerPrice, bool isBuy)
  {
   if(p.lots > 0)
     {
      double closeLots = p.lots * m_partialFraction;
      CloseSlice(p, closeLots, triggerPrice, isBuy);
     }
   p.partialDone = true;
  }

bool COutcomeTracker::IntrabarReplayGeneric(bool isBuy, CandleData &bar0, double adverseLevel, double favorableLevel, bool &favorableFirst)
  {
   int replaySecs = PeriodSeconds(m_replayTF);
   int entrySecs  = PeriodSeconds(m_entryTF);
   if(replaySecs <= 0 || entrySecs <= 0 || replaySecs >= entrySecs) return false;
   datetime barEnd = bar0.time + entrySecs;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(m_symbol, m_replayTF, bar0.time, barEnd - 1, rates);
   if(copied <= 0) return false;
   for(int i = copied - 1; i >= 0; i--)
     {
      bool adverseHere = isBuy ? (rates[i].low <= adverseLevel) : (rates[i].high >= adverseLevel);
      bool favorableHere = isBuy ? (rates[i].high >= favorableLevel) : (rates[i].low <= favorableLevel);
      if(adverseHere && !favorableHere) { favorableFirst = false; return true; }
      if(favorableHere && !adverseHere) { favorableFirst = true; return true; }
      if(adverseHere && favorableHere)  { favorableFirst = false; return true; }
     }
   return false;
  }

bool COutcomeTracker::ResolveOrder(bool isBuy, CandleData &bar0, double adverseLevel, double favorableLevel, bool &ambiguous)
  {
   ambiguous = false;
   switch(m_fillPolicy)
     {
      case FILL_OPTIMISTIC: return true;
      case FILL_NEAREST:
        {
         double distAdverse = MathAbs(bar0.open - adverseLevel);
         double distFavorable = MathAbs(bar0.open - favorableLevel);
         return (distFavorable < distAdverse);
        }
      case FILL_INTRABAR_REPLAY:
        {
         bool favorableFirst;
         if(IntrabarReplayGeneric(isBuy, bar0, adverseLevel, favorableLevel, favorableFirst)) return favorableFirst;
         ambiguous = true;
         return false;
        }
      case FILL_AMBIGUOUS: ambiguous = true; return false;
      case FILL_CONSERVATIVE:
      default: return false;
     }
  }

string COutcomeTracker::ResolveCollision(bool isBuy, CandleData &bar0, double adverseLevel, double favorableLevel,
                                         double &outExitPrice, bool &ambiguous)
  {
   bool favorableFirst = ResolveOrder(isBuy, bar0, adverseLevel, favorableLevel, ambiguous);
   if(ambiguous) { outExitPrice = bar0.close; return "Ambiguous_SLandTP"; }
   if(favorableFirst) { outExitPrice = favorableLevel; return "FinalTP_Hit"; }
   outExitPrice = adverseLevel;
   return "SL_Hit";
  }

void COutcomeTracker::FinalizeExit(int idx, PendingSetup &p, string outcome, double rawExitPrice,
                                   bool sameBarCollision, bool ambiguous)
  {
   bool isBuy = (p.setup.type == ORDER_TYPE_BUY);
   if(p.remainingLots > 0) CloseSlice(p, p.remainingLots, rawExitPrice, isBuy);
   p.sameBarCollision = sameBarCollision;
   if(p.lots > 0)
     {
      if(ambiguous) m_stats.ambiguous++;
      else
        {
         if(p.realizedPnL > 0.0000001) m_stats.wins++;
         else if(p.realizedPnL < -0.0000001) m_stats.losses++;
         else m_stats.scratches++;
         m_stats.resolvedCount++;
         m_stats.netPnL += p.realizedPnL;
         if(p.realizedPnL > 0) m_stats.grossProfit += p.realizedPnL;
         else m_stats.grossLoss += (-p.realizedPnL);
         m_stats.totalCommission += p.totalCommission;
         m_stats.totalSpreadCost += p.totalSpreadCost;
         m_stats.totalSlippageCost += p.totalSlippageCost;
         double oneRDollar = p.mgmtRiskDist * ValuePerUnitDistance() * p.lots;
         if(oneRDollar > 0) m_stats.sumRMultiple += p.realizedPnL / oneRDollar;
         if(m_calibrationEnabled) m_calibration.Record(p.setup.confidence, p.realizedPnL);
        }
     }
   m_pending[idx] = p;
   if(m_logger != NULL) m_logger.LogOutcome(m_pending[idx], m_symbol, m_entryTF, outcome, rawExitPrice, m_fillPolicy);
   string coarseOutcome;
   if(ambiguous) coarseOutcome = "ambiguous";
   else if(p.lots <= 0) coarseOutcome = "scratch";
   else if(p.realizedPnL > 0.0000001) coarseOutcome = "win";
   else if(p.realizedPnL < -0.0000001) coarseOutcome = "loss";
   else coarseOutcome = "scratch";
   PublishIfConfigured(m_pending[idx], coarseOutcome, ambiguous);
   RemoveAt(idx);
  }

void COutcomeTracker::PublishIfConfigured(const PendingSetup &p, string coarseOutcome, bool ambiguous)
  {
   if(m_publisher == NULL || p.decisionId < 0) return;
   bool isBuy = (p.setup.type == ORDER_TYPE_BUY);
   double realizedR = 0.0, mfeR = 0.0, maeR = 0.0;
   if(coarseOutcome != "no_fill" && coarseOutcome != "ambiguous" && p.mgmtRiskDist > 0)
     {
      double oneRDollar = p.mgmtRiskDist * ValuePerUnitDistance() * p.lots;
      if(oneRDollar > 0) realizedR = p.realizedPnL / oneRDollar;
      mfeR = isBuy ? (p.mfePrice - p.sizingEntryPrice) / p.mgmtRiskDist
                   : (p.sizingEntryPrice - p.mfePrice) / p.mgmtRiskDist;
      maeR = isBuy ? (p.sizingEntryPrice - p.maePrice) / p.mgmtRiskDist
                   : (p.maePrice - p.sizingEntryPrice) / p.mgmtRiskDist;
     }
   string signalId = m_publisher.SignalIdForDecision(p.decisionId);
   string direction = isBuy ? "BUY" : "SELL";
   SetupReasons r = p.setup.reasons;
   m_publisher.PublishOutcome(signalId, m_symbol, direction, coarseOutcome, realizedR, mfeR, maeR,
                              p.barsElapsed, p.barsToFill, p.filled,
                              EnumToString(r.vol_regime), EnumToString(r.session), EnumToString(r.sweep_grade),
                              r.htf_ob_confluence, p.confidenceAtSignal, p.confidenceDecayed, p.decayBars);
  }

void COutcomeTracker::AddSetup(TradeSetup &setup, long decisionId)
  {
   PendingSetup p;
   ZeroMemory(p);
   p.setup = setup;
   p.decisionId = decisionId;
   bool isBuy = (setup.type == ORDER_TYPE_BUY);
   p.entryRef = isBuy ? setup.entry_bottom : setup.entry_top;
   p.riskDist = MathAbs(p.entryRef - setup.stop_loss);
   p.mfePrice = p.entryRef;
   p.maePrice = p.entryRef;
   p.tp1Hit = false;
   p.tp2Hit = false;
   p.barsElapsed = 0;
   // Zero means "not yet observed on an eligible execution bar". Update()
   // deliberately refuses to process the creation bar, preventing
   // retroactive fill/SL/trailing decisions and same-bar look-ahead.
   p.lastBarTime = 0;
   p.filled = false;
   p.fillTime = 0;
   p.barsToFill = 0;
   p.sameBarCollision = false;
   p.confidenceAtSignal = setup.confidence;
   p.confidenceDecayed = setup.confidence;
   p.decayBars = 0;
   p.sizingEntryPrice = isBuy ? setup.entry_top : setup.entry_bottom;
   p.mgmtRiskDist = MathAbs(p.sizingEntryPrice - setup.stop_loss);
   bool exceededBudget = false;
   p.lots = (p.mgmtRiskDist > 0)
            ? m_risk.CalculateLotSize(m_symbol, m_riskPercent, p.sizingEntryPrice, setup.stop_loss,
                                      false, m_allowMinLotOverride, exceededBudget)
            : 0.0;
   p.currentSL = setup.stop_loss;
   p.beDone = false;
   p.partialDone = false;
   p.remainingLots = p.lots;
   p.entryFillPrice = 0.0;
   p.realizedPnL = 0.0;
   p.totalCommission = 0.0;
   p.totalSpreadCost = 0.0;
   p.totalSlippageCost = 0.0;
   int n = m_count++;
   ArrayResize(m_pending, m_count);
   m_pending[n] = p;
  }

void COutcomeTracker::RemoveAt(int idx)
  {
   for(int i = idx; i < m_count - 1; i++) m_pending[i] = m_pending[i + 1];
   m_count--;
   ArrayResize(m_pending, m_count);
  }

void COutcomeTracker::Resolve(int idx, string outcome, double exitPrice)
  {
   if(m_logger != NULL) m_logger.LogOutcome(m_pending[idx], m_symbol, m_entryTF, outcome, exitPrice, m_fillPolicy);
   PublishIfConfigured(m_pending[idx], "no_fill", false);
   RemoveAt(idx);
  }

void COutcomeTracker::ProcessFilledBar(int idx, CandleData &bar0)
  {
   PendingSetup p = m_pending[idx];
   bool isBuy = (p.setup.type == ORDER_TYPE_BUY);
   double finalTP = p.setup.final_tp;
   int guard = 0;
   while(guard++ < 6)
     {
      double adverseLevel = p.currentSL;
      bool adverseTouched = isBuy ? (bar0.low <= adverseLevel) : (bar0.high >= adverseLevel);
      bool tpTouched = isBuy ? (bar0.high >= finalTP) : (bar0.low <= finalTP);
      if(adverseTouched && tpTouched)
        {
         double exitPrice; bool ambiguous;
         string outcome = ResolveCollision(isBuy, bar0, adverseLevel, finalTP, exitPrice, ambiguous);
         if(outcome == "SL_Hit") outcome = SLHitLabel(p);
         FinalizeExit(idx, p, outcome, exitPrice, true, ambiguous);
         return;
        }
      if(tpTouched) { FinalizeExit(idx, p, "FinalTP_Hit", finalTP, false, false); return; }

      if(!p.beDone)
        {
         double beTrigger = isBuy ? p.sizingEntryPrice + m_breakEvenAtR * p.mgmtRiskDist
                                  : p.sizingEntryPrice - m_breakEvenAtR * p.mgmtRiskDist;
         bool beTouched = isBuy ? (bar0.high >= beTrigger) : (bar0.low <= beTrigger);
         if(adverseTouched && beTouched)
           {
            bool ambiguous;
            bool favorableFirst = ResolveOrder(isBuy, bar0, adverseLevel, beTrigger, ambiguous);
            if(ambiguous) { FinalizeExit(idx, p, "Ambiguous_SLandBE", bar0.close, true, true); return; }
            if(!favorableFirst) { FinalizeExit(idx, p, SLHitLabel(p), adverseLevel, false, false); return; }
            p.currentSL = p.sizingEntryPrice; p.beDone = true; m_pending[idx] = p; continue;
           }
         if(adverseTouched) { FinalizeExit(idx, p, SLHitLabel(p), adverseLevel, false, false); return; }
         if(beTouched) { p.currentSL = p.sizingEntryPrice; p.beDone = true; m_pending[idx] = p; continue; }
         break;
        }

      if(!p.partialDone)
        {
         double partialTrigger = isBuy ? p.sizingEntryPrice + m_partialAtR * p.mgmtRiskDist
                                       : p.sizingEntryPrice - m_partialAtR * p.mgmtRiskDist;
         bool partialTouched = isBuy ? (bar0.high >= partialTrigger) : (bar0.low <= partialTrigger);
         if(adverseTouched && partialTouched)
           {
            bool ambiguous;
            bool favorableFirst = ResolveOrder(isBuy, bar0, adverseLevel, partialTrigger, ambiguous);
            if(ambiguous) { FinalizeExit(idx, p, "Ambiguous_SLandPartial", bar0.close, true, true); return; }
            if(!favorableFirst) { FinalizeExit(idx, p, SLHitLabel(p), adverseLevel, false, false); return; }
            ApplyPartial(p, partialTrigger, isBuy); m_pending[idx] = p; continue;
           }
         if(adverseTouched) { FinalizeExit(idx, p, SLHitLabel(p), adverseLevel, false, false); return; }
         if(partialTouched) { ApplyPartial(p, partialTrigger, isBuy); m_pending[idx] = p; continue; }
         break;
        }

      if(adverseTouched) { FinalizeExit(idx, p, SLHitLabel(p), adverseLevel, false, false); return; }
      // Trail calculated from this bar's favorable extreme becomes active
      // only on the next bar. p.currentSL is therefore the only stop tested
      // against this bar, eliminating same-bar trailing look-ahead.
      if(bar0.atr > 0)
        {
         double favPrice = isBuy ? bar0.high : bar0.low;
         double newTrail = isBuy ? favPrice - m_trailAtrMult * bar0.atr : favPrice + m_trailAtrMult * bar0.atr;
         bool improved = isBuy ? (newTrail > p.currentSL) : (newTrail < p.currentSL);
         if(improved) p.currentSL = newTrail;
        }
      break;
     }
   if(p.barsElapsed >= m_maxBars) { FinalizeExit(idx, p, "Timeout", bar0.close, false, false); return; }
   m_pending[idx] = p;
  }

void COutcomeTracker::ApplyDecay(PendingSetup &p) const
  {
   if(m_decayHalfLifeBars <= 0.0 || p.decayBars <= 0) { p.confidenceDecayed = p.confidenceAtSignal; return; }
   double factor = MathPow(0.5, (double)p.decayBars / m_decayHalfLifeBars);
   p.confidenceDecayed = p.confidenceAtSignal * factor;
  }

void COutcomeTracker::Update(CTFContext* executionCtx)
  {
   if(executionCtx == NULL || executionCtx.candles.Total() == 0) return;
   // Outcome tracking is an execution/backtest concern. Never feed the FVG,
   // BOS, liquidity, or other analysis timeframe here. The caller passes the
   // EA chart/execution context explicitly and Init() stores the same TF.
   CandleData bar0 = executionCtx.candles.GetCandle(0);
   if(PeriodSeconds(executionCtx.candles.Timeframe()) <= 0 || executionCtx.candles.Timeframe() != m_entryTF) return;

   for(int i = m_count - 1; i >= 0; i--)
     {
      PendingSetup p = m_pending[i];
      bool isBuy = (p.setup.type == ORDER_TYPE_BUY);

      // Establish observation time only. The setup's creation bar is never
      // eligible for fill, invalidation, MFE/MAE, management, or timeout.
      if(p.lastBarTime == 0)
        {
         p.lastBarTime = bar0.time;
         m_pending[i] = p;
         continue;
        }

      if(bar0.time == p.lastBarTime) continue;
      p.lastBarTime = bar0.time;
      p.barsElapsed++;
      if(!p.filled)
        {
         p.decayBars++;
         ApplyDecay(p);
        }
      m_pending[i] = p;

      if(!p.filled)
        {
         bool touchedEntry = isBuy ? (bar0.low <= p.entryRef) : (bar0.high >= p.entryRef);
         if(touchedEntry)
           {
            p.filled = true;
            p.fillTime = bar0.time;
            p.barsToFill = p.barsElapsed;
            p.mfePrice = p.entryRef;
            p.maePrice = p.entryRef;
            p.currentSL = p.setup.stop_loss;
            p.remainingLots = p.lots;
            if(p.lots > 0)
              {
               p.entryFillPrice = ApplyEntryCosts(p.sizingEntryPrice, isBuy);
               double valuePerUnit = ValuePerUnitDistance();
               p.totalSpreadCost = (m_spreadPoints / 2.0) * PointSize() * p.lots * valuePerUnit;
               p.totalSlippageCost = m_slippagePoints * PointSize() * p.lots * valuePerUnit;
              }
            m_pending[i] = p;
           }
         else
           {
            bool invalidated = isBuy ? (bar0.low <= p.setup.stop_loss) : (bar0.high >= p.setup.stop_loss);
            if(invalidated) { Resolve(i, "Invalidated_NoFill", bar0.close); continue; }
            if(p.barsElapsed >= m_maxBars) { Resolve(i, "Timeout_NoFill", bar0.close); continue; }
            continue;
           }
        }

      if(isBuy)
        {
         if(bar0.high > p.mfePrice) p.mfePrice = bar0.high;
         if(bar0.low < p.maePrice) p.maePrice = bar0.low;
        }
      else
        {
         if(bar0.low < p.mfePrice) p.mfePrice = bar0.low;
         if(bar0.high > p.maePrice) p.maePrice = bar0.high;
        }
      m_pending[i] = p;

      if(isBuy)
        {
         if(!p.tp1Hit && bar0.high >= p.setup.tp1) m_pending[i].tp1Hit = true;
         if(!p.tp2Hit && bar0.high >= p.setup.tp2) m_pending[i].tp2Hit = true;
        }
      else
        {
         if(!p.tp1Hit && bar0.low <= p.setup.tp1) m_pending[i].tp1Hit = true;
         if(!p.tp2Hit && bar0.low <= p.setup.tp2) m_pending[i].tp2Hit = true;
        }
      ProcessFilledBar(i, bar0);
     }
  }

bool COutcomeTracker::GetFillState(datetime creation_time, long decisionId, bool &filled, double &fillPrice,
                                   datetime &fillTime, int &barsToFill)
  {
   for(int i = 0; i < m_count; i++)
     {
      if(m_pending[i].setup.creation_time != creation_time) continue;
      if(decisionId >= 0 && m_pending[i].decisionId != decisionId) continue;
      filled = m_pending[i].filled;
      fillPrice = m_pending[i].entryRef;
      fillTime = m_pending[i].fillTime;
      barsToFill = m_pending[i].barsToFill;
      return true;
     }
   return false;
  }

#endif
//+------------------------------------------------------------------+
