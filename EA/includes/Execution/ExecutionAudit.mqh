//+------------------------------------------------------------------+
//| Execution/ExecutionAudit.mqh                                    |
//| Append-only terminal execution audit trail.                     |
//+------------------------------------------------------------------+
#ifndef MIDAS_EXECUTIONAUDIT_MQH
#define MIDAS_EXECUTIONAUDIT_MQH

class CExecutionAudit
  {
private:
   string m_symbol;
   string m_filename;
   ulong  m_magic;

public:
   void Init(const string symbol,ulong magic)
     {
      m_symbol=symbol;
      m_magic=magic;
      string safe=symbol;
      StringReplace(safe,"/","_");
      StringReplace(safe,"\\","_");
      m_filename="MidasTouch_ExecutionAudit_"+safe+".csv";
     }

   void Log(const string eventName,const string detail,long decisionId=0,ulong ticket=0,
            double volume=0.0,double price=0.0,double sl=0.0,double tp=0.0)
     {
      ResetLastError();
      int handle=FileOpen(m_filename,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,';');
      if(handle!=INVALID_HANDLE)
        {
         if(FileSize(handle)==0)
            FileWrite(handle,"time","symbol","magic","event","decision_id","ticket","volume","price","sl","tp","detail");
         FileSeek(handle,0,SEEK_END);
         FileWrite(handle,TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),m_symbol,
                   (long)m_magic,eventName,decisionId,(long)ticket,
                   DoubleToString(volume,2),DoubleToString(price,_Digits),
                   DoubleToString(sl,_Digits),DoubleToString(tp,_Digits),detail);
         FileFlush(handle);
         FileClose(handle);
        }
      PrintFormat("MidasTouch AUDIT | %s | %s | %s | magic=%I64u | id=%I64d | ticket=%I64u | %s",
                  TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),m_symbol,eventName,
                  m_magic,decisionId,ticket,detail);
     }
  };

#endif
//+------------------------------------------------------------------+
