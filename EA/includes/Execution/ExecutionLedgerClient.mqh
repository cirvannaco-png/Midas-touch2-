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

      uchar rawData[];
      int len=StringToCharArray(payload,rawData)-1;
      if(len<0) len=0;
      ArrayResize(rawData,len);
      char data[];
      ArrayResize(data,len);
      ArrayCopy(data,rawData);

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
      if(StringLen(m_portfolioKey)>128)
        {
         Print("Midas execution ledger: generated portfolio key exceeds API limit.");
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
      string payload=StringFormat(
         "{\"portfolio_key\":\"%s\",\"request_id\":\"%s\",\"broker_position_id\":\"%I64u\",\"broker_order_id\":\"%I64u\",\"broker_deal_id\":\"%I64u\",\"symbol\":\"%s\",\"direction\":\"%s\",\"risk_r\":%.8f,\"volatility\":%.8f,\"factors\":{},\"evidence_ref\":\"%s\"}",
         JsonSafe(m_portfolioKey),JsonSafe(requestId),positionIdentifier,orderId,dealId,
         JsonSafe(symbol),JsonSafe(direction),riskR,MathMax(0.0,volatility),JsonSafe(evidenceRef));
      return PostJson("/execution-ledger/sync-position",payload);
     }

   bool SyncPendingOrder(const ulong orderTicket,const string symbol,const string direction,
                         const double riskR,const double volatility,const string evidenceRef)
     {
      if(!m_ready || orderTicket==0 || riskR<=0.0 || !MathIsValidNumber(riskR)) return false;
      string requestId=RequestIdForPendingOrder(orderTicket);
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

   bool ClosePosition(const ulong positionIdentifier,const ulong closingDealId,const string evidenceRef)
     {
      if(!m_ready || positionIdentifier==0 || closingDealId==0) return false;
      string payload=StringFormat(
         "{\"portfolio_key\":\"%s\",\"broker_position_id\":\"%I64u\",\"broker_deal_id\":\"%I64u\",\"evidence_ref\":\"%s\"}",
         JsonSafe(m_portfolioKey),positionIdentifier,closingDealId,JsonSafe(evidenceRef));
      return PostJson("/execution-ledger/position-closed",payload);
     }


   bool SyncClosedPosition(const ulong positionIdentifier,const ulong closingDealId,const string evidenceRef)
     {
      if(!m_ready || positionIdentifier==0 || closingDealId==0) return false;
      string payload=StringFormat(
         "{\"portfolio_key\":\"%s\",\"broker_position_id\":\"%I64u\",\"broker_deal_id\":\"%I64u\",\"evidence_ref\":\"%s\"}",
         JsonSafe(m_portfolioKey),positionIdentifier,closingDealId,JsonSafe(evidenceRef));
      return PostJson("/execution-ledger/sync-closed-position",payload);
     }

   bool RecoverExpired()
     {
      return PostJson("/execution-ledger/recover-expired","{}");
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
