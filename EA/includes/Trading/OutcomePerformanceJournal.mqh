//+------------------------------------------------------------------+
//| Trading/OutcomePerformanceJournal.mqh                             |
//| Durable, symbol-scoped resolved outcomes for adaptive capacity.  |
//+------------------------------------------------------------------+
#ifndef OUTCOMEPERFORMANCEJOURNAL_MQH
#define OUTCOMEPERFORMANCEJOURNAL_MQH

#include "../Core/Config.mqh"

struct OutcomePerformanceRecord
  {
   long     decisionId;
   datetime closedAt;
   int      resultCode; // 1=win, -1=loss, 0=scratch, 2=ambiguous
   double   realizedR;
   double   netPnL;
   double   commission;
   double   swap;
   double   fee;
  };

class COutcomePerformanceJournal
  {
private:
   OutcomePerformanceRecord m_records[];
   long                     m_decisionIds[];
   string                   m_filename;
   bool                     m_persistent;

   string SanitizeSymbol(const string symbol) const
     {
      string out="";
      for(int i=0;i<StringLen(symbol);i++)
        {
         ushort ch=StringGetCharacter(symbol,i);
         bool allowed=(ch>='0' && ch<='9') ||
                      (ch>='A' && ch<='Z') ||
                      (ch>='a' && ch<='z') ||
                      ch=='_';
         out+=allowed?ShortToString(ch):"_";
        }
      return out==""?"SYMBOL":out;
     }

   int FindDecision(long decisionId) const
     {
      for(int i=0;i<ArraySize(m_decisionIds);i++)
         if(m_decisionIds[i]==decisionId)return i;
      return -1;
     }

   void AddLoadedRecord(const OutcomePerformanceRecord &record)
     {
      int n=ArraySize(m_records);
      ArrayResize(m_records,n+1);
      m_records[n]=record;
      ArrayResize(m_decisionIds,n+1);
      m_decisionIds[n]=record.decisionId;
     }

   void Load()
     {
      ArrayFree(m_records);
      ArrayFree(m_decisionIds);
      if(!m_persistent || StringLen(m_filename)==0 || !FileIsExist(m_filename))return;

      int handle=FileOpen(m_filename,FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ|FILE_SHARE_WRITE);
      if(handle==INVALID_HANDLE)
        {
         PrintFormat("MedisTouch outcome journal: cannot open %s for reading (error %d).",m_filename,GetLastError());
         return;
        }

      while(!FileIsEnding(handle))
        {
         string line=FileReadString(handle);
         if(StringLen(line)==0 || StringFind(line,"decision_id;")==0)continue;

         string fields[];
         int count=StringSplit(line,StringGetCharacter(";",0),fields);
         if(count<8)continue;

         OutcomePerformanceRecord record;
         ZeroMemory(record);
         record.decisionId=(long)StringToInteger(fields[0]);
         record.closedAt=(datetime)StringToInteger(fields[1]);
         record.resultCode=(int)StringToInteger(fields[2]);
         record.realizedR=StringToDouble(fields[3]);
         record.netPnL=StringToDouble(fields[4]);
         record.commission=StringToDouble(fields[5]);
         record.swap=StringToDouble(fields[6]);
         record.fee=StringToDouble(fields[7]);
         if(record.decisionId<=0 || record.closedAt<=0)continue;
         if(FindDecision(record.decisionId)>=0)continue; // tolerate a duplicate/partial legacy append
         if(record.resultCode!=1 && record.resultCode!=-1 && record.resultCode!=0 && record.resultCode!=2)continue;
         AddLoadedRecord(record);
        }
      FileClose(handle);
     }

public:
   COutcomePerformanceJournal():m_filename(""),m_persistent(false){}

   void Init(string symbol)
     {
      m_filename="MedisTouch_OutcomePerformance_"+SanitizeSymbol(symbol)+".csv";
      // Strategy Tester data must never contaminate a terminal's live evidence journal.
      m_persistent=(MQLInfoInteger(MQL_TESTER)==0);
      ArrayFree(m_records);
      ArrayFree(m_decisionIds);
      if(m_persistent)Load();
     }

   void RestoreStats(OutcomeStats &out) const
     {
      ZeroMemory(out);
      for(int i=0;i<ArraySize(m_records);i++)
        {
         OutcomePerformanceRecord r=m_records[i];
         if(r.resultCode==2)
           {
            out.ambiguous++;
            continue;
           }

         if(r.resultCode==1)out.wins++;
         else if(r.resultCode==-1)out.losses++;
         else out.scratches++;

         out.resolvedCount++;
         out.netPnL+=r.netPnL;
         if(r.netPnL>0.0)out.grossProfit+=r.netPnL;
         else if(r.netPnL<0.0)out.grossLoss+=-r.netPnL;
         out.totalCommission+=r.commission;
         out.totalSpreadCost+=r.swap;
         out.totalSlippageCost+=r.fee;
         out.sumRMultiple+=r.realizedR;
        }
     }

   int Count() const { return ArraySize(m_records); }

   bool GetRecordAt(int index,OutcomePerformanceRecord &out) const
     {
      if(index<0 || index>=ArraySize(m_records))return false;
      out=m_records[index];
      return true;
     }

   bool RecordOutcome(long decisionId,datetime closedAt,int resultCode,double realizedR,
                      double netPnL,double commission,double swap,double fee)
     {
      if(decisionId<=0 || closedAt<=0)return false;
      if(resultCode!=1 && resultCode!=-1 && resultCode!=0 && resultCode!=2)return false;
      if(FindDecision(decisionId)>=0)return true;
      if(!m_persistent)return true;

      int handle=FileOpen(m_filename,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ|FILE_SHARE_WRITE);
      if(handle==INVALID_HANDLE)
        {
         PrintFormat("MedisTouch outcome journal: cannot open %s for append (error %d).",m_filename,GetLastError());
         return false;
        }

      bool empty=(FileSize(handle)==0);
      FileSeek(handle,0,SEEK_END);
      if(empty)
         FileWriteString(handle,"decision_id;closed_at;result_code;realized_r;net_pnl;commission;swap;fee\r\n");

      string row=StringFormat("%I64d;%I64d;%d;%s;%s;%s;%s;%s\r\n",
                              decisionId,(long)closedAt,resultCode,
                              DoubleToString(realizedR,10),DoubleToString(netPnL,8),
                              DoubleToString(commission,8),DoubleToString(swap,8),DoubleToString(fee,8));
      uint written=FileWriteString(handle,row);
      FileFlush(handle);
      FileClose(handle);
      if(written==0)
        {
         PrintFormat("MedisTouch outcome journal: write failed for decision #%I64d.",decisionId);
         return false;
        }

      OutcomePerformanceRecord record;
      ZeroMemory(record);
      record.decisionId=decisionId;
      record.closedAt=closedAt;
      record.resultCode=resultCode;
      record.realizedR=realizedR;
      record.netPnL=netPnL;
      record.commission=commission;
      record.swap=swap;
      record.fee=fee;
      AddLoadedRecord(record);
      return true;
     }
  };

#endif
//+------------------------------------------------------------------+
