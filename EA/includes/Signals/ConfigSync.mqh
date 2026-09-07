//+------------------------------------------------------------------+
//| ConfigSync.mqh                                                   |
//| Fail-closed EA transport for the immutable configuration envelope. |
//| This does NOT apply numeric parameters to the live strategy.       |
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
   bool   m_everWarned;
   CConfigSyncContract m_contract;

   bool ExtractJsonStringField(const string &json, const string field, string &out);
   bool ExtractJsonIntField(const string &json, const string field, int &out);
   bool PostAcknowledgement(const string configHash, const string strategy,
                            const string timeframe, const int version);

public:
   CConfigSync(void) : m_timeoutMs(5000), m_lastSeenHash(""), m_everWarned(false) {}

   void Init(const string symbol, const string signalEndpoint, const string apiKey,
             const string compiledWeightVersion, const int timeoutMs = 5000)
     {
      m_symbol = symbol;
      m_apiKey = apiKey;
      m_compiledWeightVersion = compiledWeightVersion;
      m_timeoutMs = timeoutMs;

      int pos = StringFind(signalEndpoint, "/signal");
      if(pos < 0)
        {
         PrintFormat("MedisTouch ConfigSync: endpoint %s doesn't end in /signal — disabled.", signalEndpoint);
         m_endpoint = "";
         return;
        }
      m_endpoint = StringSubstr(signalEndpoint, 0, pos) + "/config/" + symbol;
     }

   void Poll(void);
  };

void CConfigSync::Poll(void)
  {
   if(StringLen(m_endpoint) == 0) return;

   char data[];
   char result[];
   string resultHeaders;
   string headers = "Content-Type: application/json\r\n";
   if(StringLen(m_apiKey) > 0)
      headers += "X-API-Key: " + m_apiKey + "\r\n";

   ResetLastError();
   int status = WebRequest("GET", m_endpoint, headers, m_timeoutMs, data, result, resultHeaders);
   if(status == -1)
     {
      int err = GetLastError();
      if(err == 4060)
         PrintFormat("MedisTouch ConfigSync: WebRequest blocked for %s — add it under Tools > Options > Expert Advisors > Allow WebRequest for listed URL.", m_endpoint);
      return;
     }
   if(status < 200 || status >= 300) return;

   string body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
   string configHash, strategy, instrument, timeframe, dataVersion, optimizerVersion, lifecycle;
   int version = 0;
   if(!ExtractJsonStringField(body, "config_hash", configHash) ||
      !ExtractJsonStringField(body, "strategy", strategy) ||
      !ExtractJsonStringField(body, "instrument", instrument) ||
      !ExtractJsonStringField(body, "timeframe", timeframe) ||
      !ExtractJsonStringField(body, "data_version", dataVersion) ||
      !ExtractJsonStringField(body, "optimizer_version", optimizerVersion) ||
      !ExtractJsonStringField(body, "lifecycle_status", lifecycle) ||
      !ExtractJsonIntField(body, "version", version))
      return;

   m_contract.SetEnvelope(configHash, strategy, instrument, timeframe, dataVersion,
                          optimizerVersion, lifecycle, version);

   string reason;
   // The current EA's live strategy is the existing SMC analysis engine.
   // This validation is deliberately independent of the numeric scoring inputs.
   bool valid = m_contract.ValidateMetadata(m_symbol, EnumToString(PERIOD_CURRENT), "SMC", reason);
   // ConfigSync's endpoint is symbol-scoped; timeframe is validated against
   // the chart context below rather than assuming M15/H1/etc in the bridge.
   valid = m_contract.ValidateMetadata(m_symbol, EnumToString(_Period), "SMC", reason);
   if(!valid)
     {
      if(!m_everWarned || m_lastSeenHash != configHash)
        {
         PrintFormat("MedisTouch ConfigSync: configuration %s rejected — %s", configHash, reason);
         m_everWarned = true;
        }
      m_lastSeenHash = configHash;
      return;
     }

   if(m_lastSeenHash == configHash && m_everWarned == false)
      return;

   // ACK is an explicit protocol event, not permission to mutate live inputs.
   // The bridge activates only after this exact hash is acknowledged.
   if(PostAcknowledgement(configHash, strategy, timeframe, version))
     {
      PrintFormat("MedisTouch ConfigSync: validated and acknowledged config %s; live numeric inputs remain unchanged.", configHash);
      m_everWarned = false;
   }
   m_lastSeenHash = configHash;
  }

bool CConfigSync::PostAcknowledgement(const string configHash, const string strategy,
                                       const string timeframe, const int version)
  {
   string body = StringFormat("{\"config_hash\":\"%s\",\"strategy\":\"%s\",\"timeframe\":\"%s\",\"version\":%d}",
                              configHash, strategy, timeframe, version);
   char postData[];
   int copied = StringToCharArray(body, postData, 0, WHOLE_ARRAY, CP_UTF8);
   if(copied > 0) ArrayResize(postData, copied - 1);

   char result[];
   string resultHeaders;
   string headers = "Content-Type: application/json\r\n";
   if(StringLen(m_apiKey) > 0)
      headers += "X-API-Key: " + m_apiKey + "\r\n";

   ResetLastError();
   int status = WebRequest("POST", m_endpoint + "/ack", headers, m_timeoutMs,
                           postData, result, resultHeaders);
   if(status == -1)
     {
      PrintFormat("MedisTouch ConfigSync: ACK WebRequest failed for %s (error %d).", m_endpoint, GetLastError());
      return false;
     }
   if(status < 200 || status >= 300)
     {
      PrintFormat("MedisTouch ConfigSync: ACK rejected for %s (HTTP %d).", configHash, status);
      return false;
     }
   return true;
  }

bool CConfigSync::ExtractJsonStringField(const string &json, const string field, string &out)
  {
   string needle = "\"" + field + "\":";
   int pos = StringFind(json, needle);
   if(pos < 0) return false;
   int valueStart = pos + StringLen(needle);
   if(StringSubstr(json, valueStart, 4) == "null") { out = ""; return true; }
   if(StringGetCharacter(json, valueStart) != '"') return false;
   valueStart++;
   int valueEnd = StringFind(json, "\"", valueStart);
   if(valueEnd < 0) return false;
   out = StringSubstr(json, valueStart, valueEnd - valueStart);
   return true;
  }

bool CConfigSync::ExtractJsonIntField(const string &json, const string field, int &out)
  {
   string needle = "\"" + field + "\":";
   int pos = StringFind(json, needle);
   if(pos < 0) return false;
   int start = pos + StringLen(needle);
   string digits = "";
   for(int i = start; i < StringLen(json); i++)
     {
      ushort ch = StringGetCharacter(json, i);
      if(ch < '0' || ch > '9') break;
      digits += ShortToString((short)ch);
     }
   if(StringLen(digits) == 0) return false;
   out = (int)StringToInteger(digits);
   return true;
  }

#endif // CONFIGSYNC_MQH
