//+------------------------------------------------------------------+
//| ProductionRuntimePreflight.mq5                                   |
//| Read-only MT5/VPS connectivity check for Midas Touch 2.           |
//| Does not submit, modify, or close any broker order.               |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs
#property description "Read-only runtime preflight; never sends trade orders."

input string InpBridgeBaseUrl = "https://midas-touch2.onrender.com";
input string InpBridgeApiKey = ""; // Enter locally; never print or share this value.
input ulong  InpMagicNumber = 987654321;
input int    InpTimeoutMs = 8000;

string EmergencyStopKeyForChart()
  {
   string key = "MIDAS_STOP_" + _Symbol + "_" + IntegerToString((long)InpMagicNumber);
   StringReplace(key, ".", "_");
   StringReplace(key, "#", "_");
   if(StringLen(key) > 63)
      key = StringSubstr(key, 0, 63);
   return key;
  }

void OnStart()
  {
   Print("=== MIDAS TOUCH 2 READ-ONLY RUNTIME PREFLIGHT ===");
   Print("No trade/order operation is performed by this script.");
   PrintFormat("symbol=%s timeframe=%s terminal_connected=%s terminal_algo_trading=%s",
               _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
               TerminalInfoInteger(TERMINAL_CONNECTED) ? "YES" : "NO",
               TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ? "YES" : "NO");

   ENUM_ACCOUNT_TRADE_MODE accountMode =
      (ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE);
   ENUM_ACCOUNT_MARGIN_MODE marginMode =
      (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   PrintFormat("account_trade_mode=%s margin_mode=%s account_trade_allowed=%s expert_trading_allowed=%s",
               EnumToString(accountMode), EnumToString(marginMode),
               AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) ? "YES" : "NO",
               AccountInfoInteger(ACCOUNT_TRADE_EXPERT) ? "YES" : "NO");

   string emergencyKey = EmergencyStopKeyForChart();
   bool emergencyLatched =
      GlobalVariableCheck(emergencyKey) && GlobalVariableGet(emergencyKey) > 0.5;
   PrintFormat("emergency_stop_latched=%s", emergencyLatched ? "YES" : "NO");

   int managedPositions = 0;
   for(int i = PositionsTotal() - 1; i >= 0; --i)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         managedPositions++;
     }

   int managedPendingOrders = 0;
   for(int i = OrdersTotal() - 1; i >= 0; --i)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0)
         continue;
      if(OrderGetString(ORDER_SYMBOL) == _Symbol &&
         (ulong)OrderGetInteger(ORDER_MAGIC) == InpMagicNumber)
         managedPendingOrders++;
     }
   PrintFormat("current_chart_symbol_magic_positions=%d pending_orders=%d",
               managedPositions, managedPendingOrders);

   string baseUrl = InpBridgeBaseUrl;
   while(StringLen(baseUrl) > 0 &&
         StringSubstr(baseUrl, StringLen(baseUrl) - 1, 1) == "/")
      baseUrl = StringSubstr(baseUrl, 0, StringLen(baseUrl) - 1);

   bool apiHealthy = false;
   if(StringFind(baseUrl, "https://") != 0 || StringLen(InpBridgeApiKey) == 0)
     {
      Print("LEDGER_API=FAIL: enter an HTTPS bridge base URL and the matching key locally.");
     }
   else
     {
      string headers = "X-API-Key: " + InpBridgeApiKey +
                       "\r\nAccept: application/json\r\n";
      char requestData[];
      ArrayResize(requestData, 0);
      char response[];
      string responseHeaders;
      ResetLastError();
      int httpStatus = WebRequest("GET",
                                  baseUrl + "/execution-ledger/health",
                                  headers,
                                  MathMax(1000, InpTimeoutMs),
                                  requestData,
                                  response,
                                  responseHeaders);
      if(httpStatus == -1)
        {
         int err = GetLastError();
         PrintFormat("LEDGER_API=FAIL: MT5 WebRequest transport failed (error=%d). Add https://midas-touch2.onrender.com to Tools > Options > Expert Advisors > Allow WebRequest, then retry.", err);
        }
      else
        {
         string body = CharArrayToString(response, 0, -1, CP_UTF8);
         bool hasOnline = (StringFind(body, "online") >= 0);
         bool hasConnected = (StringFind(body, "connected") >= 0);
         bool hasReady = (StringFind(body, "ready") >= 0);
         apiHealthy = (httpStatus == 200 && hasOnline && hasConnected && hasReady);
         if(apiHealthy)
            Print("LEDGER_API=PASS: authenticated request accepted; API reports online, database connected, execution ledger ready.");
         else if(httpStatus == 401 || httpStatus == 403)
            PrintFormat("LEDGER_API=FAIL: HTTP %d; key rejected. Compare this value with the bridge SECRET_KEY locally; do not print it.", httpStatus);
         else
            PrintFormat("LEDGER_API=FAIL: HTTP %d; expected HTTP 200 and online/connected/ready response. Response body intentionally not printed.", httpStatus);
        }
     }

   bool terminalReady = (bool)TerminalInfoInteger(TERMINAL_CONNECTED) &&
                        (bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) &&
                        (bool)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) &&
                        (bool)AccountInfoInteger(ACCOUNT_TRADE_EXPERT);
   bool preflightPass = terminalReady && apiHealthy && !emergencyLatched;
   PrintFormat("PREFLIGHT=%s", preflightPass ? "PASS_CONNECTIVITY_ONLY" : "FAIL");
   Print("IMPORTANT: PASS only proves terminal trade permission plus an authenticated API/database health response.");
   Print("It does NOT prove that the running EA inputs match these script inputs or that broker positions/pending orders were reconciled.");
   Print("After restarting the EA, verify Experts log contains EXECUTION_LEDGER_READY and no EXECUTION_LEDGER_NOT_READY / EXECUTION_LEDGER_CONFIGURATION_MISSING.");
   Print("Verify the running EA Inputs locally: InpExecutionLedgerBaseUrl=https://midas-touch2.onrender.com; InpBridgeApiKey matches bridge SECRET_KEY; InpRequireExecutionLedger=true.");
   Print("Do not enable live trading on this result alone; complete the selected-broker Strategy Tester and demo-forward gates.");
  }
//+------------------------------------------------------------------+
