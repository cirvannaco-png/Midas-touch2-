//+------------------------------------------------------------------+
//| Trading/EnvironmentStrategyMemory.mqh                            |
//| Persistent Environment -> Strategy -> Outcome memory.             |
//+------------------------------------------------------------------+
#ifndef ENVIRONMENTSTRATEGYMEMORY_MQH
#define ENVIRONMENTSTRATEGYMEMORY_MQH

#include "../Core/Config.mqh"

struct EnvironmentMemoryEvidence
  { int trades; int wins; int losses; int scratches; double win_rate; double avg_r; double profit_factor; double max_drawdown_r; double avg_mae_r; double avg_mfe_r; double avg_duration; double wilson_low; double wilson_high; int sample_size; string status; double adjustment; };
struct EnvironmentMemoryRecord
  { datetime timestamp; string environment_key; int strategy; double realized_r; double mae_r; double mfe_r; int duration; bool counted; };

class CEnvironmentStrategyMemory
  {
private:
   EnvironmentMemoryRecord m_records[]; string m_filename; int m_minSample; int m_degradedMinSample; double m_bonus; double m_penalty;
   string Bucket(double value,double a,double b,double c) const {if(value<a)return "0";if(value<b)return "1";if(value<c)return "2";return "3";}
   string EnvironmentKey(const SetupReasons &r) const
     {
      double spreadAtr=0.0;if(r.atr_value>0.0&&r.point_size>0.0)spreadAtr=r.spread_points*r.point_size/r.atr_value;
      string structure=EnumToString(r.sweep_grade)+"/"+IntegerToString((int)r.breakout_class)+"/"+IntegerToString((int)r.reversion_class)+"/"+IntegerToString((int)r.keylevel_reaction);
      string trendBucket=Bucket(MathAbs(r.trend_strength),0.25,0.60,0.85);
      return EnumToString(r.regime)+"|"+EnumToString(r.vol_regime)+"|T"+trendBucket+"|L"+IntegerToString(r.liquidity_bucket)+"|N"+EnumToString(r.news_risk)+"|S"+EnumToString(r.session)+"|SP"+Bucket(spreadAtr,0.02,0.05,0.10)+"|A"+EnumToString(r.vol_regime)+"|H"+(r.htf_ob_confluence?"1":"0")+"/"+IntegerToString((int)r.htf_ob_state)+"|V"+EnumToString(r.va_zone)+"|P"+EnumToString(r.phase)+"|M"+structure;
     }
   static double WilsonZ(){return 1.959963984540054;}
   double WilsonLower(int wins,int n) const {if(n<=0)return 0.0;double z=WilsonZ(),p=(double)wins/n,den=1.0+z*z/n,center=p+z*z/(2.0*n),spread=z*MathSqrt((p*(1.0-p)/n)+(z*z/(4.0*n*n)));return (center-spread)/den;}
   double WilsonUpper(int wins,int n) const {if(n<=0)return 0.0;double z=WilsonZ(),p=(double)wins/n,den=1.0+z*z/n,center=p+z*z/(2.0*n),spread=z*MathSqrt((p*(1.0-p)/n)+(z*z/(4.0*n*n)));return (center+spread)/den;}
   void Save() const {if(StringLen(m_filename)==0)return;int h=FileOpen(m_filename,FILE_CSV|FILE_WRITE|FILE_ANSI,',');if(h==INVALID_HANDLE)return;FileWrite(h,"timestamp","environment_key","strategy","realized_r","mae_r","mfe_r","duration","counted");for(int i=0;i<ArraySize(m_records);i++)FileWrite(h,(long)m_records[i].timestamp,m_records[i].environment_key,m_records[i].strategy,m_records[i].realized_r,m_records[i].mae_r,m_records[i].mfe_r,m_records[i].duration,m_records[i].counted?1:0);FileClose(h);}
   void Load(){ArrayFree(m_records);if(StringLen(m_filename)==0||!FileIsExist(m_filename))return;int h=FileOpen(m_filename,FILE_CSV|FILE_READ|FILE_SHARE_READ|FILE_ANSI,',');if(h==INVALID_HANDLE)return;for(int c=0;c<8&&!FileIsEnding(h);c++)FileReadString(h);while(!FileIsEnding(h)){string ts=FileReadString(h);if(StringLen(ts)==0)break;EnvironmentMemoryRecord r;ZeroMemory(r);r.timestamp=(datetime)StringToInteger(ts);r.environment_key=FileReadString(h);r.strategy=(int)StringToInteger(FileReadString(h));r.realized_r=StringToDouble(FileReadString(h));r.mae_r=StringToDouble(FileReadString(h));r.mfe_r=StringToDouble(FileReadString(h));r.duration=(int)StringToInteger(FileReadString(h));r.counted=(StringToInteger(FileReadString(h))!=0);int n=ArraySize(m_records);ArrayResize(m_records,n+1);m_records[n]=r;}FileClose(h);}
public:
   CEnvironmentStrategyMemory():m_filename(""),m_minSample(30),m_degradedMinSample(60),m_bonus(2.0),m_penalty(2.0){}
   void Init(string symbol,int minSample=30,double bonus=2.0,double penalty=2.0){m_filename="MedisTouch_EnvironmentMemory_"+symbol+".csv";m_minSample=MathMax(1,minSample);m_degradedMinSample=m_minSample*2;m_bonus=MathMax(0.0,bonus);m_penalty=MathMax(0.0,penalty);Load();}
   string Key(const SetupReasons &r) const{return EnvironmentKey(r);}
   void RecordOutcome(const SetupReasons &r,ENUM_SELECTED_STRATEGY strategy,double realizedR,double maeR,double mfeR,int duration,datetime timestamp){if(strategy==STRATEGY_NONE)return;EnvironmentMemoryRecord rec;ZeroMemory(rec);rec.timestamp=timestamp;rec.environment_key=EnvironmentKey(r);rec.strategy=(int)strategy;rec.realized_r=realizedR;rec.mae_r=maeR;rec.mfe_r=mfeR;rec.duration=MathMax(0,duration);rec.counted=true;int n=ArraySize(m_records);ArrayResize(m_records,n+1);m_records[n]=rec;Save();}
   bool GetEvidence(const SetupReasons &r,ENUM_SELECTED_STRATEGY strategy,EnvironmentMemoryEvidence &out) const
     {
      ZeroMemory(out);if(strategy==STRATEGY_NONE)return false;string key=EnvironmentKey(r);double cumulative=0.0,peak=0.0;double sumR=0.0,sumMAE=0.0,sumMFE=0.0,sumDuration=0.0,grossProfit=0.0,grossLoss=0.0;int n=0,wins=0,losses=0,scratches=0;
      for(int i=0;i<ArraySize(m_records);i++){EnvironmentMemoryRecord rec=m_records[i];if(!rec.counted||rec.strategy!=(int)strategy||rec.environment_key!=key)continue;n++;sumR+=rec.realized_r;sumMAE+=rec.mae_r;sumMFE+=rec.mfe_r;sumDuration+=rec.duration;cumulative+=rec.realized_r;if(cumulative>peak)peak=cumulative;double dd=peak-cumulative;if(dd>out.max_drawdown_r)out.max_drawdown_r=dd;if(rec.realized_r>0.0){wins++;grossProfit+=rec.realized_r;}else if(rec.realized_r<0.0){losses++;grossLoss+=-rec.realized_r;}else scratches++;}
      out.trades=n;out.wins=wins;out.losses=losses;out.scratches=scratches;out.sample_size=wins+losses;out.win_rate=out.sample_size>0?(double)wins/out.sample_size:0.0;out.avg_r=n>0?sumR/n:0.0;out.profit_factor=grossLoss>0.0?grossProfit/grossLoss:(grossProfit>0.0?999999.0:0.0);out.avg_mae_r=n>0?sumMAE/n:0.0;out.avg_mfe_r=n>0?sumMFE/n:0.0;out.avg_duration=n>0?sumDuration/n:0.0;out.wilson_low=WilsonLower(wins,out.sample_size);out.wilson_high=WilsonUpper(wins,out.sample_size);
      if(out.sample_size<m_minSample){out.status="UNKNOWN";out.adjustment=0.0;return n>0;}
      bool qualified=(out.avg_r>0.0&&out.profit_factor>1.0&&out.wilson_low>=0.50);
      bool degraded=(out.sample_size>=m_degradedMinSample&&out.avg_r<0.0&&out.profit_factor>0.0&&out.profit_factor<1.0&&out.wilson_high<0.50);
      if(qualified){out.status="QUALIFIED";out.adjustment=m_bonus;}else if(degraded){out.status="DEGRADED";out.adjustment=-m_penalty;}else{out.status="NEUTRAL";out.adjustment=0.0;}return true;
     }
   int Count() const{return ArraySize(m_records);} int MinimumSample() const{return m_minSample;} int DegradedMinimumSample() const{return m_degradedMinSample;}
  };
#endif
//+------------------------------------------------------------------+
