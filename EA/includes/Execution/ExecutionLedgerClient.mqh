//+------------------------------------------------------------------+
//| Execution/ExecutionLedgerClient.mqh                              |
//| Fail-closed HTTP client for bridge-side durable execution state. |
//+------------------------------------------------------------------+
#ifndef MIDAS_EXECUTIONLEDGERCLIENT_MQH
#define MIDAS_EXECUTIONLEDGERCLIENT_MQH

class CExecutionLedgerClient
  {
private:
   string m_baseUrl;
   string m_apiKey;
   string m_portfolioKey;
   int    m_timeoutMs;
   bool   m_ready;

   string JsonSafe(string value)
     {
      // Keep identifiers JSON-safe. Server names/symbols should not contain
      // these characters, but sanitizing them prevents malformed request JSON.
      StringReplace(value,"\\","/");
      StringReplace(value,"\"","'");
      StringReplace(value,"\r"," ");
      StringReplace(value,"\n"," ");
      return value;
     }

   bool PostJson(const string path,const string &payload)
     {
      if(!m_ready) return false;

      char data[];
      int len=StringToCharArray(payload,data,0,WHOLE_ARRAY,CP_UTF8);
      if(len>0)
         ArrayResize(data,len-1); // remove the terminal NUL; HTTP body is UTF-8 JSON
      else
         ArrayResize(data,0);

      char result[];
      string resultHeaders;
      string headers="Content-Type: application/json\r\nX-API-Key: "+m_apiKey+"\r\n";
      ResetLastError();
      int status=WebRequest("POST",m_baseUrl+path,headers,m_timeoutMs,data,result,resultHeaders);
      if(status==-1)
        {
         PrintFormat("Midas execution ledger: POST %s failed at transport layer (error=%d); do not assume broker outcome.",path,GetLastError());
         return false;
        }
      if(status<200 || status>=300)
        {
         PrintFormat("Midas execution ledger: POST %s returned HTTP %d; response=%s",path,status,CharArrayToString(result));
         return false;
        }
      return true;
     }

public:
   void Init(const string baseUrl,const string apiKey,const ulong magicNumber,int timeoutMs=5000)
     {
      m_baseUrl=baseUrl;
      while(StringLen(m_baseUrl)>0 && StringSubstr(m_baseUrl,StringLen(m_baseUrl)-1,1)=="/")
         m_baseUrl=StringSubstr(m_baseUrl,0,StringLen(m_baseUrl)-1);
      m_apiKey=apiKey;
      m_timeoutMs=MathMax(1000,timeoutMs);
      m_portfolioKey="";
      m_ready=false;

      if(StringLen(m_baseUrl)<8 || StringLen(m_apiKey)==0)
        {
         Print("Midas execution ledger: base URL/API key missing; remote execution ledger is not ready.");
         return;
        }

      string server=JsonSafe(AccountInfoString(ACCOUNT_SERVER));
      string login=IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN));
      string magicText=IntegerToString((long)magicNumber);
      // Account + broker server + strategy magic defines an isolated risk book.
      m_portfolioKey=server+":"+login+":"+magicText;
      if(StringLen(m_portfolioKey)>80)
        {
         Print("Midas execution ledger: portfolio key exceeds safe request-ID budget.");
         m_portfolioKey="";
         return;
        }
      m_ready=true;
     }

   bool Ready() const { return m_ready; }
   string PortfolioKey() const { return m_portfolioKey; }

   string RequestIdForDecision(const long decisionId,const int legIndex)
     {
      return m_portfolioKey+":decision:"+IntegerToString(decisionId)+":leg:"+IntegerToString(legIndex);
     }

   string RequestIdForPosition(const ulong positionIdentifier)
     {
      return "position:"+m_portfolioKey+":"+IntegerToString((long)positionIdentifier);
     }

   string RequestIdForPendingOrder(const ulong orderTicket)
     {
      return "pending:"+m_portfolioKey+":"+IntegerToString((long)orderTicket);
     }

   bool Reserve(const long decisionId,const int legIndex,const string signalId,
                const string symbol,const string direction,const double riskR,
                const double volatility,string &requestId)
     {
      requestId=RequestIdForDecision(decisionId,legIndex);
      if(!m_ready || StringLen(requestId)>128 || riskR<=0.0 ||
         !MathIsValidNumber(riskR) || volatility<0.0 || !MathIsValidNumber(volatility))
         return false;
      string payload=StringFormat(
         "{\"portfolio_key\":\"%s\",\"request_id\":\"%s\",\"signal_id\":\"%s\",\"symbol\":\"%s\",\"direction\":\"%s\",\"risk_r\":%.8f,\"volatility\":%.8f,\"factors\":{},\"max_heat_r\":3.0}",
         JsonSafe(m_portfolioKey),JsonSafe(requestId),JsonSafe(signalId),
         JsonSafe(symbol),JsonSafe(direction),riskR,volatility);
      return PostJson("/execution-ledger/reserve",payload);
     }

   bool Transition(const string requestId,const string state,const string resultJson="{}")
     {
      if(!m_ready || StringLen(requestId)==0 || StringLen(resultJson)==0) return false;
      string payload=StringFormat("{\"request_id\":\"%s\",\"state\":\"%s\",\"result\":%s}",
                                  JsonSafe(requestId),JsonSafe(state),resultJson);
      return PostJson("/execution-ledger/transition",payload);
     }

   bool SyncPosition(const ulong positionIdentifier,const ulong orderId,const ulong dealId,
                     const string symbol,const string direction,const double riskR,
                     const double volatility,const string evidenceRef,
                     const string requestIdOverride="")
     {
      if(!m_ready || positionIdentifier==0 || riskR<=0.0 || !MathIsValidNumber(riskR)) return false;
      string requestId=requestIdOverride;
      if(StringLen(requestId)==0) requestId=RequestIdForPosition(positionIdentifier);
      string orderIdJson=(orderId>0)?StringFormat("\"%I64u\"",orderId):"null";
      string dealIdJson=(dealId>0)?StringFormat("\"%I64u\"",dealId):"null";
      string payload=StringFormat(
         "{\"portfolio_key\":\"%s\",\"request_id\":\"%s\",\"broker_position_id\":\"%I64u\",\"broker_order_id\":%s,\"broker_deal_id\":%s,\"symbol\":\"%s\",\"direction\":\"%s\",\"risk_r\":%.8f,\"volatility\":%.8f,\"factors\":{},\"evidence_ref\":\"%s\"}",
         JsonSafe(m_portfolioKey),JsonSafe(requestId),positionIdentifier,orderIdJson,dealIdJson,
         JsonSafe(symbol),JsonSafe(direction),riskR,MathMax(0.0,volatility),JsonSafe(evidenceRef));
      return PostJson("/execution-ledger/sync-position",payload);
     }

   bool SyncPendingOrder(const ulong orderTicket,const string symbol,const string direction,
                         const double riskR,const double volatility,const string evidenceRef,
                         const string requestIdOverride="")
     {
      if(!m_ready || orderTicket==0 || riskR<=0.0 || !MathIsValidNumber(riskR)) return false;
      string requestId=requestIdOverride;
      if(StringLen(requestId)==0) requestId=RequestIdForPendingOrder(orderTicket);
      string payload=StringFormat(
         "{\"portfolio_key\":\"%s\",\"request_id\":\"%s\",\"broker_order_id\":\"%I64u\",\"symbol\":\"%s\",\"direction\":\"%s\",\"risk_r\":%.8f,\"volatility\":%.8f,\"factors\":{},\"evidence_ref\":\"%s\"}",
         JsonSafe(m_portfolioKey),JsonSafe(requestId),orderTicket,
         JsonSafe(symbol),JsonSafe(direction),riskR,MathMax(0.0,volatility),JsonSafe(evidenceRef));
      return PostJson("/execution-ledger/sync-pending-order",payload);
     }

   bool UpdatePositionRisk(const ulong positionIdentifier,const string direction,
                           const double riskR,const double volatility,const string evidenceRef)
     {
      if(!m_ready || positionIdentifier==0 || riskR<=0.0 || !MathIsValidNumber(riskR)) return false;
      string payload=StringFormat(
         "{\"portfolio_key\":\"%s\",\"broker_position_id\":\"%I64u\",\"direction\":\"%s\",\"risk_r\":%.8f,\"volatility\":%.8f,\"factors\":{},\"evidence_ref\":\"%s\"}",
         JsonSafe(m_portfolioKey),positionIdentifier,JsonSafe(direction),riskR,
         MathMax(0.0,volatility),JsonSafe(evidenceRef));
      return PostJson("/execution-ledger/position-risk",payload);
     }

   bool ClosePosition(const ulong positionIdentifier,const ulong closingDealId,const string evidenceRef,
                      const string requestIdOverride="")
     {
      if(!m_ready || positionIdentifier==0 || closingDealId==0) return false;
      string payload=StringFormat(
         "{\"portfolio_key\":\"%s\",\"request_id\":\"%s\",\"broker_position_id\":\"%I64u\",\"broker_deal_id\":\"%I64u\",\"evidence_ref\":\"%s\"}",
         JsonSafe(m_portfolioKey),JsonSafe(requestIdOverride),positionIdentifier,closingDealId,JsonSafe(evidenceRef));
      return PostJson("/execution-ledger/position-closed",payload);
     }


   bool SyncClosedPosition(const ulong positionIdentifier,const ulong closingDealId,const string evidenceRef,
                           const string requestIdOverride="")
     {
      if(!m_ready || positionIdentifier==0 || closingDealId==0) return false;
      string payload=StringFormat(
         "{\"portfolio_key\":\"%s\",\"request_id\":\"%s\",\"broker_position_id\":\"%I64u\",\"broker_deal_id\":\"%I64u\",\"evidence_ref\":\"%s\"}",
         JsonSafe(m_portfolioKey),JsonSafe(requestIdOverride),positionIdentifier,closingDealId,JsonSafe(evidenceRef));
      return PostJson("/execution-ledger/sync-closed-position",payload);
     }

   bool RecoverExpired()
     {
      return PostJson("/execution-ledger/recover-expired","{}");
     }


   bool DealEvent(const string requestId,const ulong dealId,const ulong orderId,
                  const ulong positionIdentifier,const string symbol,const string entryType,
                  const string dealType,const string positionDirection,const double volume,
                  const double price,const double profitCashflow,const double commissionCashflow,
                  const double swapCashflow,const double feeCashflow,const bool cashflowsKnown,
                  const bool positionOpen,const double remainingVolume,const double riskR,
                  const double volatility,const string evidenceRef)
     {
      if(!m_ready || StringLen(requestId)==0 || StringLen(requestId)>128 ||
         dealId==0 || positionIdentifier==0 || volume<=0.0 || price<=0.0 ||
         !MathIsValidNumber(volume) || !MathIsValidNumber(price) ||
         !MathIsValidNumber(profitCashflow) || !MathIsValidNumber(commissionCashflow) ||
         !MathIsValidNumber(swapCashflow) || !MathIsValidNumber(feeCashflow) ||
         !MathIsValidNumber(remainingVolume) || !MathIsValidNumber(riskR) ||
         !MathIsValidNumber(volatility) || remainingVolume<0.0 || riskR<0.0 || volatility<0.0)
         return false;
      if(positionOpen && (remainingVolume<=0.0 || riskR<=0.0)) return false;
      string payload=StringFormat(
         "{\\"portfolio_key\\":\\"%s\\",\\"request_id\\":\\"%s\\",\\"broker_deal_id\\":\\"%I64u\\",\\"broker_order_id\\":\\"%I64u\\",\\"broker_position_id\\":\\"%I64u\\",\\"symbol\\":\\"%s\\",\\"entry_type\\":\\"%s\\",\\"deal_type\\":\\"%s\\",\\"direction\\":\\"%s\\",\\"volume\\":%.8f,\\"price\\":%.8f,\\"profit_cashflow\\":%.8f,\\"commission_cashflow\\":%.8f,\\"swap_cashflow\\":%.8f,\\"fee_cashflow\\":%.8f,\\"cashflows_known\\":%s,\\"position_open\\":%s,\\"remaining_volume\\":%.8f,\\"risk_r\\":%.8f,\\"volatility\\":%.8f,\\"factors\\":{},\\"evidence_ref\\":\\"%s\\"}",
         JsonSafe(m_portfolioKey),JsonSafe(requestId),dealId,orderId,positionIdentifier,
         JsonSafe(symbol),JsonSafe(entryType),JsonSafe(dealType),JsonSafe(positionDirection),
         volume,price,profitCashflow,commissionCashflow,swapCashflow,feeCashflow,
         cashflowsKnown?"true":"false",positionOpen?"true":"false",remainingVolume,
         riskR,volatility,JsonSafe(evidenceRef));
      return PostJson("/execution-ledger/deal-event",payload);
     }

   bool TerminalOrder(const ulong orderTicket,const string state,const string evidenceRef)
     {
      if(!m_ready || orderTicket==0 || (state!="CANCELLED" && state!="REJECTED")) return false;
      string payload=StringFormat(
         "{\"portfolio_key\":\"%s\",\"broker_order_id\":\"%I64u\",\"terminal_state\":\"%s\",\"evidence_ref\":\"%s\"}",
         JsonSafe(m_portfolioKey),orderTicket,JsonSafe(state),JsonSafe(evidenceRef));
      return PostJson("/execution-ledger/order-terminal",payload);
     }
  };

#endif
//+------------------------------------------------------------------+
