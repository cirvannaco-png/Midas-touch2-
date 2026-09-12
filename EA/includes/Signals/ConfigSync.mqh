//+------------------------------------------------------------------+
//| ConfigSync.mqh                                                   |
//| Fail-closed EA transport for immutable configuration envelopes.   |
//+------------------------------------------------------------------+
#ifndef CONFIGSYNC_MQH
#define CONFIGSYNC_MQH

#include "ConfigSyncContract.mqh"

class CConfigSync
  {
private:
   string m_symbol;
   string m_endpoint;
   string m_apiKey;
   string m_compiledWeightVersion;
   int    m_timeoutMs;
   string m_lastSeenHash;
   string m_lastAckedHash;
   bool   m_everWarned;
   CConfigSyncContract m_contract;

   bool ExtractJsonStringField(const string &json,const string field,string &out);
   bool ExtractJsonIntField(const string &json,const string field,int &out);
   bool PostAcknowledgement(const string configHash,const string strategy,
                            const string timeframe,const int version);

public:
   CConfigSync(void) : m_timeoutMs(5000),m_lastSeenHash(""),m_lastAckedHash(""),m_everWarned(false) {}

   void Init(const string symbol,const string signalEndpoint,const string apiKey,
             const string compiledWeightVersion,const int timeoutMs=5000)
     {
      m_symbol=symbol;
      m_apiKey=apiKey;
      m_compiledWeightVersion=compiledWeightVersion;
      m_timeoutMs=MathMax(1000,timeoutMs);

      string suffix="/signal";
      if(StringLen(signalEndpoint)<StringLen(suffix) ||
         StringSubstr(signalEndpoint,StringLen(signalEndpoint)-StringLen(suffix))!=suffix)
        {
         PrintFormat("MedisTouch ConfigSync: endpoint %s must end in /signal — disabled.",signalEndpoint);
         m_endpoint="";
         return;
        }
      m_endpoint=StringSubstr(signalEndpoint,0,StringLen(signalEndpoint)-StringLen(suffix)) + "/config/" + symbol;
     }

   void Poll(void);
  };
//+------------------------------------------------------------------+
void CConfigSync::Poll(void)
  {
   if(StringLen(m_endpoint)==0) return;

   char data[]; char result[]; string resultHeaders;
   string headers="Content-Type: application/json\r\n";
   if(StringLen(m_apiKey)>0) headers+="X-API-Key: "+m_apiKey+"\r\n";

   ResetLastError();
   int status=WebRequest("GET",m_endpoint,headers,m_timeoutMs,data,result,resultHeaders);
   if(status==-1)
     {
      int err=GetLastError();
      if(err==4060) PrintFormat("MedisTouch ConfigSync: WebRequest blocked for %s — add the URL to MT5 allowed WebRequest URLs.",m_endpoint);
      return;
     }
   if(status<200 || status>=300) return;

   string body=CharArrayToString(result,0,WHOLE_ARRAY,CP_UTF8);
   string configHash,strategy,instrument,timeframe,dataVersion,optimizerVersion,lifecycle;
   int version=0;
   if(!ExtractJsonStringField(body,"config_hash",configHash) ||
      !ExtractJsonStringField(body,"strategy",strategy) ||
      !ExtractJsonStringField(body,"instrument",instrument) ||
      !ExtractJsonStringField(body,"timeframe",timeframe) ||
      !ExtractJsonStringField(body,"data_version",dataVersion) ||
      !ExtractJsonStringField(body,"optimizer_version",optimizerVersion) ||
      !ExtractJsonStringField(body,"lifecycle_status",lifecycle) ||
      !ExtractJsonIntField(body,"version",version)) return;

   m_contract.SetEnvelope(configHash,strategy,instrument,timeframe,dataVersion,optimizerVersion,lifecycle,version);
   string reason;
   if(!m_contract.ValidateMetadata(m_symbol,EnumToString(_Period),"SMC",reason))
     {
      if(!m_everWarned || m_lastSeenHash!=configHash)
        {
         PrintFormat("MedisTouch ConfigSync: configuration %s rejected — %s",configHash,reason);
         m_everWarned=true;
        }
      m_lastSeenHash=configHash;
      return;
     }

   // A valid envelope is not considered synchronized until its ACK has
   // actually succeeded. The old implementation updated m_lastSeenHash
   // even when POST /ack failed, which caused the next poll to return early
   // forever and left the server waiting for an ACK that would never arrive.
   if(m_lastAckedHash==configHash) { m_lastSeenHash=configHash; m_everWarned=false; return; }

   if(PostAcknowledgement(configHash,strategy,timeframe,version))
     {
      m_lastAckedHash=configHash;
      m_lastSeenHash=configHash;
      m_everWarned=false;
      PrintFormat("MedisTouch ConfigSync: validated and acknowledged config %s; live numeric inputs remain unchanged.",configHash);
     }
   else
     {
      m_lastSeenHash=configHash;
      m_everWarned=true;
      PrintFormat("MedisTouch ConfigSync: ACK failed for config %s; will retry on the next poll.",configHash);
     }
  }
//+------------------------------------------------------------------+
bool CConfigSync::PostAcknowledgement(const string configHash,const string strategy,
                                       const string timeframe,const int version)
  {
   string body=StringFormat("{\"config_hash\":\"%s\",\"strategy\":\"%s\",\"timeframe\":\"%s\",\"version\":%d}",
                            configHash,strategy,timeframe,version);
   char postData[];
   int copied=StringToCharArray(body,postData,0,WHOLE_ARRAY,CP_UTF8);
   if(copied>0) ArrayResize(postData,copied-1);
   char result[]; string resultHeaders;
   string headers="Content-Type: application/json\r\n";
   if(StringLen(m_apiKey)>0) headers+="X-API-Key: "+m_apiKey+"\r\n";
   ResetLastError();
   int status=WebRequest("POST",m_endpoint+"/ack",headers,m_timeoutMs,postData,result,resultHeaders);
   if(status==-1) return false;
   return status>=200 && status<300;
  }
//+------------------------------------------------------------------+
bool CConfigSync::ExtractJsonStringField(const string &json,const string field,string &out)
  {
   string needle="\""+field+"\":";
   int pos=StringFind(json,needle);
   if(pos<0) return false;
   int valueStart=pos+StringLen(needle);
   if(StringSubstr(json,valueStart,4)=="null") { out=""; return true; }
   if(StringGetCharacter(json,valueStart)!='"') return false;
   valueStart++;
   int valueEnd=StringFind(json,"\"",valueStart);
   if(valueEnd<0) return false;
   out=StringSubstr(json,valueStart,valueEnd-valueStart);
   return true;
  }
//+------------------------------------------------------------------+
bool CConfigSync::ExtractJsonIntField(const string &json,const string field,int &out)
  {
   string needle="\""+field+"\":";
   int pos=StringFind(json,needle);
   if(pos<0) return false;
   int start=pos+StringLen(needle);
   string digits="";
   for(int i=start;i<StringLen(json);i++)
     {
      ushort ch=StringGetCharacter(json,i);
      if(ch<'0' || ch>'9') break;
      digits+=StringSubstr(json,i,1);
     }
   if(StringLen(digits)==0) return false;
   out=(int)StringToInteger(digits);
   return true;
  }
#endif
//+------------------------------------------------------------------+
