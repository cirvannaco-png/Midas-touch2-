//+------------------------------------------------------------------+
//| Decision/DecisionQuality.mqh                                     |
//| Hierarchical structural validation and trade-quality firewall.   |
//+------------------------------------------------------------------+
#ifndef DECISIONQUALITY_MQH
#define DECISIONQUALITY_MQH

#include "../Core/Config.mqh"

struct StructuralValidationResult
  {
   ENUM_STRUCTURAL_STATE state;
   ENUM_STRUCTURE_STAGE stage;
   double score;
   string reason;
  };

struct TradeQualityResult
  {
   ENUM_DECISION_STATE decision;
   ENUM_FIREWALL_LAYER layer;
   ENUM_RISK_CLASS riskClass;
   double qualityScore;
   string reason;
  };

class CSetupLifecyclePolicy
  {
public:
   bool CanTransition(ENUM_SETUP_LIFECYCLE current,ENUM_SETUP_LIFECYCLE next) const
     {
      if(current==next) return true;
      if(current==SETUP_DETECTED && (next==SETUP_ARMED || next==SETUP_WAITING_RETEST || next==SETUP_EXPIRED)) return true;
      if(current==SETUP_ARMED && (next==SETUP_WAITING_RETEST || next==SETUP_RETEST_CONFIRMED || next==SETUP_ENTRY_ELIGIBLE || next==SETUP_EXPIRED)) return true;
      if(current==SETUP_WAITING_RETEST && (next==SETUP_RETEST_CONFIRMED || next==SETUP_ENTRY_ELIGIBLE || next==SETUP_EXPIRED)) return true;
      if(current==SETUP_RETEST_CONFIRMED && (next==SETUP_ENTRY_ELIGIBLE || next==SETUP_EXPIRED)) return true;
      if(current==SETUP_ENTRY_ELIGIBLE && next==SETUP_EXPIRED) return true;
      return false;
     }

   bool Advance(TradeSetup &setup,ENUM_SETUP_LIFECYCLE next) const
     {
      if(!CanTransition(setup.setup_lifecycle,next)) return false;
      setup.setup_lifecycle=next;
      return true;
     }
  };

class CStructuralValidator
  {
private:
   double SweepGradeScore(ENUM_SWEEP_GRADE grade) const
     {
      switch(grade)
        {
         case SWEEP_GRADE_A: return 1.00;
         case SWEEP_GRADE_B: return 0.80;
         case SWEEP_GRADE_C: return 0.55;
         default:            return 0.00;
        }
     }

public:
   StructuralValidationResult Validate(const TradeSetup &setup,
                                        bool requireCausalFVG,
                                        bool fvgAvailable) const
     {
      StructuralValidationResult out;
      out.state=STRUCTURE_INVALID;
      out.stage=STRUCTURE_STAGE_NO_STRUCTURE;
      out.score=0.0;
      out.reason="";

      const SetupReasons r=setup.reasons;

      if(r.inducement_structure_type!=INDUCEMENT_STRUCTURE_NONE)
         out.stage=STRUCTURE_STAGE_LIQUIDITY_IDENTIFIED;
      else
        {
         out.reason="no authoritative liquidity structure";
         return out;
        }

      if(!r.liquidity_swept)
        {
         out.reason="liquidity identified but not swept";
         return out;
        }
      out.stage=STRUCTURE_STAGE_LIQUIDITY_SWEPT;

      if(r.displacement_atr<=0.0)
        {
         out.reason="no production displacement measurement";
         return out;
        }
      out.stage=STRUCTURE_STAGE_VALID_DISPLACEMENT;

      if(!r.bos_confirmed)
        {
         out.reason="liquidity swept but no confirming BOS";
         return out;
        }
      out.stage=STRUCTURE_STAGE_CONFIRMING_BOS;

      if(!fvgAvailable)
        {
         out.reason="no live FVG available for entry";
         return out;
        }

      if(requireCausalFVG && !r.fvg_causal)
        {
         out.reason="entry FVG is not causally downstream of the production BOS";
         return out;
        }
      if(r.fvg_causal)
         out.stage=STRUCTURE_STAGE_CAUSAL_FVG;
      else
         out.stage=STRUCTURE_STAGE_CAUSAL_FVG;

      if(!r.premium_discount_ok || r.value_area_contradiction)
        {
         out.reason="location actively contradicts the trade thesis";
         return out;
        }
      out.stage=STRUCTURE_STAGE_LOCATION_VALID;

      bool freshOrTested=(r.fvg_state==FVG_FRESH || r.fvg_state==FVG_TESTED);
      if(!freshOrTested || r.time_decay<=0.0)
        {
         out.reason="entry zone is no longer fresh/tradeable or structure has fully decayed";
         return out;
        }
      out.stage=STRUCTURE_STAGE_FRESHNESS_VALID;

      bool buy=(setup.type==ORDER_TYPE_BUY);
      bool invalidationDefined=(setup.invalidation>0.0 && setup.stop_loss>0.0 &&
                                ((buy && setup.stop_loss<setup.invalidation && setup.invalidation<setup.entry_bottom) ||
                                 (!buy && setup.stop_loss>setup.invalidation && setup.invalidation>setup.entry_top)));
      if(!invalidationDefined)
        {
         out.reason="structural invalidation/stop geometry is undefined or inverted";
         return out;
        }
      out.stage=STRUCTURE_STAGE_INVALIDATION_DEFINED;

      double sweep=SweepGradeScore(r.sweep_grade);
      double bos=MathMin(MathMax(r.bos_strength,0.0),1.0);
      double displacement=MathMin(MathMax(r.displacement_atr/2.0,0.0),1.0);
      double fvgQuality=(r.fvg_state==FVG_FRESH)?1.0:0.70;
      double location=(r.premium_discount_ok && !r.value_area_contradiction)?1.0:0.0;
      double invalidation=(r.invalidation_distance_atr>0.0)?MathMin(1.0,r.invalidation_distance_atr/2.0):1.0;

      out.score=100.0*(0.20*sweep+0.25*bos+0.15*displacement+0.15*fvgQuality+0.15*location+0.10*invalidation);
      bool degraded=(r.sweep_grade==SWEEP_GRADE_C || r.bos_strength<0.50 ||
                      r.fvg_state==FVG_TESTED || r.time_decay<0.55);
      if(degraded)
        {
         out.state=STRUCTURE_DEGRADED;
         out.stage=STRUCTURE_STAGE_STRUCTURALLY_VALID;
         out.reason="structure is complete but contains degraded-quality components";
         return out;
        }

      out.state=STRUCTURE_VALID;
      out.stage=STRUCTURE_STAGE_STRUCTURALLY_VALID;
      out.reason="production SMC chain is structurally complete";
      return out;
     }
  };

class CTradeQualityFirewall
  {
private:
   double Clamp01(double v) const { return MathMin(1.0,MathMax(0.0,v)); }

   double EnvironmentFactor(const SetupReasons &r) const
     {
      double s=r.env_score;
      if(s<=0.0) s=1.0;
      return Clamp01(s);
     }

   void ComputeFamilyScores(SetupReasons &r,bool isSMC)
     {
      double sweep=0.0;
      switch(r.sweep_grade)
        {
         case SWEEP_GRADE_A: sweep=1.0; break;
         case SWEEP_GRADE_B: sweep=0.80; break;
         case SWEEP_GRADE_C: sweep=0.55; break;
         default: sweep=0.0; break;
        }

      double structure=0.35*Clamp01(r.bos_strength)+
                       0.25*Clamp01(r.displacement_atr/2.0)+
                       0.20*(r.bos_confirmed?1.0:0.0)+
                       0.20*EnvironmentFactor(r);
      double liquidity=0.35*sweep+
                       0.25*Clamp01(r.liquidity_score)+
                       0.20*(r.liquidity_age_bars>=0 ? 1.0/(1.0+0.10*r.liquidity_age_bars) : 0.0)+
                       0.20*(r.sweep_follow_through?1.0:0.0);
      double location=0.35*(r.premium_discount_ok?1.0:0.0)+
                      0.25*(r.fib_in_zone?1.0:0.0)+
                      0.20*(r.value_area_contradiction?0.0:r.va_score>0.0?r.va_score:0.5)+
                      0.20*(r.htf_ob_confluence?1.0:0.5);
      double fvgState=!isSMC ? 1.0 : (r.fvg_state==FVG_FRESH ? 1.0 : (r.fvg_state==FVG_TESTED ? 0.70 : 0.0));
      double chase=r.chase_ok?1.0:0.0;
      double session=r.session_ok?1.0:0.0;
      double spreadFactor=1.0;
      if(r.point_size>0.0 && r.atr_value>0.0)
        {
         double spreadAtr=r.spread_points*r.point_size/r.atr_value;
         spreadFactor=Clamp01(1.0-spreadAtr/0.10);
        }
      double execution=0.35*fvgState+0.25*chase+0.20*session+0.20*spreadFactor;

      r.structure_family_score=100.0*Clamp01(structure);
      r.liquidity_family_score=100.0*Clamp01(liquidity);
      r.location_family_score=100.0*Clamp01(location);
      r.execution_family_score=100.0*Clamp01(execution);
      r.environment_family_score=100.0*EnvironmentFactor(r);

      r.quality_score=0.30*r.structure_family_score+
                      0.25*r.liquidity_family_score+
                      0.20*r.location_family_score+
                      0.15*r.execution_family_score+
                      0.10*r.environment_family_score;
     }

public:
   TradeQualityResult Evaluate(TradeSetup &setup,
                               bool isSMC,
                               bool requireStructuralValidator,
                               bool enableEnvironmentHardBlock,
                               int degradedMinSample,
                               double minQualityScore,
                               double maxExecutionSpreadPoints,
                               bool requireCausalFVG) const
     {
      TradeQualityResult out;
      out.decision=DECISION_REJECT;
      out.layer=FIREWALL_NONE;
      out.riskClass=RISK_CLASS_NONE;
      out.qualityScore=0.0;
      out.reason="";

      SetupReasons &r=setup.reasons;
      ComputeFamilyScores(r,isSMC);
      out.qualityScore=r.quality_score;
      r.decision_blocking_layer=FIREWALL_NONE;
      r.decision_reason="";
      r.decision_state=DECISION_REJECT;
      r.risk_class=RISK_CLASS_NONE;
      r.setup_lifecycle=SETUP_DETECTED;
      CSetupLifecyclePolicy lifecycle;

      if(isSMC && requireStructuralValidator)
        {
         CStructuralValidator validator;
         StructuralValidationResult sv=validator.Validate(setup,requireCausalFVG,r.fvg_state==FVG_FRESH||r.fvg_state==FVG_TESTED);
         r.structural_state=sv.state;
         r.structural_stage=sv.stage;
         r.structural_score=sv.score;
         r.structural_reason=sv.reason;
         if(sv.state==STRUCTURE_INVALID)
           {
            r.decision_blocking_layer=FIREWALL_STRUCTURE;
            r.decision_reason=sv.reason;
            lifecycle.Advance(setup,SETUP_EXPIRED);
            out.layer=FIREWALL_STRUCTURE;
            out.reason=sv.reason;
            return out;
           }
        }

      if(enableEnvironmentHardBlock && r.environment_memory_status=="DEGRADED" &&
         r.environment_memory_sample>=MathMax(1,degradedMinSample))
        {
         r.decision_blocking_layer=FIREWALL_ENVIRONMENT;
         r.decision_reason="historically degraded strategy/environment combination";
         lifecycle.Advance(setup,SETUP_EXPIRED);
         out.layer=FIREWALL_ENVIRONMENT;
         out.reason=r.decision_reason;
         return out;
        }

      if(r.session==SESSION_DEAD || r.session_ok==false)
        {
         r.decision_blocking_layer=FIREWALL_EXECUTION;
         r.decision_reason="execution session is not allowed";
         lifecycle.Advance(setup,SETUP_EXPIRED);
         out.layer=FIREWALL_EXECUTION;
         out.reason=r.decision_reason;
         return out;
        }

      if(r.news_risk==NEWS_BLOCKED)
        {
         r.decision_blocking_layer=FIREWALL_EXECUTION;
         r.decision_reason="blocked news window";
         lifecycle.Advance(setup,SETUP_EXPIRED);
         out.layer=FIREWALL_EXECUTION;
         out.reason=r.decision_reason;
         return out;
        }

      if(!r.chase_ok || (maxExecutionSpreadPoints>0.0 && r.spread_points>maxExecutionSpreadPoints))
        {
         r.decision_state=DECISION_WAIT;
         r.setup_lifecycle=SETUP_WAITING_RETEST;
         r.decision_blocking_layer=FIREWALL_EXECUTION;
         r.decision_reason=!r.chase_ok ? "entry is too far from confirmed structure; wait for retrace" : "spread is too wide; wait for execution conditions to normalize";
         out.decision=DECISION_WAIT;
         out.layer=FIREWALL_EXECUTION;
         out.riskClass=RISK_CLASS_MINIMAL;
         out.reason=r.decision_reason;
         out.qualityScore=r.quality_score;
         return out;
        }

      if(isSMC && r.structural_state!=STRUCTURE_INVALID)
        {
         lifecycle.Advance(setup,SETUP_ARMED);
         if(r.fvg_state==FVG_TESTED)
            lifecycle.Advance(setup,SETUP_RETEST_CONFIRMED);
        }

      if(isSMC && r.structural_state==STRUCTURE_DEGRADED)
        {
         // Degraded is not universally invalid. Require a stronger composite
         // quality score so the system abstains without imposing a universal
         // weak-BOS or weak-sweep ban.
         if(r.quality_score<MathMax(minQualityScore,72.0))
           {
            r.decision_blocking_layer=FIREWALL_STRUCTURE;
            r.decision_reason="structurally degraded setup below the quality threshold";
            lifecycle.Advance(setup,SETUP_EXPIRED);
            out.layer=FIREWALL_STRUCTURE;
            out.reason=r.decision_reason;
            return out;
           }
        }

      if(r.quality_score<minQualityScore)
        {
         r.decision_blocking_layer=FIREWALL_RISK;
         r.decision_reason=StringFormat("composite trade quality %.1f below minimum %.1f",r.quality_score,minQualityScore);
         lifecycle.Advance(setup,SETUP_EXPIRED);
         out.layer=FIREWALL_RISK;
         out.reason=r.decision_reason;
         return out;
        }

      if(setup.invalidation<=0.0 || setup.stop_loss<=0.0 ||
         ((setup.type==ORDER_TYPE_BUY && setup.stop_loss>=setup.invalidation) ||
          (setup.type==ORDER_TYPE_SELL && setup.stop_loss<=setup.invalidation)))
        {
         r.decision_blocking_layer=FIREWALL_RISK;
         r.decision_reason="risk geometry violates immutable structural invalidation";
         lifecycle.Advance(setup,SETUP_EXPIRED);
         out.layer=FIREWALL_RISK;
         out.reason=r.decision_reason;
         return out;
        }

      lifecycle.Advance(setup,SETUP_ENTRY_ELIGIBLE);
      if(r.quality_score>=85.0) out.risk_class=RISK_CLASS_HIGH_CONVICTION;
      else if(r.quality_score>=72.0) out.riskClass=RISK_CLASS_STANDARD;
      else out.riskClass=RISK_CLASS_MINIMAL;

      out.decision=DECISION_TRADE;
      out.reason="trade passed hierarchical structural/environment/execution/risk firewalls";
      if(out.riskClass==RISK_CLASS_NONE) out.riskClass=RISK_CLASS_MINIMAL;
      r.risk_class=out.riskClass;
      r.decision_state=DECISION_TRADE;
      r.decision_reason=out.reason;
      return out;
     }

   void FinalizeWithCalibration(TradeSetup &setup,bool requireCalibratedProbability,double minCalibratedProbability) const
     {
      if(setup.decision_state==DECISION_REJECT) return;
      if(!requireCalibratedProbability) return;

      if(!setup.calibration_has_enough_data)
        {
         setup.decision_state=DECISION_WAIT;
         setup.setup_lifecycle=SETUP_WAITING_RETEST;
         setup.reasons.decision_state=DECISION_WAIT;
         setup.reasons.decision_blocking_layer=FIREWALL_CALIBRATION;
         setup.reasons.decision_reason="calibration sample is insufficient for an evidence-gated trade";
         setup.active=true;
         return;
        }

      if(setup.calibrated_probability<minCalibratedProbability)
        {
         setup.decision_state=DECISION_REJECT;
         setup.setup_lifecycle=SETUP_EXPIRED;
         setup.reasons.decision_state=DECISION_REJECT;
         setup.reasons.decision_blocking_layer=FIREWALL_CALIBRATION;
         setup.reasons.decision_reason=StringFormat("calibrated probability %.1f%% below minimum %.1f%%",
                                                     setup.calibrated_probability,minCalibratedProbability);
         setup.active=true;
         return;
        }

      if(setup.reasons.quality_score>=90.0 && setup.calibrated_probability>=minCalibratedProbability+8.0)
         {
          setup.risk_class=RISK_CLASS_HIGH_CONVICTION;
          setup.reasons.risk_class=RISK_CLASS_HIGH_CONVICTION;
         }
     }
  };

#endif
//+------------------------------------------------------------------+
