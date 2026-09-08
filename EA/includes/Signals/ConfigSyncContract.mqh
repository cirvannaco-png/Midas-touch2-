//+------------------------------------------------------------------+
//| ConfigSyncContract.mqh                                           |
//| EA-side protocol boundary for immutable configuration delivery.   |
//| This class validates metadata and ACK state only. It deliberately  |
//| does not mutate any trading inputs or strategy objects.           |
//+------------------------------------------------------------------+
#ifndef CONFIGSYNC_CONTRACT_MQH
#define CONFIGSYNC_CONTRACT_MQH

#define CONFIG_SYNC_PROTOCOL_VERSION 1

class CConfigSyncContract
  {
private:
   string m_configHash;
   string m_strategy;
   string m_instrument;
   string m_timeframe;
   string m_dataVersion;
   string m_optimizerVersion;
   string m_lifecycle;
   int    m_version;

public:
   CConfigSyncContract(void)
     {
      Reset();
     }

   void Reset(void)
     {
      m_configHash = "";
      m_strategy = "";
      m_instrument = "";
      m_timeframe = "";
      m_dataVersion = "";
      m_optimizerVersion = "";
      m_lifecycle = "";
      m_version = 0;
     }

   void SetEnvelope(const string configHash,
                    const string strategy,
                    const string instrument,
                    const string timeframe,
                    const string dataVersion,
                    const string optimizerVersion,
                    const string lifecycle,
                    const int version)
     {
      m_configHash = configHash;
      m_strategy = strategy;
      m_instrument = instrument;
      m_timeframe = timeframe;
      m_dataVersion = dataVersion;
      m_optimizerVersion = optimizerVersion;
      m_lifecycle = lifecycle;
      m_version = version;
     }

   bool ValidateMetadata(const string expectedInstrument,
                         const string expectedTimeframe,
                         const string expectedStrategy,
                         string &reason) const
     {
      reason = "";
      if(m_version != CONFIG_SYNC_PROTOCOL_VERSION)
        {
         reason = "unsupported configuration protocol version";
         return false;
        }
      if(m_configHash == "")
        {
         reason = "configuration hash is missing";
         return false;
        }
      if(m_strategy != expectedStrategy)
        {
         reason = "strategy mismatch";
         return false;
        }
      if(m_instrument != expectedInstrument)
        {
         reason = "instrument mismatch";
         return false;
        }
      if(m_timeframe != expectedTimeframe)
        {
         reason = "timeframe mismatch";
         return false;
        }
      if(m_dataVersion == "")
        {
         reason = "data version is missing";
         return false;
        }
      if(m_optimizerVersion == "")
        {
         reason = "optimizer version is missing";
         return false;
        }
      // Evaluation states are not activation states. Only the bridge's
      // CHAMPION envelope may cross the exact-ACK activation boundary.
      if(m_lifecycle != "CHAMPION")
        {
         reason = "configuration lifecycle is not CHAMPION";
         return false;
        }
      return true;
     }

   bool CanActivate(const string acknowledgedHash,
                    const string expectedHash,
                    const bool metadataValid,
                    string &reason) const
     {
      reason = "";
      if(!metadataValid)
        {
         reason = "configuration metadata validation failed";
         return false;
        }
      if(m_configHash == "" || expectedHash == "")
        {
         reason = "configuration hash is missing";
         return false;
        }
      if(m_configHash != expectedHash)
        {
         reason = "configuration hash does not match expected identity";
         return false;
        }
      if(acknowledgedHash == "")
        {
         reason = "EA acknowledgement is missing";
         return false;
        }
      if(acknowledgedHash != expectedHash)
        {
         reason = "EA acknowledgement hash mismatch";
         return false;
        }
      return true;
     }

   string ConfigHash(void) const { return m_configHash; }
   string Lifecycle(void) const { return m_lifecycle; }
   int    Version(void) const { return m_version; }
  };

#endif // CONFIGSYNC_CONTRACT_MQH
//+------------------------------------------------------------------+
