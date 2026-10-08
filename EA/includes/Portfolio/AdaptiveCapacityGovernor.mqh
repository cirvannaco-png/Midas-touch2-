//+------------------------------------------------------------------+
//| Portfolio/AdaptiveCapacityGovernor.mqh                           |
//| Performance-conditioned execution capacity.                     |
//| Expands position capacity only after resolved outcomes support   |
//| the edge; never changes baseline per-trade risk.                 |
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
   int    m_level;
   int    m_maxOpen;
   int    m_perSymbol;
   int    m_perGroup;

   int PerformanceLevel(const OutcomeStats &stats,double drawdownPercent)
     {
      if(!m_enabled) return 0;
      if(drawdownPercent>=m_capacityBlockDrawdown) return 0;

      int sample=stats.wins+stats.losses;
      if(sample<=0) return 0;

      double winRate=100.0*(double)stats.wins/(double)sample;
      double avgR=stats.AverageRMultiple();
      double pf=stats.ProfitFactor();

      bool elite=sample>=m_minEliteSample &&
                 winRate>=m_eliteWinRate &&
                 avgR>=m_eliteAvgR &&
                 (pf<0.0 || pf>=m_elitePF);
      if(elite) return 3;

      bool proven=sample>=m_minProvenSample &&
                  winRate>=m_provenWinRate &&
                  avgR>=m_provenAvgR &&
                  (pf<0.0 || pf>=m_provenPF);
      if(proven) return 2;

      bool strong=sample>=m_minStrongSample &&
                  winRate>=m_strongWinRate &&
                  avgR>=m_strongAvgR &&
                  (pf<0.0 || pf>=m_strongPF);
      if(strong) return 1;

      return 0;
     }

public:
   CAdaptiveCapacityGovernor():
      m_enabled(true),
      m_minStrongSample(20),m_minProvenSample(35),m_minEliteSample(50),
      m_strongWinRate(70.0),m_provenWinRate(75.0),m_eliteWinRate(80.0),
      m_strongAvgR(0.05),m_provenAvgR(0.10),m_eliteAvgR(0.15),
      m_strongPF(1.15),m_provenPF(1.25),m_elitePF(1.50),
      m_capacityBlockDrawdown(5.0),
      m_baselineMaxOpen(3),m_baselinePerSymbol(3),m_baselinePerGroup(3),
      m_strongMaxOpen(4),m_strongPerSymbol(4),m_strongPerGroup(4),
      m_provenMaxOpen(5),m_provenPerSymbol(5),m_provenPerGroup(5),
      m_eliteMaxOpen(6),m_elitePerSymbol(6),m_elitePerGroup(6),
      m_level(0),m_maxOpen(3),m_perSymbol(3),m_perGroup(3) {}

   void Init(bool enabled,
             int baselineMaxOpen,int baselinePerSymbol,int baselinePerGroup,
             int strongMaxOpen,int strongPerSymbol,int strongPerGroup,
             int provenMaxOpen,int provenPerSymbol,int provenPerGroup,
             int eliteMaxOpen,int elitePerSymbol,int elitePerGroup,
             int minStrongSample,int minProvenSample,int minEliteSample,
             double strongWinRate,double provenWinRate,double eliteWinRate,
             double strongAvgR,double provenAvgR,double eliteAvgR,
             double strongPF,double provenPF,double elitePF,
             double capacityBlockDrawdown)
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
      m_level=0;
      m_maxOpen=m_baselineMaxOpen;
      m_perSymbol=m_baselinePerSymbol;
      m_perGroup=m_baselinePerGroup;
     }

   void Refresh(const OutcomeStats &stats,double drawdownPercent)
     {
      m_level=PerformanceLevel(stats,MathMax(0.0,drawdownPercent));

      if(m_level<=0)
        {
         m_maxOpen=m_baselineMaxOpen;
         m_perSymbol=m_baselinePerSymbol;
         m_perGroup=m_baselinePerGroup;
        }
      else if(m_level==1)
        {
         m_maxOpen=m_strongMaxOpen;
         m_perSymbol=m_strongPerSymbol;
         m_perGroup=m_strongPerGroup;
        }
      else if(m_level==2)
        {
         m_maxOpen=m_provenMaxOpen;
         m_perSymbol=m_provenPerSymbol;
         m_perGroup=m_provenPerGroup;
        }
      else
        {
         m_maxOpen=m_eliteMaxOpen;
         m_perSymbol=m_elitePerSymbol;
         m_perGroup=m_elitePerGroup;
        }
     }

   int Level() const { return m_level; }
   int MaxOpenTrades() const { return m_maxOpen; }
   int MaxPositionsPerSymbol() const { return m_perSymbol; }
   int MaxPositionsPerGroup() const { return m_perGroup; }
   bool Expanded() const { return m_level>0; }
  };

#endif
//+------------------------------------------------------------------+
