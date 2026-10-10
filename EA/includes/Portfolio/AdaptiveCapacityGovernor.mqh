//+------------------------------------------------------------------+
//| Portfolio/AdaptiveCapacityGovernor.mqh                           |
//| Performance-conditioned execution capacity.                     |
//| Extra slots are earned, confirmed, and context-gated.           |
//+------------------------------------------------------------------+
#ifndef ADAPTIVECAPACITYGOVERNOR_MQH
#define ADAPTIVECAPACITYGOVERNOR_MQH

#include "../Core/Config.mqh"

class CAdaptiveCapacityGovernor
  {
private:
   bool   m_enabled;
   int    m_minStrongSample;
   int    m_minProvenSample;
   int    m_minEliteSample;
   double m_strongWinRate;
   double m_provenWinRate;
   double m_eliteWinRate;
   double m_strongAvgR;
   double m_provenAvgR;
   double m_eliteAvgR;
   double m_strongPF;
   double m_provenPF;
   double m_elitePF;
   double m_capacityBlockDrawdown;

   int    m_shortWindow;
   int    m_longWindow;
   int    m_promotionConfirmations;
   int    m_demotionConfirmations;
   int    m_strongPromotionCooldown;
   int    m_provenPromotionCooldown;
   int    m_elitePromotionCooldown;

   int    m_baselineMaxOpen;
   int    m_baselinePerSymbol;
   int    m_baselinePerGroup;
   int    m_strongMaxOpen;
   int    m_strongPerSymbol;
   int    m_strongPerGroup;
   int    m_provenMaxOpen;
   int    m_provenPerSymbol;
   int    m_provenPerGroup;
   int    m_eliteMaxOpen;
   int    m_elitePerSymbol;
   int    m_elitePerGroup;

   int    m_statisticalLevel;
   int    m_effectiveLevel;
   int    m_maxOpen;
   int    m_perSymbol;
   int    m_perGroup;

   int    m_lastEvidenceSample;
   int    m_tradesSinceChange;
   int    m_promotionCandidate;
   int    m_promotionStreak;
   int    m_demotionStreak;
   bool   m_regimeEligible;
   bool   m_executionHealthy;

   bool PromotionMeets(int level,const OutcomeStats &lifetime,const OutcomeStats &shortStats,const OutcomeStats &longStats) const
     {
      int sample=lifetime.wins+lifetime.losses;
      if(level<=0)return true;

      int required=(level==1?m_minStrongSample:(level==2?m_minProvenSample:m_minEliteSample));
      if(sample<required)return false;

      double wr=100.0*(double)lifetime.wins/(double)sample;
      double avgR=lifetime.AverageRMultiple();
      double pf=lifetime.ProfitFactor();

      double shortWr=shortStats.WinRateExcludingAmbiguous();
      double longWr=longStats.WinRateExcludingAmbiguous();
      double shortAvgR=shortStats.AverageRMultiple();
      double longAvgR=longStats.AverageRMultiple();
      double shortPF=shortStats.ProfitFactor();
      double longPF=longStats.ProfitFactor();

      double reqWr=(level==1?m_strongWinRate:(level==2?m_provenWinRate:m_eliteWinRate));
      double reqAvgR=(level==1?m_strongAvgR:(level==2?m_provenAvgR:m_eliteAvgR));
      double reqPF=(level==1?m_strongPF:(level==2?m_provenPF:m_elitePF));
      int longRequired=(level==1?m_minStrongSample:(level==2?m_minProvenSample:m_minEliteSample));

      // Promotion must survive both recent and longer rolling windows.
      if(shortStats.ExcludingAmbiguousTotal()<m_shortWindow)return false;
      if(longStats.ExcludingAmbiguousTotal()<longRequired)return false;
      if(wr<reqWr || avgR<reqAvgR || (pf>=0.0 && pf<reqPF))return false;
      if(shortWr<reqWr || shortAvgR<reqAvgR || (shortPF>=0.0 && shortPF<reqPF))return false;
      if(longWr<reqWr || longAvgR<reqAvgR || (longPF>=0.0 && longPF<reqPF))return false;
      return true;
     }

   bool RetentionMeets(int level,const OutcomeStats &shortStats,const OutcomeStats &longStats) const
     {
      if(level<=0)return true;
      int longRequired=(level==1?m_minStrongSample:(level==2?m_minProvenSample:m_minEliteSample));
      if(shortStats.ExcludingAmbiguousTotal()<m_shortWindow || longStats.ExcludingAmbiguousTotal()<longRequired)return false;

      double reqWr=(level==1?65.0:(level==2?68.0:72.0));
      double reqAvgR=(level==1?0.00:(level==2?0.03:0.05));
      double reqPF=(level==1?1.05:(level==2?1.10:1.25));

      double shortPF=shortStats.ProfitFactor();
      double longPF=longStats.ProfitFactor();
      if(shortStats.WinRateExcludingAmbiguous()<reqWr || longStats.WinRateExcludingAmbiguous()<reqWr)return false;
      if(shortStats.AverageRMultiple()<reqAvgR || longStats.AverageRMultiple()<reqAvgR)return false;
      if((shortPF>=0.0 && shortPF<reqPF) || (longPF>=0.0 && longPF<reqPF))return false;
      return true;
     }

   int PromotionTarget(const OutcomeStats &lifetime,const OutcomeStats &shortStats,const OutcomeStats &longStats) const
     {
      if(PromotionMeets(3,lifetime,shortStats,longStats))return 3;
      if(PromotionMeets(2,lifetime,shortStats,longStats))return 2;
      if(PromotionMeets(1,lifetime,shortStats,longStats))return 1;
      return 0;
     }

   int PromotionCooldownFor(int nextLevel) const
     {
      if(nextLevel>=3)return m_elitePromotionCooldown;
      if(nextLevel==2)return m_provenPromotionCooldown;
      return m_strongPromotionCooldown;
     }

   void ApplyLevel(int level)
     {
      m_statisticalLevel=MathMax(0,MathMin(3,level));
      m_tradesSinceChange=0;
      m_promotionCandidate=0;
      m_promotionStreak=0;
      m_demotionStreak=0;
     }

   void RecomputeEffectiveLevel(double drawdownPercent)
     {
      int level=m_statisticalLevel;
      if(!m_enabled || drawdownPercent>=m_capacityBlockDrawdown || !m_regimeEligible || !m_executionHealthy)
         level=0;
      m_effectiveLevel=level;

      if(level<=0){m_maxOpen=m_baselineMaxOpen;m_perSymbol=m_baselinePerSymbol;m_perGroup=m_baselinePerGroup;}
      else if(level==1){m_maxOpen=m_strongMaxOpen;m_perSymbol=m_strongPerSymbol;m_perGroup=m_strongPerGroup;}
      else if(level==2){m_maxOpen=m_provenMaxOpen;m_perSymbol=m_provenPerSymbol;m_perGroup=m_provenPerGroup;}
      else {m_maxOpen=m_eliteMaxOpen;m_perSymbol=m_elitePerSymbol;m_perGroup=m_elitePerGroup;}
     }

public:
   CAdaptiveCapacityGovernor():
      m_enabled(true),
      m_minStrongSample(20),m_minProvenSample(35),m_minEliteSample(50),
      m_strongWinRate(70.0),m_provenWinRate(75.0),m_eliteWinRate(80.0),
      m_strongAvgR(0.05),m_provenAvgR(0.10),m_eliteAvgR(0.15),
      m_strongPF(1.15),m_provenPF(1.25),m_elitePF(1.50),
      m_capacityBlockDrawdown(5.0),
      m_shortWindow(20),m_longWindow(50),
      m_promotionConfirmations(3),m_demotionConfirmations(2),
      m_strongPromotionCooldown(10),m_provenPromotionCooldown(15),m_elitePromotionCooldown(20),
      m_baselineMaxOpen(3),m_baselinePerSymbol(3),m_baselinePerGroup(3),
      m_strongMaxOpen(4),m_strongPerSymbol(4),m_strongPerGroup(4),
      m_provenMaxOpen(5),m_provenPerSymbol(5),m_provenPerGroup(5),
      m_eliteMaxOpen(6),m_elitePerSymbol(6),m_elitePerGroup(6),
      m_statisticalLevel(0),m_effectiveLevel(0),m_maxOpen(3),m_perSymbol(3),m_perGroup(3),
      m_lastEvidenceSample(0),m_tradesSinceChange(0),m_promotionCandidate(0),m_promotionStreak(0),m_demotionStreak(0),
      m_regimeEligible(true),m_executionHealthy(true) {}

   void Init(bool enabled,
             int baselineMaxOpen,int baselinePerSymbol,int baselinePerGroup,
             int strongMaxOpen,int strongPerSymbol,int strongPerGroup,
             int provenMaxOpen,int provenPerSymbol,int provenPerGroup,
             int eliteMaxOpen,int elitePerSymbol,int elitePerGroup,
             int minStrongSample,int minProvenSample,int minEliteSample,
             double strongWinRate,double provenWinRate,double eliteWinRate,
             double strongAvgR,double provenAvgR,double eliteAvgR,
             double strongPF,double provenPF,double elitePF,
             double capacityBlockDrawdown,
             int shortWindow=20,int longWindow=50,
             int promotionConfirmations=3,int demotionConfirmations=2,
             int strongPromotionCooldown=10,int provenPromotionCooldown=15,int elitePromotionCooldown=20)
     {
      m_enabled=enabled;
      m_baselineMaxOpen=MathMax(1,baselineMaxOpen);
      m_baselinePerSymbol=MathMax(1,baselinePerSymbol);
      m_baselinePerGroup=MathMax(1,baselinePerGroup);
      m_strongMaxOpen=MathMax(m_baselineMaxOpen,strongMaxOpen);
      m_strongPerSymbol=MathMax(m_baselinePerSymbol,strongPerSymbol);
      m_strongPerGroup=MathMax(m_baselinePerGroup,strongPerGroup);
      m_provenMaxOpen=MathMax(m_strongMaxOpen,provenMaxOpen);
      m_provenPerSymbol=MathMax(m_strongPerSymbol,provenPerSymbol);
      m_provenPerGroup=MathMax(m_strongPerGroup,provenPerGroup);
      m_eliteMaxOpen=MathMax(m_provenMaxOpen,eliteMaxOpen);
      m_elitePerSymbol=MathMax(m_provenPerSymbol,elitePerSymbol);
      m_elitePerGroup=MathMax(m_provenPerGroup,elitePerGroup);

      m_minStrongSample=MathMax(1,minStrongSample);
      m_minProvenSample=MathMax(m_minStrongSample,minProvenSample);
      m_minEliteSample=MathMax(m_minProvenSample,minEliteSample);

      m_strongWinRate=MathMax(0.0,MathMin(100.0,strongWinRate));
      m_provenWinRate=MathMax(m_strongWinRate,MathMin(100.0,provenWinRate));
      m_eliteWinRate=MathMax(m_provenWinRate,MathMin(100.0,eliteWinRate));

      m_strongAvgR=strongAvgR;
      m_provenAvgR=MathMax(m_strongAvgR,provenAvgR);
      m_eliteAvgR=MathMax(m_provenAvgR,eliteAvgR);

      m_strongPF=MathMax(0.0,strongPF);
      m_provenPF=MathMax(m_strongPF,provenPF);
      m_elitePF=MathMax(m_provenPF,elitePF);

      m_capacityBlockDrawdown=MathMax(0.0,capacityBlockDrawdown);
      m_shortWindow=MathMax(1,shortWindow);
      m_longWindow=MathMax(m_shortWindow,longWindow);
      m_promotionConfirmations=MathMax(1,promotionConfirmations);
      m_demotionConfirmations=MathMax(1,demotionConfirmations);
      m_strongPromotionCooldown=MathMax(0,strongPromotionCooldown);
      m_provenPromotionCooldown=MathMax(m_strongPromotionCooldown,provenPromotionCooldown);
      m_elitePromotionCooldown=MathMax(m_provenPromotionCooldown,elitePromotionCooldown);
      m_statisticalLevel=0;m_effectiveLevel=0;m_maxOpen=m_baselineMaxOpen;m_perSymbol=m_baselinePerSymbol;m_perGroup=m_baselinePerGroup;
      m_lastEvidenceSample=0;m_tradesSinceChange=0;m_promotionCandidate=0;m_promotionStreak=0;m_demotionStreak=0;
      m_regimeEligible=true;m_executionHealthy=true;
     }

   void Refresh(const OutcomeStats &lifetime,const OutcomeStats &shortStats,const OutcomeStats &longStats,double drawdownPercent,bool executionHealthy)
     {
      int evidenceSample=lifetime.wins+lifetime.losses;
      int delta=evidenceSample-m_lastEvidenceSample;
      if(delta<0)delta=evidenceSample; // safe recovery after any tracker reset
      if(delta>0)
        {
         m_tradesSinceChange+=delta;
         int events=MathMin(1,delta); // require distinct outcome-driven confirmations
         int target=PromotionTarget(lifetime,shortStats,longStats);

         if(target>m_statisticalLevel)
           {
            int next=MathMin(m_statisticalLevel+1,target);
            if(next!=m_promotionCandidate){m_promotionCandidate=next;m_promotionStreak=0;}
            if(m_promotionCandidate==next)m_promotionStreak+=events;
            if(m_tradesSinceChange>=PromotionCooldownFor(next) && m_promotionStreak>=m_promotionConfirmations)
               ApplyLevel(next);
           }
         else
           {
            m_promotionCandidate=0;m_promotionStreak=0;
           }

         if(m_statisticalLevel>0 && !RetentionMeets(m_statisticalLevel,shortStats,longStats))
           m_demotionStreak++;
         else
           m_demotionStreak=0;

         if(m_statisticalLevel>0 && m_demotionStreak>=m_demotionConfirmations)
           ApplyLevel(m_statisticalLevel-1);
        }
      m_lastEvidenceSample=evidenceSample;
      m_executionHealthy=executionHealthy;
      RecomputeEffectiveLevel(MathMax(0.0,drawdownPercent));
     }

   void SetContext(bool regimeEligible,bool executionHealthy,double drawdownPercent)
     {
      m_regimeEligible=regimeEligible;
      m_executionHealthy=executionHealthy;
      RecomputeEffectiveLevel(MathMax(0.0,drawdownPercent));
     }

   int StatisticalLevel() const { return m_statisticalLevel; }
   int Level() const { return m_effectiveLevel; }
   int MaxOpenTrades() const { return m_maxOpen; }
   int MaxPositionsPerSymbol() const { return m_perSymbol; }
   int MaxPositionsPerGroup() const { return m_perGroup; }
   bool Expanded() const { return m_effectiveLevel>0; }
   bool ExpansionEvidenceReady() const { return m_statisticalLevel>0; }
  };

#endif
//+------------------------------------------------------------------+
