//+------------------------------------------------------------------+
//| Decision/DecisionFingerprint.mqh                                 |
//| Portable canonical decision serialization and SHA-256 hashing.   |
//+------------------------------------------------------------------+
#ifndef DECISIONFINGERPRINT_MQH
#define DECISIONFINGERPRINT_MQH
#include "TradeDecision.mqh"

string DecisionFpNormalizeString(const string value)
  {
   string out=value;
   StringTrimLeft(out);
   StringTrimRight(out);
   return out;
  }

string DecisionFpCanonical(const TradeDecisionRecord &rec)
  {
   string direction=(rec.setup.type==ORDER_TYPE_BUY)?"BUY":"SELL";
   double entry=(rec.setup.type==ORDER_TYPE_BUY)?rec.setup.entry_top:rec.setup.entry_bottom;
   string canonical=
      "schema_version="+DecisionFpNormalizeString(rec.decision_schema_version)+
      "|decision_id="+IntegerToString(rec.decision_id)+
      "|symbol="+DecisionFpNormalizeString(rec.symbol)+
      "|direction="+direction+
      "|entry="+DoubleToString(entry,8)+
      "|invalidation="+DoubleToString(rec.setup.invalidation,8)+
      "|sl="+DoubleToString(rec.setup.stop_loss,8)+
      "|tp1="+DoubleToString(rec.setup.tp1,8)+
      "|tp2="+DoubleToString(rec.setup.tp2,8)+
      "|final_tp="+DoubleToString(rec.setup.final_tp,8)+
      "|confidence="+DoubleToString(rec.setup.confidence,4)+
      "|action="+TradePolicyToString(rec.action)+
      "|reduce_risk="+(rec.reduce_risk?"true":"false")+
      "|spread_points="+DoubleToString(rec.spread_points,8)+
      "|regime="+EnumToString(rec.setup.reasons.regime)+
      "|strategy="+EnumToString(rec.setup.reasons.selected_strategy)+
      "|session="+EnumToString(rec.setup.reasons.session)+
      "|weight_version="+DecisionFpNormalizeString(rec.weight_version)+
      "|strategy_version="+DecisionFpNormalizeString(rec.strategy_version)+
      "|model_version="+DecisionFpNormalizeString(rec.model_version)+
      "|calibration_version="+DecisionFpNormalizeString(rec.calibration_version)+
      "|feature_schema_version="+DecisionFpNormalizeString(rec.feature_schema_version)+
      "|environment_schema_version="+DecisionFpNormalizeString(rec.environment_schema_version)+
      "|environment_key="+DecisionFpNormalizeString(rec.environment_key);
   return canonical;
  }

string DecisionFpSha256(const string canonical)
  {
   uchar data[];
   const uchar key[] = {};
   uchar result[];
   int copied=StringToCharArray(canonical,data,0,-1,CP_UTF8);
   if(copied<=0)return "";
   ArrayResize(data,copied-1);
   ResetLastError();
   int n=CryptEncode(CRYPT_HASH_SHA256,data,key,result);
   if(n!=32)return "";
   string hex="";
   for(int i=0;i<n;i++)hex+=StringFormat("%02X",(int)result[i]);
   return hex;
  }

string DecisionFingerprintFor(const TradeDecisionRecord &rec)
  {
   return DecisionFpSha256(DecisionFpCanonical(rec));
  }

#endif
//+------------------------------------------------------------------+
