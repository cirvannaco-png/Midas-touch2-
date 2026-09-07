//+------------------------------------------------------------------+
//| ConfigSync.mqh                                                    |
//|                                                                    |
//| v2.11+ observes the bridge configuration endpoint. The original    |
//| weight-version drift warning remains intentionally intact. The     |
//| EA-side contract is now bound here as a fail-closed validation      |
//| boundary: metadata/hash/ACK can never activate a configuration     |
//| unless every required field agrees. Numeric trading inputs are not  |
//| mutated by this module.                                           |
//+------------------------------------------------------------------+
#ifndef CONFIGSYNC_MQH
#define CONFIGSYNC_MQH

#include "ConfigSyncContract.mqh"

class CConfigSync
  {
private:
   string   m_symbol;
   string   m_endpoint;
   string   m_apiKey;
   string   m_compiledWeightVersion;
   int      m_timeoutMs;
   string   m_lastSeenApproved;
   bool     m_everWarned;
   CConfigSyncContract m_contract;

   bool     ExtractJsonStringField(const string &json, string field, string &out);

public:
            CConfigSync(void) : m_timeoutMs(5000), m_lastSeenApproved(""), m_everWarned(false) {}

   void     Init(string symbol, string signalEndpoint, string apiKey, string compiledWeightVersion, int timeoutMs = 5000)
     {
      m_symbol = symbol;
      m_apiKey = apiKey;
      m_compiledWeightVersion = compiledWeightVersion;
      m_timeoutMs = timeoutMs;
      m_contract.Reset();

      int pos = StringFind(signalEndpoint, "/signal");
      if(pos < 0)
        {
         PrintFormat("MedisTouch ConfigSync: endpoint %s doesn't end in /signal — config sync disabled for this instance.", signalEndpoint);
         m_endpoint = "";
         return;
        }
      m_endpoint = StringSubstr(signalEndpoint, 0, pos) + "/config/" + symbol;
     }

   // The transport currently exposes the legacy approved weight-version
   // field. That remains observation-only. A future full envelope may be
   // loaded into m_contract, but activation must pass CanActivate() first.
   void     Poll(void);

   bool     ValidateCandidate(const string configHash,
                              const string strategy,
                              const string instrument,
                              const string timeframe,
                              const string dataVersion,
                              const string optimizerVersion,
                              const string lifecycle,
                              const int version,
                              string &reason)
     {
      m_contract.SetEnvelope(configHash, strategy, instrument, timeframe,
                             dataVersion, optimizerVersion, lifecycle, version);
      return m_contract.ValidateMetadata(instrument, timeframe, strategy, reason);
     }

   bool     ValidateAcknowledgement(const string acknowledgedHash,
                                    const string expectedHash,
                                    const bool metadataValid,
                                    string &reason) const
     {
      return m_contract.CanActivate(acknowledgedHash, expectedHash, metadataValid, reason);
     }
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
   string approved;
   if(!ExtractJsonStringField(body, "approved_weight_version", approved))
      return;

   m_lastSeenApproved = approved;
   if(StringLen(approved) == 0) return;

   if(approved != m_compiledWeightVersion && !m_everWarned)
     {
      PrintFormat("MedisTouch ConfigSync: bridge reports '%s' as the latest approved weight_version, but this %s instance is compiled with InpWeightSetVersion='%s'. Recompile/redeploy this chart to match, or this instance keeps running its own weights — nothing is applied automatically.",
                  approved, m_symbol, m_compiledWeightVersion);
      m_everWarned = true;
     }
   else if(approved == m_compiledWeightVersion)
      m_everWarned = false;
  }

bool CConfigSync::ExtractJsonStringField(const string &json, string field, string &out)
  {
   string needle = "\"" + field + "\":";
   int pos = StringFind(json, needle);
   if(pos < 0) return false;
   int valueStart = pos + StringLen(needle);

   if(StringSubstr(json, valueStart, 4) == "null")
     {
      out = "";
      return true;
     }
   if(StringGetCharacter(json, valueStart) != '"') return false;
   valueStart++;
   int valueEnd = StringFind(json, "\"", valueStart);
   if(valueEnd < 0) return false;
   out = StringSubstr(json, valueStart, valueEnd - valueStart);
   return true;
  }

#endif // CONFIGSYNC_MQH
