//+------------------------------------------------------------------+
//|                                       Execution/BrokerAdapter.mqh |
//+------------------------------------------------------------------+
#ifndef BROKERADAPTER_MQH
#define BROKERADAPTER_MQH

#include <Trade\Trade.mqh>

class CBrokerAdapter
  {
private:
   CTrade            m_trade;
   ulong             m_magic;
   int               m_maxRetries;
   int               m_retryDelayMs;
   ulong             m_lastLatencyUs;
   ulong             m_lastBrokerOrderId;
   ulong             m_lastBrokerDealId;
   ulong             m_lastBrokerPositionId;
   bool              m_lastRequestAttempted;
   uint              m_lastRetcode;

   void              CaptureBrokerIdentifiers(string symbol);
   bool              LastRequestOk(string action);
   bool              LastExecutionCompleted(string action,bool allowPartial=false,bool allowNoChanges=false);
   ulong             ResolvePositionTicket(string symbol);
   bool              IsRetryable(uint retcode);
   int               DelayForRetcode(uint retcode);
   bool              IsConnected();
   bool              IsMarketOpenForTrading(string symbol, bool requireFullOpen, bool isBuy=true);
   bool              ValidateStopDistance(string symbol, double refPrice, double sl, double tp, bool isBuy, string action);

public:
   void              Init(ulong magic, int maxRetries = 3, int retryDelayMs = 300);
   double            LastLatencyMs() { return (double)m_lastLatencyUs / 1000.0; }
   ulong             LastBrokerOrderId() const { return m_lastBrokerOrderId; }
   ulong             LastBrokerDealId() const { return m_lastBrokerDealId; }
   ulong             LastBrokerPositionId() const { return m_lastBrokerPositionId; }
   bool              LastRequestAttempted() const { return m_lastRequestAttempted; }
   uint              LastRetcode() const { return m_lastRetcode; }
   bool              LastRequestAmbiguous() const
     {
      return m_lastRequestAttempted &&
             (m_lastRetcode==TRADE_RETCODE_TIMEOUT ||
              m_lastRetcode==TRADE_RETCODE_CONNECTION ||
              m_lastRetcode==TRADE_RETCODE_ERROR);
     }
   void              ResetLastRequestStatus()
     {
      m_lastRequestAttempted=false;
      m_lastRetcode=0;
      m_lastBrokerOrderId=0;
      m_lastBrokerDealId=0;
      m_lastBrokerPositionId=0;
     }
   bool              MarketBuy(string symbol, double volume, double sl, double tp, ulong &ticketOut, double &fillPriceOut, string comment = "");
   bool              MarketSell(string symbol, double volume, double sl, double tp, ulong &ticketOut, double &fillPriceOut, string comment = "");
   bool              PlaceLimit(string symbol, ENUM_ORDER_TYPE type, double volume, double price,
                                double sl, double tp, ulong &ticketOut, string comment = "");
   bool              CancelOrder(ulong ticket);
   bool              ModifySLTP(ulong ticket, double sl, double tp);
   bool              ClosePartial(ulong ticket, double volume);
   bool              CloseFull(ulong ticket);
   ulong             PositionTicketForIdentifier(string symbol, ulong positionIdentifier);
  };
//+------------------------------------------------------------------+
void CBrokerAdapter::Init(ulong magic, int maxRetries, int retryDelayMs)
  {
   m_magic = magic;
   m_trade.SetExpertMagicNumber(magic);
   m_trade.SetDeviationInPoints(20);
   m_trade.SetTypeFillingBySymbol(_Symbol);
   m_maxRetries = MathMax(1,maxRetries);
   m_retryDelayMs = MathMax(0,retryDelayMs);
   m_lastLatencyUs = 0;
   m_lastBrokerOrderId = 0;
   m_lastBrokerDealId = 0;
   m_lastBrokerPositionId = 0;
   m_lastRequestAttempted = false;
   m_lastRetcode = 0;
  }
//+------------------------------------------------------------------+
void CBrokerAdapter::CaptureBrokerIdentifiers(string symbol)
  {
   m_lastBrokerOrderId=(ulong)m_trade.ResultOrder();
   m_lastBrokerDealId=(ulong)m_trade.ResultDeal();
   m_lastBrokerPositionId=0;
   if(m_lastBrokerDealId>0 && HistoryDealSelect(m_lastBrokerDealId))
      m_lastBrokerPositionId=(ulong)HistoryDealGetInteger(m_lastBrokerDealId,DEAL_POSITION_ID);
   // For accepted pending orders the order ID is the durable broker reference;
   // for market fills the position ID comes from the actual deal history.
   if(m_lastBrokerPositionId==0 && m_lastBrokerDealId>0)
      PrintFormat("MidasTouch BrokerAdapter: deal #%I64u accepted but stable position identity is not yet observable for %s; reconciliation remains required.",
                  m_lastBrokerDealId,symbol);
  }
//+------------------------------------------------------------------+
// Retry only broker outcomes that are explicitly transient. Unknown,
// ambiguous, or permanent outcomes fail closed to prevent duplicate exposure.
bool CBrokerAdapter::IsRetryable(uint retcode)
  {
   // Retry only explicit price responses that guarantee the trade was not
   // executed. TIMEOUT, CONNECTION and generic ERROR remain ambiguous.
   switch(retcode)
     {
      case TRADE_RETCODE_REQUOTE:
      case TRADE_RETCODE_PRICE_CHANGED:
      case TRADE_RETCODE_PRICE_OFF:
         return true;
      default:
         return false;
     }
  }
//+------------------------------------------------------------------+
int CBrokerAdapter::DelayForRetcode(uint retcode)
  {
   switch(retcode)
     {
      case TRADE_RETCODE_REQUOTE:
      case TRADE_RETCODE_PRICE_CHANGED:
      case TRADE_RETCODE_PRICE_OFF:
         return MathMin(m_retryDelayMs,50);
      default:
         return m_retryDelayMs;
     }
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::IsConnected()
  {
   if(TerminalInfoInteger(TERMINAL_CONNECTED)) return true;
   Print("MedisTouch BrokerAdapter: terminal not connected to the trade server — refusing to submit.");
   return false;
  }
//+------------------------------------------------------------------+
// requireFullOpen=true is used for new exposure. In addition to disabled
// and close-only, enforce the broker's directional-only modes. This avoids
// sending a known-doomed BUY to a SHORTONLY symbol (or vice versa).
bool CBrokerAdapter::IsMarketOpenForTrading(string symbol, bool requireFullOpen, bool isBuy)
  {
   long mode=(long)SymbolInfoInteger(symbol,SYMBOL_TRADE_MODE);
   if(mode==SYMBOL_TRADE_MODE_DISABLED)
     {
      PrintFormat("MedisTouch BrokerAdapter: %s trading is disabled — refusing.",symbol);
      return false;
     }
   if(requireFullOpen && mode==SYMBOL_TRADE_MODE_CLOSEONLY)
     {
      PrintFormat("MedisTouch BrokerAdapter: %s is close-only — refusing new exposure.",symbol);
      return false;
     }
   if(requireFullOpen && mode==SYMBOL_TRADE_MODE_LONGONLY && !isBuy)
     {
      PrintFormat("MedisTouch BrokerAdapter: %s is LONGONLY — refusing SELL.",symbol);
      return false;
     }
   if(requireFullOpen && mode==SYMBOL_TRADE_MODE_SHORTONLY && isBuy)
     {
      PrintFormat("MedisTouch BrokerAdapter: %s is SHORTONLY — refusing BUY.",symbol);
      return false;
     }
   return true;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::ValidateStopDistance(string symbol, double refPrice, double sl, double tp, bool isBuy, string action)
  {
   if(refPrice<=0.0)
     {
      PrintFormat("MedisTouch BrokerAdapter: %s refused — invalid reference price %.5f.",action,refPrice);
      return false;
     }
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
   if(point<=0.0) return false;

   long stopsLevelPts=SymbolInfoInteger(symbol,SYMBOL_TRADE_STOPS_LEVEL);
   long freezeLevelPts=SymbolInfoInteger(symbol,SYMBOL_TRADE_FREEZE_LEVEL);
   double minDist=MathMax(stopsLevelPts,freezeLevelPts)*point;

   if(sl>0.0)
     {
      bool wrongSide=isBuy ? (sl>=refPrice) : (sl<=refPrice);
      if(wrongSide)
        {
         PrintFormat("MedisTouch BrokerAdapter: %s refused — SL %.5f is on the wrong side of reference %.5f.",action,sl,refPrice);
         return false;
        }
      if(minDist>0.0 && MathAbs(refPrice-sl)<minDist)
        {
         PrintFormat("MedisTouch BrokerAdapter: %s refused — SL %.5f is too close to %.5f (requires >= %.1f points).",action,sl,refPrice,minDist/point);
         return false;
        }
     }
   if(tp>0.0)
     {
      bool wrongSide=isBuy ? (tp<=refPrice) : (tp>=refPrice);
      if(wrongSide)
        {
         PrintFormat("MedisTouch BrokerAdapter: %s refused — TP %.5f is on the wrong side of reference %.5f.",action,tp,refPrice);
         return false;
        }
      if(minDist>0.0 && MathAbs(refPrice-tp)<minDist)
        {
         PrintFormat("MedisTouch BrokerAdapter: %s refused — TP %.5f is too close to %.5f (requires >= %.1f points).",action,tp,refPrice,minDist/point);
         return false;
        }
     }
   return true;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::LastRequestOk(string action)
  {
   uint code=m_trade.ResultRetcode();
   if(code==TRADE_RETCODE_DONE || code==TRADE_RETCODE_PLACED || code==TRADE_RETCODE_DONE_PARTIAL) return true;
   PrintFormat("MedisTouch BrokerAdapter: %s failed, retcode=%d (%s)",action,code,m_trade.ResultRetcodeDescription());
   return false;
  }
//+------------------------------------------------------------------+
// Order/position helpers return true only when the trade server confirms
// the requested terminal state. CTrade's bool alone only checks request structure.
bool CBrokerAdapter::LastExecutionCompleted(string action,bool allowPartial,bool allowNoChanges)
  {
   uint code=m_trade.ResultRetcode();
   bool completed=(code==TRADE_RETCODE_DONE ||
                   (allowPartial && code==TRADE_RETCODE_DONE_PARTIAL) ||
                   (allowNoChanges && code==TRADE_RETCODE_NO_CHANGES));
   if(!completed)
      PrintFormat("MedisTouch BrokerAdapter: %s not confirmed, retcode=%d (%s)",
                  action,code,m_trade.ResultRetcodeDescription());
   return completed;
  }
//+------------------------------------------------------------------+
// Resolve the terminal's current position ticket from the stable history identifier.
// POSITION_IDENTIFIER is a ledger identity, not the argument to PositionSelectByTicket.
ulong CBrokerAdapter::PositionTicketForIdentifier(string symbol,ulong positionIdentifier)
  {
   if(positionIdentifier==0) return 0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)!=symbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=m_magic) continue;
      if((ulong)PositionGetInteger(POSITION_IDENTIFIER)==positionIdentifier)
         return ticket;
     }
   return 0;
  }
//+------------------------------------------------------------------+
ulong CBrokerAdapter::ResolvePositionTicket(string symbol)
  {
   ulong dealTicket=m_trade.ResultDeal();
   ulong positionIdentifier=0;
   if(dealTicket>0 && HistoryDealSelect(dealTicket))
      positionIdentifier=(ulong)HistoryDealGetInteger(dealTicket,DEAL_POSITION_ID);

   if(positionIdentifier>0)
     {
      ulong ticket=PositionTicketForIdentifier(symbol,positionIdentifier);
      if(ticket>0) return ticket;

      // A synchronous trade call can return before the terminal exposes the
      // resulting position snapshot. Keep the stable identifier temporarily:
      // the transaction handler and manager reconcile it to POSITION_TICKET.
      PrintFormat("MedisTouch BrokerAdapter: position identifier #%I64u has no current ticket snapshot yet; deferred reconciliation will retry.",positionIdentifier);
      return positionIdentifier;
     }

   ulong orderTicket=m_trade.ResultOrder();
   if(orderTicket>0)
     {
      if(PositionSelectByTicket(orderTicket) &&
         PositionGetString(POSITION_SYMBOL)==symbol &&
         (ulong)PositionGetInteger(POSITION_MAGIC)==m_magic)
         return orderTicket;
      PrintFormat("MedisTouch BrokerAdapter: accepted order #%I64u has no resolved deal/position identity yet; transaction recovery must reconcile it.",orderTicket);
      return orderTicket;
     }

   Print("MedisTouch BrokerAdapter: broker accepted a request without a resolvable deal, order, or position identifier.");
   return 0;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::MarketBuy(string symbol,double volume,double sl,double tp,ulong &ticketOut,double &fillPriceOut,string comment)
  {
   ticketOut=0; fillPriceOut=0.0;
   ResetLastRequestStatus();
   if(!IsConnected() || !IsMarketOpenForTrading(symbol,true,true)) { m_lastLatencyUs=0; return false; }
   double refPrice=SymbolInfoDouble(symbol,SYMBOL_ASK);
   if(!ValidateStopDistance(symbol,refPrice,sl,tp,true,"MarketBuy")) { m_lastLatencyUs=0; return false; }
   ulong t0=GetMicrosecondCount();
   for(int i=0;i<m_maxRetries;i++)
     {
      bool requestOk=m_trade.Buy(volume,symbol,0.0,sl,tp,comment);
      m_lastRequestAttempted=true;
      m_lastRetcode=m_trade.ResultRetcode();
      CaptureBrokerIdentifiers(symbol);
      if(requestOk && LastRequestOk("MarketBuy"))
        {
         ticketOut=ResolvePositionTicket(symbol);
         fillPriceOut=m_trade.ResultPrice();
         m_lastLatencyUs=GetMicrosecondCount()-t0;
         return ticketOut>0;
        }
      uint code=m_lastRetcode;
      if(!IsRetryable(code)) break;
      Sleep(DelayForRetcode(code));
     }
   m_lastLatencyUs=GetMicrosecondCount()-t0;
   return false;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::MarketSell(string symbol,double volume,double sl,double tp,ulong &ticketOut,double &fillPriceOut,string comment)
  {
   ticketOut=0; fillPriceOut=0.0;
   ResetLastRequestStatus();
   if(!IsConnected() || !IsMarketOpenForTrading(symbol,true,false)) { m_lastLatencyUs=0; return false; }
   double refPrice=SymbolInfoDouble(symbol,SYMBOL_BID);
   if(!ValidateStopDistance(symbol,refPrice,sl,tp,false,"MarketSell")) { m_lastLatencyUs=0; return false; }
   ulong t0=GetMicrosecondCount();
   for(int i=0;i<m_maxRetries;i++)
     {
      bool requestOk=m_trade.Sell(volume,symbol,0.0,sl,tp,comment);
      m_lastRequestAttempted=true;
      m_lastRetcode=m_trade.ResultRetcode();
      CaptureBrokerIdentifiers(symbol);
      if(requestOk && LastRequestOk("MarketSell"))
        {
         ticketOut=ResolvePositionTicket(symbol);
         fillPriceOut=m_trade.ResultPrice();
         m_lastLatencyUs=GetMicrosecondCount()-t0;
         return ticketOut>0;
        }
      uint code=m_lastRetcode;
      if(!IsRetryable(code)) break;
      Sleep(DelayForRetcode(code));
     }
   m_lastLatencyUs=GetMicrosecondCount()-t0;
   return false;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::PlaceLimit(string symbol,ENUM_ORDER_TYPE type,double volume,double price,double sl,double tp,ulong &ticketOut,string comment)
  {
   ticketOut=0;
   ResetLastRequestStatus();
   if(type!=ORDER_TYPE_BUY_LIMIT && type!=ORDER_TYPE_SELL_LIMIT) return false;
   bool isBuy=(type==ORDER_TYPE_BUY_LIMIT);
   if(!IsConnected() || !IsMarketOpenForTrading(symbol,true,isBuy)) { m_lastLatencyUs=0; return false; }
   if(!ValidateStopDistance(symbol,price,sl,tp,isBuy,"PlaceLimit")) { m_lastLatencyUs=0; return false; }
   ulong t0=GetMicrosecondCount();
   for(int i=0;i<m_maxRetries;i++)
     {
      bool ok=isBuy
               ? m_trade.BuyLimit(volume,price,symbol,sl,tp,ORDER_TIME_GTC,0,comment)
               : m_trade.SellLimit(volume,price,symbol,sl,tp,ORDER_TIME_GTC,0,comment);
      m_lastRequestAttempted=true;
      m_lastRetcode=m_trade.ResultRetcode();
      CaptureBrokerIdentifiers(symbol);
      if(ok && LastRequestOk("PlaceLimit"))
        {
         ticketOut=m_trade.ResultOrder();
         m_lastLatencyUs=GetMicrosecondCount()-t0;
         return ticketOut>0;
        }
      uint code=m_lastRetcode;
      if(!IsRetryable(code)) break;
      Sleep(DelayForRetcode(code));
     }
   m_lastLatencyUs=GetMicrosecondCount()-t0;
   return false;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::CancelOrder(ulong ticket)
  {
   if(!IsConnected() || ticket==0 || !OrderSelect(ticket)) return false;
   if((ulong)OrderGetInteger(ORDER_MAGIC)!=m_magic)
     {
      PrintFormat("MedisTouch BrokerAdapter: CancelOrder refused for foreign magic order #%I64u.",ticket);
      return false;
     }
   bool submitted=m_trade.OrderDelete(ticket);
   if(!submitted)
     {
      LastExecutionCompleted("CancelOrder",false,false);
      return false;
     }
   return LastExecutionCompleted("CancelOrder",false,false);
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::ModifySLTP(ulong ticket,double sl,double tp)
  {
   if(!IsConnected() || !PositionSelectByTicket(ticket)) return false;
   if((ulong)PositionGetInteger(POSITION_MAGIC)!=m_magic)
     {
      PrintFormat("MedisTouch BrokerAdapter: ModifySLTP refused for foreign magic position #%I64u.",ticket);
      return false;
     }
   string symbol=PositionGetString(POSITION_SYMBOL);
   bool isBuy=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY);
   double refPrice=isBuy ? SymbolInfoDouble(symbol,SYMBOL_BID) : SymbolInfoDouble(symbol,SYMBOL_ASK);
   if(!ValidateStopDistance(symbol,refPrice,sl,tp,isBuy,"ModifySLTP")) return false;
   bool submitted=m_trade.PositionModify(ticket,sl,tp);
   if(!submitted)
     {
      LastExecutionCompleted("ModifySLTP",false,true);
      return false;
     }
   return LastExecutionCompleted("ModifySLTP",false,true);
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::ClosePartial(ulong ticket,double volume)
  {
   if(!IsConnected() || !PositionSelectByTicket(ticket)) return false;
   string symbol=PositionGetString(POSITION_SYMBOL);
   if((ulong)PositionGetInteger(POSITION_MAGIC)!=m_magic)
     {
      PrintFormat("MedisTouch BrokerAdapter: ClosePartial refused for foreign magic position #%I64u.",ticket);
      return false;
     }
   if(!IsMarketOpenForTrading(symbol,false,true)) return false;

   double initialVolume=PositionGetDouble(POSITION_VOLUME);
   double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   double minVolume=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   if(initialVolume<=0.0 || step<=0.0 || minVolume<=0.0 || volume<=0.0)
     {
      PrintFormat("MedisTouch BrokerAdapter: ClosePartial refused invalid volume (ticket=%I64u requested=%.8f current=%.8f).",ticket,volume,initialVolume);
      return false;
     }

   int volumeDigits=0;
   for(int d=0;d<=8;d++)
      if(MathAbs(step-NormalizeDouble(step,d))<1e-9) { volumeDigits=d; break; }
   double closeVolume=NormalizeDouble(MathFloor((volume+1e-10)/step)*step,volumeDigits);
   if(closeVolume<minVolume || closeVolume>=initialVolume-step*0.25)
     {
      PrintFormat("MedisTouch BrokerAdapter: ClosePartial refused non-partial volume (ticket=%I64u requested=%.8f normalized=%.8f current=%.8f).",ticket,volume,closeVolume,initialVolume);
      return false;
     }

   ENUM_ACCOUNT_MARGIN_MODE mode=(ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   bool submitted=false;
   if(mode==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
      submitted=m_trade.PositionClosePartial(ticket,closeVolume);
   else
     {
      // CTrade::PositionClosePartial is documented for hedging accounts only.
      // On netting/exchange accounts, an opposite deal reduces the single net
      // position. The strict volume checks above prevent accidental reversal.
      bool isBuy=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY);
      submitted=isBuy
                ? m_trade.Sell(closeVolume,symbol,0.0,0.0,0.0,"MidasTouch partial reduction")
                : m_trade.Buy(closeVolume,symbol,0.0,0.0,0.0,"MidasTouch partial reduction");
     }
   if(!submitted)
     {
      LastExecutionCompleted("ClosePartial",true,false);
      return false;
     }
   if(!LastExecutionCompleted("ClosePartial",true,false)) return false;

   bool remains=PositionSelectByTicket(ticket);
   if(!remains && mode!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
      remains=PositionSelect(symbol); // a netting position's ticket may be reissued after a deal
   if(!remains)
     {
      PrintFormat("MedisTouch BrokerAdapter: ClosePartial was accepted but position #%I64u no longer exists; verify state before treating it as a runner.",ticket);
      return false;
     }
   double remainingVolume=PositionGetDouble(POSITION_VOLUME);
   if(remainingVolume>=initialVolume-step*0.25 || remainingVolume<minVolume-step*0.25)
     {
      PrintFormat("MedisTouch BrokerAdapter: ClosePartial did not leave a valid reduced position (ticket=%I64u before=%.8f after=%.8f).",ticket,initialVolume,remainingVolume);
      return false;
     }
   return true;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::CloseFull(ulong ticket)
  {
   if(!IsConnected() || !PositionSelectByTicket(ticket)) return false;
   string symbol=PositionGetString(POSITION_SYMBOL);
   if((ulong)PositionGetInteger(POSITION_MAGIC)!=m_magic)
     {
      PrintFormat("MedisTouch BrokerAdapter: CloseFull refused for foreign magic position #%I64u.",ticket);
      return false;
     }
   if(!IsMarketOpenForTrading(symbol,false,true)) return false;
   bool submitted=m_trade.PositionClose(ticket);
   if(!submitted)
     {
      LastExecutionCompleted("CloseFull",true,false);
      return false;
     }
   if(!LastExecutionCompleted("CloseFull",true,false)) return false;
   if(PositionSelectByTicket(ticket))
     {
      double remainingVolume=PositionGetDouble(POSITION_VOLUME);
      if(remainingVolume>0.0)
        {
         PrintFormat("MedisTouch BrokerAdapter: CloseFull was accepted but position #%I64u still has %.8f lot(s); emergency stop must remain unverified.",ticket,remainingVolume);
         return false;
        }
     }
   return true;
  }
#endif
//+------------------------------------------------------------------+
