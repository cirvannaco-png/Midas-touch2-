//+------------------------------------------------------------------+
//| Execution/TesterDealExport.mqh                                   |
//| Test-only export of native MT5 broker-deal history.              |
//| This component is inert outside MQL_TESTER.                       |
//+------------------------------------------------------------------+
#ifndef MIDAS_TESTERDEALEXPORT_MQH
#define MIDAS_TESTERDEALEXPORT_MQH

struct TesterDealExportRow
  {
   ulong deal_id;
   ulong order_id;
   ulong position_id;
   datetime deal_time;
   string symbol;
   string entry;
   double volume;
   double price;
   double profit;
   double commission;
   double swap;
   double fee;
  };

class CTesterDealExport
  {
private:
   bool   m_enabled;
   string m_symbol;
   string m_runId;
   string m_dealsName;
   string m_openName;
   ulong  m_magic;
   TesterDealExportRow m_rows[];
   ulong  m_seenDeals[];
   ulong  m_riskPositions[];
   double m_positionRiskCash[];

   string SafeName(string value)
     {
      StringReplace(value,"/","_");
      StringReplace(value,"\\","_");
      StringReplace(value,":","_");
      StringReplace(value,"*","_");
      StringReplace(value,"?","_");
      StringReplace(value,"\"","_");
      StringReplace(value,"<","_");
      StringReplace(value,">","_");
      StringReplace(value,"|","_");
      StringReplace(value," ","_");
      if(StringLen(value)==0) value="manual";
      if(StringLen(value)>32) value=StringSubstr(value,0,32);
      return value;
     }

   string EntryName(const ENUM_DEAL_ENTRY entry) const
     {
      if(entry==DEAL_ENTRY_IN) return "IN";
      if(entry==DEAL_ENTRY_OUT) return "OUT";
      if(entry==DEAL_ENTRY_OUT_BY) return "OUT_BY";
      if(entry==DEAL_ENTRY_INOUT) return "INOUT";
      return "UNKNOWN";
     }

   int RiskIndex(const ulong positionId) const
     {
      for(int i=0;i<ArraySize(m_riskPositions);i++)
         if(m_riskPositions[i]==positionId) return i;
      return -1;
     }

   void AddEntryRisk(const ulong positionId,const double riskCash)
     {
      if(positionId==0 || !MathIsValidNumber(riskCash) || riskCash<=0.0) return;
      int index=RiskIndex(positionId);
      if(index<0)
        {
         index=ArraySize(m_riskPositions);
         ArrayResize(m_riskPositions,index+1);
         ArrayResize(m_positionRiskCash,index+1);
         m_riskPositions[index]=positionId;
         m_positionRiskCash[index]=0.0;
        }
      m_positionRiskCash[index]+=riskCash;
     }

   double RiskCash(const ulong positionId) const
     {
      int index=RiskIndex(positionId);
      return index>=0 ? m_positionRiskCash[index] : 0.0;
     }

   bool DealWasSeen(const ulong dealId) const
     {
      for(int i=0;i<ArraySize(m_seenDeals);i++)
         if(m_seenDeals[i]==dealId) return true;
      return false;
     }

public:
   void Init(const string runId,const string symbol,const ulong magic,const bool enabled)
     {
      m_enabled=(enabled && (bool)MQLInfoInteger(MQL_TESTER));
      m_symbol=symbol;
      m_magic=magic;
      m_runId=SafeName(runId);
      m_dealsName="MidasTesterDeals_"+m_runId+".csv";
      m_openName="MidasTesterOpen_"+m_runId+".csv";
      ArrayResize(m_rows,0);
      ArrayResize(m_seenDeals,0);
      ArrayResize(m_riskPositions,0);
      ArrayResize(m_positionRiskCash,0);
      if(m_enabled)
         PrintFormat("MIDAS_TEST_EXPORT_READY run=%s symbol=%s magic=%I64u",
                     m_runId,m_symbol,m_magic);
     }

   bool Enabled() const { return m_enabled; }

   bool Record(const ulong dealId,const ulong orderId,const ulong positionId,
               const datetime dealTime,const string symbol,
               const ENUM_DEAL_ENTRY entry,const double volume,const double price,
               const double profit,const double commission,const double swap,
               const double fee,const double entryRiskCash)
     {
      if(!m_enabled) return true;
      if(dealId==0 || orderId==0 || positionId==0 || symbol=="") return false;
      if(DealWasSeen(dealId)) return true;
      double values[]={volume,price,profit,commission,swap,fee,entryRiskCash};
      for(int i=0;i<ArraySize(values);i++)
         if(!MathIsValidNumber(values[i])) return false;
      if(volume<=0.0 || price<=0.0) return false;

      int seen=ArraySize(m_seenDeals);
      ArrayResize(m_seenDeals,seen+1);
      m_seenDeals[seen]=dealId;
      if(entry==DEAL_ENTRY_IN) AddEntryRisk(positionId,entryRiskCash);

      int count=ArraySize(m_rows);
      ArrayResize(m_rows,count+1);
      m_rows[count].deal_id=dealId;
      m_rows[count].order_id=orderId;
      m_rows[count].position_id=positionId;
      m_rows[count].deal_time=dealTime;
      m_rows[count].symbol=symbol;
      m_rows[count].entry=EntryName(entry);
      m_rows[count].volume=volume;
      m_rows[count].price=price;
      m_rows[count].profit=profit;
      m_rows[count].commission=commission;
      m_rows[count].swap=swap;
      m_rows[count].fee=fee;
      return true;
     }

   void Finalize()
     {
      if(!m_enabled) return;
      int handle=FileOpen(m_dealsName,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
      if(handle==INVALID_HANDLE)
        {
         PrintFormat("MIDAS_TEST_EXPORT_ERROR kind=deals file=%s error=%d",
                     m_dealsName,GetLastError());
         return;
        }
      FileWrite(handle,"position_id","time","entry","volume","profit","commission",
                "swap","fee","risk_cash","lane","deal_id","order_id","symbol");
      for(int i=0;i<ArraySize(m_rows);i++)
        {
         TesterDealExportRow row=m_rows[i];
         FileWrite(handle,
                   IntegerToString((long)row.position_id),
                   TimeToString(row.deal_time,TIME_DATE|TIME_SECONDS),
                   row.entry,
                   DoubleToString(row.volume,8),
                   DoubleToString(row.profit,8),
                   DoubleToString(row.commission,8),
                   DoubleToString(row.swap,8),
                   DoubleToString(row.fee,8),
                   DoubleToString(RiskCash(row.position_id),8),
                   "SMC",
                   IntegerToString((long)row.deal_id),
                   IntegerToString((long)row.order_id),
                   row.symbol);
        }
      FileFlush(handle);
      FileClose(handle);

      int openHandle=FileOpen(m_openName,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
      if(openHandle==INVALID_HANDLE)
        {
         PrintFormat("MIDAS_TEST_EXPORT_ERROR kind=open_positions file=%s error=%d",
                     m_openName,GetLastError());
         return;
        }
      FileWrite(openHandle,"position_id");
      for(int p=PositionsTotal()-1;p>=0;p--)
        {
         ulong ticket=PositionGetTicket(p);
         if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
         if(PositionGetString(POSITION_SYMBOL)!=m_symbol) continue;
         if((ulong)PositionGetInteger(POSITION_MAGIC)!=m_magic) continue;
         ulong positionId=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
         if(positionId>0) FileWrite(openHandle,IntegerToString((long)positionId));
        }
      FileFlush(openHandle);
      FileClose(openHandle);
      PrintFormat("MIDAS_TEST_EXPORT_COMPLETE run=%s deals=%d risk_positions=%d deals_file=%s open_file=%s",
                  m_runId,ArraySize(m_rows),ArraySize(m_riskPositions),m_dealsName,m_openName);
     }
  };

#endif
//+------------------------------------------------------------------+
