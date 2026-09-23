//+------------------------------------------------------------------+
//| Execution/MultiTradeEngine.mqh                                  |
//| High-probability multi-leg execution allocation.                 |
//+------------------------------------------------------------------+
#ifndef MULTITRADEENGINE_MQH
#define MULTITRADEENGINE_MQH

#include "../Core/Config.mqh"

#define MULTITRADE_MAX_LEGS 3

struct MultiTradePlan
  {
   bool eligible;
   int legCount;
   double riskFraction[MULTITRADE_MAX_LEGS];
   double target[MULTITRADE_MAX_LEGS];
   string label[MULTITRADE_MAX_LEGS];
   string reason;
  };

class CMultiTradeEngine
  {
private:
   bool   m_enabled;
   double m_dualProbability;
   double m_tripleProbability;
   double m_minRawConfidence;
   int    m_minCalibrationSample;
   double m_dualRiskFraction0;
   double m_dualRiskFraction1;
   double m_tripleRiskFraction0;
   double m_tripleRiskFraction1;
   double m_tripleRiskFraction2;
   bool   m_requireHedging;

public:
   void Init(bool enabled,double dualProbability,double tripleProbability,
             double minRawConfidence,int minCalibrationSample,
             double dualRiskFraction0,double dualRiskFraction1,
             double tripleRiskFraction0,double tripleRiskFraction1,double tripleRiskFraction2,
             bool requireHedging=true);
   bool Build(const TradeSetup &setup,int availableSlots,MultiTradePlan &out);
   bool IsHedgingAccount() const;
  };

void CMultiTradeEngine::Init(bool enabled,double dualProbability,double tripleProbability,
                             double minRawConfidence,int minCalibrationSample,
                             double dualRiskFraction0,double dualRiskFraction1,
                             double tripleRiskFraction0,double tripleRiskFraction1,double tripleRiskFraction2,
                             bool requireHedging)
  {
   m_enabled=enabled;
   m_dualProbability=MathMax(0.0,MathMin(100.0,dualProbability));
   m_tripleProbability=MathMax(m_dualProbability,MathMin(100.0,tripleProbability));
   m_minRawConfidence=MathMax(0.0,MathMin(100.0,minRawConfidence));
   m_minCalibrationSample=MathMax(1,minCalibrationSample);
   m_dualRiskFraction0=MathMax(0.0,dualRiskFraction0);
   m_dualRiskFraction1=MathMax(0.0,dualRiskFraction1);
   m_tripleRiskFraction0=MathMax(0.0,tripleRiskFraction0);
   m_tripleRiskFraction1=MathMax(0.0,tripleRiskFraction1);
   m_tripleRiskFraction2=MathMax(0.0,tripleRiskFraction2);
   m_requireHedging=requireHedging;
  }

bool CMultiTradeEngine::IsHedgingAccount() const
  {
   return (AccountInfoInteger(ACCOUNT_MARGIN_MODE)==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);
  }

bool CMultiTradeEngine::Build(const TradeSetup &setup,int availableSlots,MultiTradePlan &out)
  {
   ZeroMemory(out);
   out.eligible=false;
   out.legCount=1;
   out.riskFraction[0]=1.0;
   out.target[0]=setup.final_tp;
   out.label[0]="PRIMARY";
   out.reason="single-trade path";

   if(!m_enabled) { out.reason="multi-trade disabled"; return true; }
   if(!setup.active) { out.reason="setup inactive"; return true; }
   if(availableSlots<2) { out.reason="fewer than two execution slots available"; return true; }
   if(!setup.calibration_has_enough_data || setup.calibration_sample<m_minCalibrationSample)
     { out.reason="calibration sample is insufficient for multi-trade scaling"; return true; }
   if(setup.confidence<m_minRawConfidence)
     { out.reason="raw confidence below multi-trade floor"; return true; }
   // Fail closed on malformed calibration values. NaN comparisons are
   // false, which could otherwise let a corrupted probability bypass the
   // ordinary "< threshold" gate.
   if(!MathIsValidNumber(setup.calibrated_probability) ||
      setup.calibrated_probability<0.0 || setup.calibrated_probability>100.0)
     { out.reason="calibrated probability is invalid"; return true; }
   if(!MathIsValidNumber(setup.confidence) ||
      setup.confidence<0.0 || setup.confidence>100.0)
     { out.reason="raw confidence is invalid"; return true; }
   if(setup.calibrated_probability<m_dualProbability)
     { out.reason="calibrated probability below dual-trade threshold"; return true; }
   if(m_requireHedging && !IsHedgingAccount())
     { out.reason="multi-trade requires MT5 hedging account semantics"; return true; }

   int legs=2;
   if(availableSlots>=3 && setup.calibrated_probability>=m_tripleProbability)
      legs=3;

   out.eligible=true;
   out.legCount=legs;
   if(legs==2)
     {
      out.riskFraction[0]=m_dualRiskFraction0;
      out.riskFraction[1]=m_dualRiskFraction1;
      out.target[0]=setup.tp1;
      out.target[1]=setup.final_tp;
      out.label[0]="TP1";
      out.label[1]="FINAL";
      out.reason=StringFormat("dual execution: calibrated probability %.1f%%",setup.calibrated_probability);
     }
   else
     {
      out.riskFraction[0]=m_tripleRiskFraction0;
      out.riskFraction[1]=m_tripleRiskFraction1;
      out.riskFraction[2]=m_tripleRiskFraction2;
      out.target[0]=setup.tp1;
      out.target[1]=setup.tp2;
      out.target[2]=setup.final_tp;
      out.label[0]="TP1";
      out.label[1]="TP2";
      out.label[2]="FINAL";
      out.reason=StringFormat("triple execution: calibrated probability %.1f%%",setup.calibrated_probability);
     }

   double fractionTotal=0.0;
   for(int i=0;i<out.legCount;i++)
      fractionTotal+=out.riskFraction[i];
   if(MathAbs(fractionTotal-1.0)>0.000001)
     {
      ZeroMemory(out);
      out.eligible=false;
      out.legCount=1;
      out.riskFraction[0]=1.0;
      out.target[0]=setup.final_tp;
      out.label[0]="PRIMARY";
      out.reason="invalid multi-trade risk allocation";
      return false;
     }
   return true;
  }

#endif
//+------------------------------------------------------------------+
