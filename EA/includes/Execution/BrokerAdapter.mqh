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
   ulong             ResolvePositionTicket();
   bool              IsRetryable(uint retcode);
   int               DelayForRetcode(uint retcode);
   bool              IsConnected();
   bool              IsMarketOpenForTrading(string symbol, bool requireFullOpen, bool isBuy=true);
   bool              ValidateStopDistance(string symbol, double refPrice, double sl, double tp, bool isBuy, string action);

public:
   void              Init(ulong magic, int maxRetries = 3, int retryDelayMs = 300);
   double            LastLatencyMs() { return (double)m_lastLatencyUs / 1000.0; }
   bool              MarketBuy(string symbol, double volume, double sl, double tp, ulong &ticketOut, double &fillPriceOut, string comment = "");
   bool              MarketSell(string symbol, double volume, double sl, double tp, ulong &ticketOut, double &fillPriceOut, string comment = "");
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
ulong CBrokerAdapter::ResolvePositionTicket()
  {
   ulong dealTicket=m_trade.ResultDeal();
   if(dealTicket==0) return m_trade.ResultOrder();
   if(!HistoryDealSelect(dealTicket))
     {
      PrintFormat("MedisTouch BrokerAdapter: could not select deal #%d; falling back to order ticket.",dealTicket);
      return m_trade.ResultOrder();
     }
   ulong positionId=(ulong)HistoryDealGetInteger(dealTicket,DEAL_POSITION_ID);
   if(positionId==0)
     {
      PrintFormat("MedisTouch BrokerAdapter: deal #%d has no DEAL_POSITION_ID; falling back to order ticket.",dealTicket);
      return m_trade.ResultOrder();
     }
   return positionId;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::MarketBuy(string symbol,double volume,double sl,double tp,ulong &ticketOut,double &fillPriceOut,string comment)
  {
   ticketOut=0; fillPriceOut=0.0;
   if(!IsConnected() || !IsMarketOpenForTrading(symbol,true,true)) { m_lastLatencyUs=0; return false; }
   double refPrice=SymbolInfoDouble(symbol,SYMBOL_ASK);
   if(!ValidateStopDistance(symbol,refPrice,sl,tp,true,"MarketBuy")) { m_lastLatencyUs=0; return false; }
   ulong t0=GetMicrosecondCount();
   for(int i=0;i<m_maxRetries;i++)
     {
      if(m_trade.Buy(volume,symbol,0.0,sl,tp,comment) && LastRequestOk("MarketBuy"))
        {
         ticketOut=ResolvePositionTicket();
         fillPriceOut=m_trade.ResultPrice();
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
bool CBrokerAdapter::MarketSell(string symbol,double volume,double sl,double tp,ulong &ticketOut,double &fillPriceOut,string comment)
  {
   ticketOut=0; fillPriceOut=0.0;
   if(!IsConnected() || !IsMarketOpenForTrading(symbol,true,false)) { m_lastLatencyUs=0; return false; }
   double refPrice=SymbolInfoDouble(symbol,SYMBOL_BID);
   if(!ValidateStopDistance(symbol,refPrice,sl,tp,false,"MarketSell")) { m_lastLatencyUs=0; return false; }
   ulong t0=GetMicrosecondCount();
   for(int i=0;i<m_maxRetries;i++)
     {
      if(m_trade.Sell(volume,symbol,0.0,sl,tp,comment) && LastRequestOk("MarketSell"))
        {
         ticketOut=ResolvePositionTicket();
         fillPriceOut=m_trade.ResultPrice();
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
   if(m_trade.PositionModify(ticket,sl,tp)) return true;
   LastRequestOk("ModifySLTP"); return false;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::ClosePartial(ulong ticket,double volume)
  {
   if(!IsConnected() || !PositionSelectByTicket(ticket)) return false;
   if(!IsMarketOpenForTrading(PositionGetString(POSITION_SYMBOL),false,true)) return false;
   if(m_trade.PositionClosePartial(ticket,volume)) return true;
   LastRequestOk("ClosePartial"); return false;
  }
//+------------------------------------------------------------------+
bool CBrokerAdapter::CloseFull(ulong ticket)
  {
   if(!IsConnected() || !PositionSelectByTicket(ticket)) return false;
   if(!IsMarketOpenForTrading(PositionGetString(POSITION_SYMBOL),false,true)) return false;
   if(m_trade.PositionClose(ticket)) return true;
   LastRequestOk("CloseFull"); return false;
  }
#endif
//+------------------------------------------------------------------+
