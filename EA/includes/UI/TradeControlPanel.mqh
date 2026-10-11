//+------------------------------------------------------------------+
//| UI/TradeControlPanel.mqh                                         |
//| On-chart operator controls and append-only execution audit trail. |
//+------------------------------------------------------------------+
#ifndef MIDAS_TRADECONTROLPANEL_MQH
#define MIDAS_TRADECONTROLPANEL_MQH

enum ENUM_PANEL_ACTION
  {
   PANEL_ACTION_NONE=0,
   PANEL_ACTION_BUY,
   PANEL_ACTION_SELL,
   PANEL_ACTION_CLOSE_ALL,
   PANEL_ACTION_EMERGENCY_STOP,
   PANEL_ACTION_RESUME
  };

class CTradeControlPanel
  {
private:
   long   m_chart;
   string m_prefix;
   string m_symbol;
   ulong  m_magic;
   int    m_x;
   int    m_y;

   bool CreateLabel(const string suffix,const string caption,int x,int y,int fontSize,color textColor)
     {
      string name=m_prefix+suffix;
      if(ObjectFind(m_chart,name)<0 && !ObjectCreate(m_chart,name,OBJ_LABEL,0,0,0))
         return false;
      ObjectSetInteger(m_chart,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetInteger(m_chart,name,OBJPROP_XDISTANCE,x);
      ObjectSetInteger(m_chart,name,OBJPROP_YDISTANCE,y);
      ObjectSetInteger(m_chart,name,OBJPROP_FONTSIZE,fontSize);
      ObjectSetInteger(m_chart,name,OBJPROP_COLOR,textColor);
      ObjectSetInteger(m_chart,name,OBJPROP_HIDDEN,true);
      ObjectSetInteger(m_chart,name,OBJPROP_SELECTABLE,false);
      ObjectSetString(m_chart,name,OBJPROP_FONT,"Consolas");
      ObjectSetString(m_chart,name,OBJPROP_TEXT,caption);
      return true;
     }

   bool CreateButton(const string suffix,const string caption,int x,int y,int width,color background,color foreground)
     {
      string name=m_prefix+suffix;
      if(ObjectFind(m_chart,name)<0 && !ObjectCreate(m_chart,name,OBJ_BUTTON,0,0,0))
         return false;
      ObjectSetInteger(m_chart,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetInteger(m_chart,name,OBJPROP_XDISTANCE,x);
      ObjectSetInteger(m_chart,name,OBJPROP_YDISTANCE,y);
      ObjectSetInteger(m_chart,name,OBJPROP_XSIZE,width);
      ObjectSetInteger(m_chart,name,OBJPROP_YSIZE,25);
      ObjectSetInteger(m_chart,name,OBJPROP_FONTSIZE,9);
      ObjectSetInteger(m_chart,name,OBJPROP_COLOR,foreground);
      ObjectSetInteger(m_chart,name,OBJPROP_BGCOLOR,background);
      ObjectSetInteger(m_chart,name,OBJPROP_BORDER_COLOR,clrDimGray);
      ObjectSetInteger(m_chart,name,OBJPROP_HIDDEN,true);
      ObjectSetInteger(m_chart,name,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(m_chart,name,OBJPROP_STATE,false);
      ObjectSetString(m_chart,name,OBJPROP_FONT,"Arial");
      ObjectSetString(m_chart,name,OBJPROP_TEXT,caption);
      return true;
     }

public:
   bool Init(long chartId,string symbol,ulong magic)
     {
      m_chart=chartId;
      m_prefix="MidasCtl_";
      m_symbol=symbol;
      m_magic=magic;
      m_x=10;
      m_y=18;
      ObjectsDeleteAll(m_chart,m_prefix);
      bool ok=true;
      ok=CreateLabel("TITLE","MIDAS TOUCH  |  EXECUTION CONTROL",m_x,m_y,10,clrWhite) && ok;
      ok=CreateLabel("STATUS1","Loading account and trade state...",m_x,m_y+20,9,clrSilver) && ok;
      ok=CreateLabel("STATUS2","Trail: --  |  Session: --",m_x,m_y+37,9,clrSilver) && ok;
      int by=m_y+57;
      int bw=86;
      int gap=5;
      ok=CreateButton("BUY","BUY",m_x,by,bw,clrForestGreen,clrWhite) && ok;
      ok=CreateButton("SELL","SELL",m_x+(bw+gap),by,bw,clrFireBrick,clrWhite) && ok;
      ok=CreateButton("CLOSE","CLOSE ALL",m_x+2*(bw+gap),by,bw,clrDarkSlateGray,clrWhite) && ok;
      ok=CreateButton("STOP","EMERGENCY STOP",m_x+3*(bw+gap),by,105,clrMaroon,clrWhite) && ok;
      ok=CreateButton("RESUME","RESUME",m_x+3*(bw+gap)+110,by,72,clrDarkGreen,clrWhite) && ok;
      ChartRedraw(m_chart);
      return ok;
     }

   void Refresh(int managedPositions,double floatingPnl,bool trailingEnabled,bool emergencyStopped,string sessionName)
     {
      string state=emergencyStopped ? "EMERGENCY HALT" : "RUNNING";
      color stateColor=emergencyStopped ? clrTomato : clrLimeGreen;
      ObjectSetString(m_chart,m_prefix+"STATUS1",OBJPROP_TEXT,
                      StringFormat("%s | Magic: %I64u | Positions: %d | Float: %.2f",
                                   m_symbol,m_magic,managedPositions,floatingPnl));
      ObjectSetInteger(m_chart,m_prefix+"STATUS1",OBJPROP_COLOR,clrSilver);
      ObjectSetString(m_chart,m_prefix+"STATUS2",OBJPROP_TEXT,
                      StringFormat("State: %s  |  Trailing profit: %s  |  Session: %s",
                                   state,(trailingEnabled ? "ON" : "OFF"),sessionName));
      ObjectSetInteger(m_chart,m_prefix+"STATUS2",OBJPROP_COLOR,stateColor);
      ChartRedraw(m_chart);
     }

   int CommandForClick(const string objectName)
     {
      if(StringFind(objectName,m_prefix)!=0)
         return PANEL_ACTION_NONE;
      ObjectSetInteger(m_chart,objectName,OBJPROP_STATE,false);
      string key=StringSubstr(objectName,StringLen(m_prefix));
      if(key=="BUY") return PANEL_ACTION_BUY;
      if(key=="SELL") return PANEL_ACTION_SELL;
      if(key=="CLOSE") return PANEL_ACTION_CLOSE_ALL;
      if(key=="STOP") return PANEL_ACTION_EMERGENCY_STOP;
      if(key=="RESUME") return PANEL_ACTION_RESUME;
      return PANEL_ACTION_NONE;
     }

   void Destroy()
     {
      ObjectsDeleteAll(m_chart,m_prefix);
      ChartRedraw(m_chart);
     }
  };

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
