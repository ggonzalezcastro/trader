//+------------------------------------------------------------------+
//|  FxGerardClient.mq5                                              |
//|  Thin client: conecta a Python host por TCP socket               |
//|  Recibe JSON commands; envia ticks + acks.                       |
//+------------------------------------------------------------------+
#property strict
#include <Trade\Trade.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Trade\PositionInfo.mqh>

input string  HostIP         = "127.0.0.1";
input ushort  HostPort       = 5555;
input ulong   DefaultMagic   = 50001;
input int     ReconnectMs    = 2000;
input int     HeartbeatSec   = 5;
input bool    LocalTrailing  = true;
input double  TrailATRmult   = 1.5;
input double  BreakevenAtR   = 0.5;

CTrade        trade;
CSymbolInfo   sym;
CPositionInfo pos;
int           sock = INVALID_HANDLE;
datetime      lastHB = 0;
ulong         seq = 0;
bool          connected = false;
datetime      lastCmdTime = 0;

int OnInit(){
   sym.Name(_Symbol);
   trade.SetExpertMagicNumber(DefaultMagic);
   trade.SetDeviationInPoints(20);
   trade.SetTypeFillingBySymbol(_Symbol);
   EventSetTimer(1);
   Print("FxGerardClient iniciado. Conectando a ", HostIP, ":", HostPort);
   ConnectSock();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason){
   EventKillTimer();
   CloseSock();
   Print("FxGerardClient detenido. Razon: ", reason);
}

bool ConnectSock(){
   if(sock != INVALID_HANDLE) SocketClose(sock);
   sock = SocketCreate();
   if(sock == INVALID_HANDLE){
      Print("SocketCreate error: ", GetLastError());
      return false;
   }
   if(!SocketConnect(sock, HostIP, HostPort, 1000)){
      Print("SocketConnect error: ", GetLastError());
      SocketClose(sock);
      sock = INVALID_HANDLE;
      return false;
   }
   connected = true;
   string hello = "{\"type\":\"hello\",\"symbol\":\""+_Symbol+"\",\"magic\":"+IntegerToString(DefaultMagic)+"}";
   SendJson(hello);
   Print("Conectado a Python host");
   return true;
}

void CloseSock(){
   if(sock != INVALID_HANDLE){
      SocketClose(sock);
      sock = INVALID_HANDLE;
      connected = false;
   }
}

bool SendJson(string s){
   if(sock == INVALID_HANDLE) return false;
   string line = s + "\n";
   uchar buf[];
   StringToCharArray(line, buf, 0, StringLen(line), CP_UTF8);
   int sent = SocketSend(sock, buf, ArraySize(buf) - 1);
   return sent > 0;
}

void OnTick(){
   if(!connected || sock == INVALID_HANDLE){
      ConnectSock();
      return;
   }
   sym.RefreshRates();
   string tick = StringFormat(
      "{\"type\":\"tick\",\"seq\":%I64u,\"sym\":\"%s\",\"bid\":%.5f,\"ask\":%.5f,\"t\":%I64u}",
      ++seq, _Symbol, sym.Bid(), sym.Ask(), (long)TimeCurrent()
   );
   SendJson(tick);
   PollCommands();
   if(LocalTrailing) ManageLocalTrailing();
}

void OnTimer(){
   if(TimeCurrent() - lastHB >= HeartbeatSec){
      SendJson("{\"type\":\"hb\",\"t\":"+IntegerToString((long)TimeCurrent())+"}");
      lastHB = TimeCurrent();
   }
   if(!connected) ConnectSock();
}

void PollCommands(){
   if(sock == INVALID_HANDLE) return;
   if(!SocketIsReadable(sock)) return;

   uchar buf[8192];
   int n = SocketRead(sock, buf, 8192, 100);
   if(n <= 0) return;

   string s = CharArrayToString(buf, 0, n, CP_UTF8);
   string lines[];
   int cnt = StringSplit(s, '\n', lines);

   for(int i = 0; i < cnt; i++){
      string ln = lines[i];
      if(StringLen(ln) < 3) continue;
      DispatchCmd(ln);
   }
}

void DispatchCmd(string js){
   lastCmdTime = TimeCurrent();

   if(StringFind(js, "\"op\":\"open\"") >= 0){
      DispatchOpen(js);
   }
   else if(StringFind(js, "\"op\":\"close\"") >= 0){
      DispatchClose(js);
   }
   else if(StringFind(js, "\"op\":\"modify\"") >= 0){
      DispatchModify(js);
   }
   else if(StringFind(js, "\"op\":\"close_all\"") >= 0){
      DispatchCloseAll(js);
   }
   else if(StringFind(js, "\"op\":\"ping\"") >= 0){
      DispatchPing(js);
   }
}

void DispatchOpen(string js){
   string sym2   = JsonStr(js, "symbol");
   string side   = JsonStr(js, "side");
   double vol    = JsonNum(js, "volume");
   double sl     = JsonNum(js, "sl");
   double tp     = JsonNum(js, "tp");
   ulong  mg     = (ulong)JsonNum(js, "magic");
   string cmt    = JsonStr(js, "comment");
   ulong  req_id = (ulong)JsonNum(js, "req_id");

   trade.SetExpertMagicNumber(mg);
   bool ok = false;
   if(side == "buy"){
      ok = trade.Buy(vol, sym2, 0.0, sl, tp, cmt);
   } else {
      ok = trade.Sell(vol, sym2, 0.0, sl, tp, cmt);
   }

   string ack = StringFormat(
      "{\"type\":\"ack\",\"req_id\":%I64u,\"ok\":%s,\"ticket\":%I64u,\"retcode\":%u}",
      req_id, ok ? "true" : "false", trade.ResultOrder(), trade.ResultRetcode()
   );
   SendJson(ack);
}

void DispatchClose(string js){
   ulong ticket = (ulong)JsonNum(js, "ticket");
   ulong req_id = (ulong)JsonNum(js, "req_id");

   bool ok = trade.PositionClose(ticket);

   string ack = StringFormat(
      "{\"type\":\"ack\",\"req_id\":%I64u,\"ok\":%s}",
      req_id, ok ? "true" : "false"
   );
   SendJson(ack);
}

void DispatchModify(string js){
   ulong ticket = (ulong)JsonNum(js, "ticket");
   double sl    = JsonNum(js, "sl");
   double tp    = JsonNum(js, "tp");
   ulong req_id = (ulong)JsonNum(js, "req_id");

   bool ok = trade.PositionModify(ticket, sl, tp);

   string ack = StringFormat(
      "{\"type\":\"ack\",\"req_id\":%I64u,\"ok\":%s}",
      req_id, ok ? "true" : "false"
   );
   SendJson(ack);
}

void DispatchCloseAll(string js){
   ulong mg = (ulong)JsonNum(js, "magic");
   string reason = JsonStr(js, "reason");
   ulong req_id = (ulong)JsonNum(js, "req_id");

   int closed = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--){
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() != _Symbol) continue;
      if(mg > 0 && pos.Magic() != mg) continue;

      if(trade.PositionClose(pos.Ticket())) closed++;
   }

   string ack = StringFormat(
      "{\"type\":\"ack\",\"req_id\":%I64u,\"ok\":true,\"closed\":%d,\"reason\":\"%s\"}",
      req_id, closed, reason
   );
   SendJson(ack);
}

void DispatchPing(string js){
   ulong req_id = (ulong)JsonNum(js, "req_id");
   string pong = "{\"type\":\"pong\",\"req_id\":"+IntegerToString(req_id)+"}";
   SendJson(pong);
}

void ManageLocalTrailing(){
   double atr = iATR(_Symbol, PERIOD_M5, 14);

   for(int i = PositionsTotal() - 1; i >= 0; i--){
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() != _Symbol) continue;
      if(pos.Magic() < 50000 || pos.Magic() > 59999) continue;

      double newSL = 0;
      if(pos.PositionType() == POSITION_TYPE_BUY){
         newSL = sym.Bid() - atr * TrailATRmult;
         if(newSL > pos.StopLoss() && newSL > pos.PriceOpen()){
            trade.PositionModify(pos.Ticket(), newSL, pos.TakeProfit());
         }
      } else {
         newSL = sym.Ask() + atr * TrailATRmult;
         if(newSL < pos.StopLoss() && newSL < pos.PriceOpen()){
            trade.PositionModify(pos.Ticket(), newSL, pos.TakeProfit());
         }
      }
   }
}

string JsonStr(string js, string key){
   string k = "\""+key+"\":\"";
   int pos = StringFind(js, k);
   if(pos < 0) return "";
   pos += StringLen(k);
   int end = StringFind(js, "\"", pos);
   if(end < 0) return "";
   return StringSubstr(js, pos, end - pos);
}

double JsonNum(string js, string key){
   string k = "\""+key+"\":";
   int pos = StringFind(js, k);
   if(pos < 0) return 0;
   pos += StringLen(k);
   int end = pos;
   while(end < StringLen(js) && (StringGetCharacter(js, end) >= '0' || StringGetCharacter(js, end) == '.' || StringGetCharacter(js, end) == '-')){
      end++;
   }
   string num = StringSubstr(js, pos, end - pos);
   return StringToDouble(num);
}