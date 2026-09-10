//+------------------------------------------------------------------+
//|                                       Decision/DecisionStore.mqh |
//+------------------------------------------------------------------+
#ifndef DECISIONSTORE_MQH
#define DECISIONSTORE_MQH
#include "../Core/Config.mqh"
#include "TradeDecision.mqh"
#define DECISION_CSV_SEP ";"

class CDecisionStore
  {
private:
   string m_symbol,m_decisionsFile,m_executionsFile;
   TradeDecisionRecord m_decisions[];
   ExecutionRecord m_executions[];
   string SanitizeSymbol(const string s);
   bool AppendLine(const string filename,const string line);
   int ReadLines(const string filename,string &lines[]);
   string SerializeDecision(const TradeDecisionRecord &rec);
   bool ParseDecision(const string line,TradeDecisionRecord &rec);
   string SerializeExecution(const ExecutionRecord &rec);
   bool ParseExecution(const string line,ExecutionRecord &rec);
   void LoadFromDisk();
public:
   CDecisionStore();
   void Init(const string symbol); void Deinit();
   bool Save(const TradeDecisionRecord &rec); bool SaveExecution(long decisionId,double volume,ulong ticket);
   int LoadAll(TradeDecisionRecord &out[]); int LoadAllExecutions(ExecutionRecord &out[]);
   bool FindById(long decisionId,TradeDecisionRecord &out); int Count() const{return ArraySize(m_decisions);}
  };

CDecisionStore::CDecisionStore():m_symbol(""),m_decisionsFile(""),m_executionsFile(""){}
string CDecisionStore::SanitizeSymbol(const string s){string out="";for(int i=0;i<StringLen(s);i++){ushort c=StringGetCharacter(s,i);bool ok=(c>='0'&&c<='9')||(c>='A'&&c<='Z')||(c>='a'&&c<='z')||c=='_';out+=ok?ShortToString(c):"_";}return out==""?"SYMBOL":out;}
void CDecisionStore::Init(const string symbol){m_symbol=(symbol=="")?_Symbol:symbol;string tag=SanitizeSymbol(m_symbol);m_decisionsFile="MedisTouch_Decisions_"+tag+".csv";m_executionsFile="MedisTouch_Executions_"+tag+".csv";ArrayFree(m_decisions);ArrayFree(m_executions);LoadFromDisk();}
void CDecisionStore::Deinit(){ArrayFree(m_decisions);ArrayFree(m_executions);}

bool CDecisionStore::AppendLine(const string filename,const string line)
  {
   ResetLastError();int handle=FileOpen(filename,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);if(handle==INVALID_HANDLE){PrintFormat("MedisTouch DecisionStore: cannot open %s for append (error %d).",filename,GetLastError());return false;}
   FileSeek(handle,0,SEEK_END);uint written=FileWriteString(handle,line+"\r\n");if(written!=(uint)StringLen(line)+2){int err=GetLastError();FileClose(handle);PrintFormat("MedisTouch DecisionStore: short write to %s (error %d).",filename,err);return false;}FileFlush(handle);FileClose(handle);return true;
  }
int CDecisionStore::ReadLines(const string filename,string &lines[]){ArrayFree(lines);if(!FileIsExist(filename))return 0;int h=FileOpen(filename,FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ|FILE_SHARE_WRITE);if(h==INVALID_HANDLE)return 0;int n=0;while(!FileIsEnding(h)){string line=FileReadString(h);if(StringLen(line)==0)continue;ArrayResize(lines,n+1);lines[n++]=line;}FileClose(h);return n;}

string CDecisionStore::SerializeDecision(const TradeDecisionRecord &rec)
  {string p[13];p[0]=IntegerToString(rec.decision_id);p[1]=rec.symbol;p[2]=IntegerToString((int)rec.setup.type);p[3]=DoubleToString(rec.setup.entry_top,_Digits);p[4]=DoubleToString(rec.setup.entry_bottom,_Digits);p[5]=DoubleToString(rec.setup.stop_loss,_Digits);p[6]=DoubleToString(rec.setup.tp1,_Digits);p[7]=DoubleToString(rec.setup.tp2,_Digits);p[8]=DoubleToString(rec.setup.final_tp,_Digits);p[9]=DoubleToString(rec.setup.confidence,2);p[10]=IntegerToString((long)rec.decided_time);p[11]=IntegerToString((int)rec.action);p[12]=rec.reduce_risk?"1":"0";string line=p[0];for(int i=1;i<13;i++)line+=DECISION_CSV_SEP+p[i];return line;}
bool CDecisionStore::ParseDecision(const string line,TradeDecisionRecord &rec){string f[];int n=StringSplit(line,StringGetCharacter(DECISION_CSV_SEP,0),f);if(n<11)return false;ZeroMemory(rec);rec.decision_id=(long)StringToInteger(f[0]);rec.symbol=f[1];rec.setup.type=(ENUM_ORDER_TYPE)(int)StringToInteger(f[2]);rec.setup.entry_top=StringToDouble(f[3]);rec.setup.entry_bottom=StringToDouble(f[4]);rec.setup.stop_loss=StringToDouble(f[5]);rec.setup.tp1=StringToDouble(f[6]);rec.setup.tp2=StringToDouble(f[7]);rec.setup.final_tp=StringToDouble(f[8]);rec.setup.confidence=StringToDouble(f[9]);rec.setup.creation_time=(datetime)StringToInteger(f[10]);rec.setup.active=true;rec.confidence=rec.setup.confidence;rec.decided_time=rec.setup.creation_time;rec.action=(n>11)?(ENUM_TRADE_POLICY)(int)StringToInteger(f[11]):POLICY_EXECUTE_ONLY;rec.reduce_risk=(n>12&&f[12]=="1");rec.valid=true;rec.reason="restored from "+m_decisionsFile;return true;}
string CDecisionStore::SerializeExecution(const ExecutionRecord &rec){return IntegerToString(rec.decision_id)+DECISION_CSV_SEP+DoubleToString(rec.volume,2)+DECISION_CSV_SEP+IntegerToString((long)rec.ticket)+DECISION_CSV_SEP+IntegerToString((long)rec.submitted_time);}
bool CDecisionStore::ParseExecution(const string line,ExecutionRecord &rec){string f[];int n=StringSplit(line,StringGetCharacter(DECISION_CSV_SEP,0),f);if(n<3)return false;ZeroMemory(rec);rec.decision_id=(long)StringToInteger(f[0]);rec.volume=StringToDouble(f[1]);rec.ticket=(ulong)StringToInteger(f[2]);rec.submitted_time=(n>3)?(datetime)StringToInteger(f[3]):0;return true;}
void CDecisionStore::LoadFromDisk(){string lines[];int n=ReadLines(m_decisionsFile,lines);for(int i=0;i<n;i++){TradeDecisionRecord r;if(!ParseDecision(lines[i],r))continue;int k=ArraySize(m_decisions);ArrayResize(m_decisions,k+1);m_decisions[k]=r;}string el[];int m=ReadLines(m_executionsFile,el);for(int i=0;i<m;i++){ExecutionRecord r;if(!ParseExecution(el[i],r))continue;int k=ArraySize(m_executions);ArrayResize(m_executions,k+1);m_executions[k]=r;}}

// Persist first; only after a successful append does the in-memory mirror
// become authoritative. A failed disk write therefore cannot create a
// false "saved" state that disappears on restart.
bool CDecisionStore::Save(const TradeDecisionRecord &rec)
  {
   if(!rec.valid)return false;for(int i=0;i<ArraySize(m_decisions);i++)if(m_decisions[i].decision_id==rec.decision_id)return true;
   if(!AppendLine(m_decisionsFile,SerializeDecision(rec)))return false;int idx=ArraySize(m_decisions);ArrayResize(m_decisions,idx+1);m_decisions[idx]=rec;return true;
  }
bool CDecisionStore::SaveExecution(long decisionId,double volume,ulong ticket)
  {
   for(int i=0;i<ArraySize(m_executions);i++)if(m_executions[i].decision_id==decisionId&&m_executions[i].ticket==ticket)return true;
   ExecutionRecord rec;ZeroMemory(rec);rec.decision_id=decisionId;rec.volume=volume;rec.ticket=ticket;rec.submitted_time=TimeCurrent();
   if(!AppendLine(m_executionsFile,SerializeExecution(rec)))return false;int idx=ArraySize(m_executions);ArrayResize(m_executions,idx+1);m_executions[idx]=rec;return true;
  }
int CDecisionStore::LoadAll(TradeDecisionRecord &out[]){int n=ArraySize(m_decisions);ArrayResize(out,n);for(int i=0;i<n;i++)out[i]=m_decisions[i];return n;}
int CDecisionStore::LoadAllExecutions(ExecutionRecord &out[]){int n=ArraySize(m_executions);ArrayResize(out,n);for(int i=0;i<n;i++)out[i]=m_executions[i];return n;}
bool CDecisionStore::FindById(long decisionId,TradeDecisionRecord &out){for(int i=ArraySize(m_decisions)-1;i>=0;i--)if(m_decisions[i].decision_id==decisionId){out=m_decisions[i];return true;}return false;}
#endif
//+------------------------------------------------------------------+
