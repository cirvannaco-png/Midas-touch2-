//+------------------------------------------------------------------+
//| TradeSetup.mqh                                                    |
//| Canonical TradeSetup contract - handbook section 3, verbatim.     |
//|                                                                    |
//| Mirrors app/models.py's TradeSetup field-for-field so the EA side |
//| and the Python/backend side agree on the same shape when signals  |
//| cross the WebRequest boundary (EA -> telegram-bridge /signal).    |
//|                                                                    |
//| CORE INVARIANT: invalidation and stop_loss are separate fields.   |
//| invalidation = where the THESIS is wrong (strategy-owned).        |
//| stop_loss    = the actual protective order sent to the broker.    |
//| Example from the handbook: entry 3350, invalidation 3347, SL 3346.|
//| Do not collapse these into one value anywhere in the setup        |
//| engines - that was the specific bug the handbook calls out.       |
//+------------------------------------------------------------------+
#property strict

struct SetupReasons
  {
   string            items[];

   void              Add(const string reason)
     {
      int n = ArraySize(items);
      ArrayResize(items, n + 1);
      items[n] = reason;
     }
  };

struct TradeSetup
  {
   ENUM_ORDER_TYPE   type;
   double            entry_top;
   double            entry_bottom;

   // Strategy thesis boundary - where the IDEA is wrong.
   double            invalidation;

   // Actual executable protective order - where the ORDER exits.
   double            stop_loss;

   double            tp1;
   double            tp2;
   double            final_tp;

   double            confidence;

   datetime          creation_time;
   datetime          expiry_time;
   bool              active;

   SetupReasons      reasons;
   double            calibrated_probability;
   int               calibration_sample;
  };

//+------------------------------------------------------------------+
//| Cheap sanity checks - NOT a substitute for the fail-closed        |
//| execution validation (broker/symbol metadata) that must happen    |
//| separately, immediately before order submission. This only        |
//| catches internally-inconsistent setups before they're even sent.  |
//|                                                                    |
//| v2.18: invalidation and target geometry is now checked here too.  |
//| The old helper only checked stop_loss, which meant a malformed     |
//| thesis boundary or inverted target ladder could cross the wire.    |
//| No strategy logic is created here; this is pure contract safety.   |
//+------------------------------------------------------------------+
bool ValidateTradeSetupShape(const TradeSetup &setup, string &error_out)
  {
   error_out = "";

   if(setup.type != ORDER_TYPE_BUY && setup.type != ORDER_TYPE_SELL)
     {
      error_out = "TradeSetup type is not BUY or SELL";
      return false;
     }

   if(setup.entry_top < setup.entry_bottom)
     {
      error_out = "entry_top must be >= entry_bottom";
      return false;
     }

   // A non-finite value must never reach WebRequest/order submission.
   if(!MathIsValidNumber(setup.entry_top) || !MathIsValidNumber(setup.entry_bottom) ||
      !MathIsValidNumber(setup.invalidation) || !MathIsValidNumber(setup.stop_loss) ||
      !MathIsValidNumber(setup.tp1) || !MathIsValidNumber(setup.tp2) ||
      !MathIsValidNumber(setup.final_tp) || !MathIsValidNumber(setup.confidence))
     {
      error_out = "TradeSetup contains a non-finite value";
      return false;
     }

   if(setup.confidence < 0.0 || setup.confidence > 100.0)
     {
      error_out = "confidence must be in the canonical 0..100 range";
      return false;
     }

   if(setup.type == ORDER_TYPE_BUY)
     {
      if(setup.stop_loss >= setup.entry_bottom)
        {
         error_out = "BUY stop_loss must be below entry range";
         return false;
        }
      if(setup.invalidation >= setup.entry_bottom)
        {
         error_out = "BUY invalidation must be below entry range";
         return false;
        }
      if(setup.tp1 <= setup.entry_top || setup.tp2 <= setup.tp1 || setup.final_tp <= setup.tp2)
        {
         error_out = "BUY targets must increase: TP1 < TP2 < final TP";
         return false;
        }
     }
   else
     {
      if(setup.stop_loss <= setup.entry_top)
        {
         error_out = "SELL stop_loss must be above entry range";
         return false;
        }
      if(setup.invalidation <= setup.entry_top)
        {
         error_out = "SELL invalidation must be above entry range";
         return false;
        }
      if(setup.tp1 >= setup.entry_bottom || setup.tp2 >= setup.tp1 || setup.final_tp >= setup.tp2)
        {
         error_out = "SELL targets must decrease: TP1 > TP2 > final TP";
         return false;
        }
     }

   return true;
  }

//+------------------------------------------------------------------+
//| Serializes to the JSON body telegram-bridge's POST /signal        |
//| endpoint expects (per its README's documented payload shape).     |
//| Keep this in sync BY HAND with app/models.py and the bridge's     |
//| validator.py - there is no shared schema file across MQL5/Python  |
//| in this repo layout, so a field added on one side silently does   |
//| nothing on the other until both are updated.                      |
//+------------------------------------------------------------------+
string TradeSetupToSignalJson(const string signal_id, const string symbol,
                               const string timeframe, const TradeSetup &setup)
  {
   string reasons_json = "[";
   for(int i = 0; i < ArraySize(setup.reasons.items); i++)
     {
      if(i > 0)
         reasons_json += ",";
      string reason = setup.reasons.items[i];
      StringReplace(reason, "\"", "'");
      reasons_json += "\"" + reason + "\"";
     }
   reasons_json += "]";

   string direction = (setup.type == ORDER_TYPE_BUY) ? "BUY" : "SELL";
   string json = "{";
   json += "\"signal_id\":\"" + signal_id + "\",";
   json += "\"symbol\":\"" + symbol + "\",";
   json += "\"direction\":\"" + direction + "\",";
   json += "\"entry\":" + DoubleToString(setup.entry_bottom, 5) + ",";
   // CORE INVARIANT, preserved across the wire: invalidation (thesis
   // boundary) and sl (protective order) are separate fields here too.
   json += "\"invalidation\":" + DoubleToString(setup.invalidation, 5) + ",";
   json += "\"sl\":" + DoubleToString(setup.stop_loss, 5) + ",";
   json += "\"tp1\":" + DoubleToString(setup.tp1, 5) + ",";
   json += "\"tp2\":" + DoubleToString(setup.tp2, 5) + ",";
   json += "\"final_tp\":" + DoubleToString(setup.final_tp, 5) + ",";
   json += "\"confidence\":" + DoubleToString(setup.confidence, 1) + ",";
   json += "\"reasons\":" + reasons_json + ",";
   json += "\"timeframe\":\"" + timeframe + "\"";
   json += "}";
   // REQUIRED on the receiving end: telegram-bridge/app/models.py and
   // validator.py must accept `invalidation` and `final_tp` as fields
   // distinct from `sl`/`tp2`, or this fix is a no-op — the bridge will
   // just ignore the new keys. Update both sides together.
   return json;
  }
