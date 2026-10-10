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
   int               m_maxRetries;
   int               m_retryDelayMs;
   ulong             m_lastLatencyUs;

   bool              LastRequestOk(string action);
   ulong             ResolvePositionTicket(bool &fillConfirmedOut);
   bool              IsRetryable(uint retcode);
   int               DelayForRetcode(uint retcode);
   bool              IsConnected();
   bool              IsMarketOpenForTrading(string symbol, bool requireFullOpen, bool isBuy=true);
   bool              ValidateStopDistance(string symbol, double refPrice, double sl, double tp, bool isBuy, string action);

public:
   void              Init(ulong magic, int maxRetries = 3, int retryDelayMs = 300);
   double            LastLatencyMs() { return (double)m_lastLatencyUs / 1000.0; }
   bool              MarketBuy(string symbol, double volume, double sl, double tp, ulong &ticketOut, double &fillPriceOut, bool &fillConfirmedOut, string comment = "");
   bool              MarketSell(string symbol, double volume, double sl, double tp, ulong &ticketOut, double &fillPriceOut, bool &fillConfirmedOut, string comment = "");
   bool              PlaceLimit(string symbol, ENUM_ORDER_TYPE type, double volume, double price,
                                double sl, double tp, ulong &ticketOut, string comment = "");
   bool              CancelOrder(ulong ticket);
   bool              ModifySLTP(ulong ticket, double sl, double tp);
   bool              ClosePartial(ulong ticket, double volume);
   bool              CloseFull(ulong ticket);
  };
//+------------------------------------------------------------------+
void CBrokerAdapter::Init(ulong magic, int maxRetries, int retryDelayMs)
  {
   m_trade.SetExpertMagicNumber(magic);
   m_trade.SetDeviationInPoints(20);
   m_trade.SetTypeFillingBySymbol(_Symbol);
   m_maxRetries = MathMax(1,maxRetries);
   m_retryDelayMs = MathMax(0,retryDelayMs);
   m_lastLatencyUs = 0;
  }
//+------------------------------------------------------------------+
// Retry only broker outcomes that are explicitly transient. Unknown,
// ambiguous, or permanent outcomes fail closed to prevent duplicate exposure.
bool CBrokerAdapter::IsRetryable(uint retcode)
  {
   switch(retcode)
     {
      case TRADE_RETCODE_REQUOTE:
      case TRADE_RETCODE_PRICE_CHANGED:
      case TRADE_RETCODE_PRICE_OFF:
      case TRADE_RETCODE_CONNECTION:
      case TRADE_RETCODE_TIMEOUT:
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
      case TRADE_RETCODE_CONNECTION:
      case TRADE_RETCODE_TIMEOUT:
         return MathMax(m_retryDelayMs,500);
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
ulong CBrokerAdapter::ResolvePositionTicket(bool &fillConfirmedOut)
  {
   // Never interpret an order ticket as a filled position identifier. If the
   // server accepted the request but the deal/position identity is not yet
   // visible, return the order ticket and let TRADE_TRANSACTION_DEAL_ADD
   // promote the managed trade from Pending to Filled.
   fillConfirmedOut=false;
   ulong dealTicket=m_trade.ResultDeal();
   if(dealTicket>0 && HistoryDealSelect(dealTicket))
     {
      ulong positionId=(ulong)HistoryDealGetInteger(dealTicket,DEAL_POSITION_ID);
      uint code=m_trade.ResultRetcode();
      if(positionId>0 && code==TRADE_RETCODE_DONE)
        {
         fillConfirmedOut=true;
         return positionId;
        }
     }
   return m_trade.ResultOrder();
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::MarketBuy(string symbol,double volume,double sl,double tp,ulong &ticketOut,double &fillPriceOut,bool &fillConfirmedOut,string comment)
  {
   ticketOut=0; fillPriceOut=0.0; fillConfirmedOut=false;
   if(!IsConnected() || !IsMarketOpenForTrading(symbol,true,true)) { m_lastLatencyUs=0; return false; }
   double refPrice=SymbolInfoDouble(symbol,SYMBOL_ASK);
   if(!ValidateStopDistance(symbol,refPrice,sl,tp,true,"MarketBuy")) { m_lastLatencyUs=0; return false; }
   ulong t0=GetMicrosecondCount();
   for(int i=0;i<m_maxRetries;i++)
     {
      if(m_trade.Buy(volume,symbol,0.0,sl,tp,comment) && LastRequestOk("MarketBuy"))
        {
         ticketOut=ResolvePositionTicket(fillConfirmedOut);
         fillPriceOut=fillConfirmedOut?m_trade.ResultPrice():0.0;
         m_lastLatencyUs=GetMicrosecondCount()-t0;
         if(ticketOut==0)
            Print("CRITICAL: MarketBuy accepted by trade API but neither a position identifier nor order ticket was available; inspect broker history before retrying.");
         else if(!fillConfirmedOut)
            PrintFormat("MedisTouch BrokerAdapter: MarketBuy accepted as order #%I64u; waiting for confirmed fill event.",ticketOut);
         return ticketOut>0;
        }
      uint code=m_trade.ResultRetcode();
      if(!IsRetryable(code)) break;
      Sleep(DelayForRetcode(code));
     }
   m_lastLatencyUs=GetMicrosecondCount()-t0;
   return false;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::MarketSell(string symbol,double volume,double sl,double tp,ulong &ticketOut,double &fillPriceOut,bool &fillConfirmedOut,string comment)
  {
   ticketOut=0; fillPriceOut=0.0; fillConfirmedOut=false;
   if(!IsConnected() || !IsMarketOpenForTrading(symbol,true,false)) { m_lastLatencyUs=0; return false; }
   double refPrice=SymbolInfoDouble(symbol,SYMBOL_BID);
   if(!ValidateStopDistance(symbol,refPrice,sl,tp,false,"MarketSell")) { m_lastLatencyUs=0; return false; }
   ulong t0=GetMicrosecondCount();
   for(int i=0;i<m_maxRetries;i++)
     {
      if(m_trade.Sell(volume,symbol,0.0,sl,tp,comment) && LastRequestOk("MarketSell"))
        {
         ticketOut=ResolvePositionTicket(fillConfirmedOut);
         fillPriceOut=fillConfirmedOut?m_trade.ResultPrice():0.0;
         m_lastLatencyUs=GetMicrosecondCount()-t0;
         if(ticketOut==0)
            Print("CRITICAL: MarketSell accepted by trade API but neither a position identifier nor order ticket was available; inspect broker history before retrying.");
         else if(!fillConfirmedOut)
            PrintFormat("MedisTouch BrokerAdapter: MarketSell accepted as order #%I64u; waiting for confirmed fill event.",ticketOut);
         return ticketOut>0;
        }
      uint code=m_trade.ResultRetcode();
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
      if(ok && LastRequestOk("PlaceLimit"))
        {
         ticketOut=m_trade.ResultOrder();
         m_lastLatencyUs=GetMicrosecondCount()-t0;
         return ticketOut>0;
        }
      uint code=m_trade.ResultRetcode();
      if(!IsRetryable(code)) break;
      Sleep(DelayForRetcode(code));
     }
   m_lastLatencyUs=GetMicrosecondCount()-t0;
   return false;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::CancelOrder(ulong ticket)
  {
   if(!IsConnected()) return false;
   if(m_trade.OrderDelete(ticket)) return true;
   LastRequestOk("CancelOrder"); return false;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::ModifySLTP(ulong ticket,double sl,double tp)
  {
   if(!IsConnected()) return false;
   if(!PositionSelectByTicket(ticket)) return false;
   string symbol=PositionGetString(POSITION_SYMBOL);
   bool isBuy=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY);
   double refPrice=isBuy ? SymbolInfoDouble(symbol,SYMBOL_BID) : SymbolInfoDouble(symbol,SYMBOL_ASK);
   if(!ValidateStopDistance(symbol,refPrice,sl,tp,isBuy,"ModifySLTP")) return false;
   bool submitted=m_trade.PositionModify(ticket,sl,tp);
   if(submitted && m_trade.ResultRetcode()==TRADE_RETCODE_DONE) return true;
   uint code=m_trade.ResultRetcode();
   PrintFormat("MedisTouch BrokerAdapter: ModifySLTP was not confirmed by the trade server (submitted=%s, retcode=%u, %s).",
               submitted?"true":"false",code,m_trade.ResultRetcodeDescription());
   return false;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::ClosePartial(ulong ticket,double volume)
  {
   if(!IsConnected() || !PositionSelectByTicket(ticket)) return false;
   string symbol=PositionGetString(POSITION_SYMBOL);
   if(!IsMarketOpenForTrading(symbol,false,true)) return false;

   // CTrade::PositionClosePartial is a hedging-account operation only. In
   // netting mode, an opposite deal could close/reverse the aggregated symbol
   // position, so this method deliberately refuses to emulate a partial close.
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      Print("MedisTouch BrokerAdapter: partial close is unsupported on netting/exchange accounts; preserve the existing SL/TP instead of risking a reversal.");
      return false;
     }

   double currentVolume=PositionGetDouble(POSITION_VOLUME);
   double minVolume=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(currentVolume<=0.0 || minVolume<=0.0 || step<=0.0 || volume<=0.0)
     {
      PrintFormat("MedisTouch BrokerAdapter: ClosePartial refused due to invalid volume metadata (current=%.8f, requested=%.8f, min=%.8f, step=%.8f).",
                  currentVolume,volume,minVolume,step);
      return false;
     }

   // Round down to the broker's volume grid, and never leave a remainder below
   // minimum volume. This avoids  invalid-volume requests for fractional lots.
   double maxPartial=currentVolume-minVolume;
   if(maxPartial<minVolume-1e-10)
     {
      PrintFormat("MedisTouch BrokerAdapter: position volume %.8f is too small for a legal partial close; retaining the runner.",currentVolume);
      return false;
     }
   double bounded=MathMin(volume,maxPartial);
   double steps=MathFloor((bounded/step)+1e-9);
   double normalized=steps*step;
   int volumeDigits=0;
   for(int digits=0;digits<=8;digits++)
     {
      double scaled=step*MathPow(10.0,digits);
      if(MathAbs(scaled-MathRound(scaled))<1e-8)
        {
         volumeDigits=digits;
         break;
        }
      volumeDigits=digits;
     }
   normalized=NormalizeDouble(normalized,volumeDigits);
   double remainder=NormalizeDouble(currentVolume-normalized,volumeDigits);
   if(normalized<minVolume-1e-10 || remainder<minVolume-1e-10)
     {
      PrintFormat("MedisTouch BrokerAdapter: normalized partial volume %.8f would leave illegal remainder %.8f; keeping the position unchanged.",
                  normalized,remainder);
      return false;
     }

   bool submitted=m_trade.PositionClosePartial(ticket,normalized);
   uint code=m_trade.ResultRetcode();
   if(submitted && (code==TRADE_RETCODE_DONE || code==TRADE_RETCODE_DONE_PARTIAL)) return true;
   PrintFormat("MedisTouch BrokerAdapter: ClosePartial was not confirmed by the trade server (submitted=%s, requested=%.8f, retcode=%u, %s).",
               submitted?"true":"false",normalized,code,m_trade.ResultRetcodeDescription());
   return false;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::CloseFull(ulong ticket)
  {
   if(!IsConnected() || !PositionSelectByTicket(ticket)) return false;
   if(!IsMarketOpenForTrading(PositionGetString(POSITION_SYMBOL),false,true)) return false;
   bool submitted=m_trade.PositionClose(ticket);
   uint code=m_trade.ResultRetcode();
   if(submitted && code==TRADE_RETCODE_DONE) return true;
   PrintFormat("MedisTouch BrokerAdapter: CloseFull was not confirmed by the trade server (submitted=%s, retcode=%u, %s).",
               submitted?"true":"false",code,m_trade.ResultRetcodeDescription());
   return false;
  }
#endif
//+------------------------------------------------------------------+
