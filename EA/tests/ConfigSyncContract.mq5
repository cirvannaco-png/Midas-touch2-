//+------------------------------------------------------------------+
//| ConfigSyncContract.mq5                                            |
//| Lightweight compile-time/runtime assertions for the EA contract.  |
//| No orders are sent and no trading inputs are changed.              |
//+------------------------------------------------------------------+
#property strict

#include "../includes/Signals/ConfigSyncContract.mqh"

bool Expect(const bool condition, const string label)
  {
   if(!condition)
     {
      PrintFormat("ConfigSyncContract TEST FAILED: %s", label);
      return false;
     }
   return true;
  }

void OnStart()
  {
   CConfigSyncContract contract;
   string reason;
   bool ok = true;

   contract.SetEnvelope("hash-a", "SMC", "XAUUSD", "M15",
                        "data-1", "optimizer-1", "CHALLENGER", 1);
   ok &= Expect(contract.ValidateMetadata("XAUUSD", "M15", "SMC", reason),
                "matching metadata must validate");
   ok &= Expect(!contract.ValidateMetadata("EURUSD", "M15", "SMC", reason),
                "instrument mismatch must reject");
   ok &= Expect(!contract.CanActivate("", "hash-a", true, reason),
                "missing acknowledgement must hold");
   ok &= Expect(!contract.CanActivate("wrong", "hash-a", true, reason),
                "wrong acknowledgement must hold");
   ok &= Expect(contract.CanActivate("hash-a", "hash-a", true, reason),
                "exact acknowledgement must activate");

   contract.SetEnvelope("hash-b", "SMC", "XAUUSD", "M15",
                        "data-1", "optimizer-1", "OPTIMIZED", 1);
   ok &= Expect(!contract.ValidateMetadata("XAUUSD", "M15", "SMC", reason),
                "non-deployable lifecycle must reject");

   Print(ok ? "ConfigSyncContract TEST PASS" : "ConfigSyncContract TEST FAIL");
  }
