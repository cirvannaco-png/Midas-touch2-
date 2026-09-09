//+------------------------------------------------------------------+
//| Monitoring/SLModificationAudit.mqh                               |
//| Append-only local audit trail for successful SL changes.          |
//+------------------------------------------------------------------+
#ifndef SLMODIFICATIONAUDIT_MQH
#define SLMODIFICATIONAUDIT_MQH

class CSLModificationAudit
  {
private:
   string m_file;
   bool   m_common;
public:
   void Init(string fileName="MedisTouch_SL_Audit.csv", bool useCommonFolder=false)
     {
      m_file=fileName;
      m_common=useCommonFolder;
      int flags=FILE_CSV|FILE_READ|FILE_WRITE|FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_ANSI;
      if(m_common) flags|=FILE_COMMON;
      int h=FileOpen(m_file,flags,',');
      if(h==INVALID_HANDLE)
        {
         PrintFormat("MedisTouch SL audit: cannot open %s",m_file);
         return;
        }
      if(FileSize(h)==0)
         FileWrite(h,"timestamp","ticket","symbol","side","stage","old_sl","new_sl","price","r_multiple","reason");
      FileClose(h);
     }

   void Record(ulong ticket,string symbol,bool isBuy,string stage,double oldSL,double newSL,
               double price,double rMultiple,string reason)
     {
      int flags=FILE_CSV|FILE_READ|FILE_WRITE|FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_ANSI;
      if(m_common) flags|=FILE_COMMON;
      int h=FileOpen(m_file,flags,',');
      if(h==INVALID_HANDLE)
        {
         PrintFormat("MedisTouch SL audit: failed to append ticket #%d",ticket);
         return;
        }
      FileSeek(h,0,SEEK_END);
      FileWrite(h,TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),LongToString((long)ticket),symbol,
                isBuy?"BUY":"SELL",stage,DoubleToString(oldSL,8),DoubleToString(newSL,8),
                DoubleToString(price,8),DoubleToString(rMultiple,4),reason);
      FileFlush(h);
      FileClose(h);
     }
  };
#endif
//+------------------------------------------------------------------+
