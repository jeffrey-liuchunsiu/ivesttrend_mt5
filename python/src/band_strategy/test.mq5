//+------------------------------------------------------------------+
//|                                              websocket_trader.mq5   |
//+------------------------------------------------------------------+
#property copyright "Your Name"
#property link "https://www.yourwebsite.com"
#property version "1.00"
#property strict

#include <Trade/Trade.mqh>

// WebSocket client settings
input string ServerAddress = "http://18.141.245.200:5000";
input int ReconnectSeconds = 5;
input int HeartbeatSeconds = 10;

// Global variables
CTrade trade;
int socket;
bool socket_connected = false;
datetime last_heartbeat;
string received_data;
string client_ip;
int client_magic;

// Add this with other input parameters at the top
input int CustomMagicNumber = 0; // Set to 0 for auto-generated magic number from IP

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
    client_ip = TerminalInfoString(TERMINAL_IP_ADDRESS);

    // Set magic number based on input or generate from IP
    if (CustomMagicNumber > 0)
    {
        client_magic = CustomMagicNumber;
    }
    else
    {
        // Auto-generate from IP
        string ip_parts[];
        StringSplit(client_ip, '.', ip_parts);
        client_magic = 1000000 + StringToInteger(ip_parts[3]);
    }

    Print("Using magic number: ", client_magic);
    Print("Client IP: ", client_ip);

    EventSetTimer(1);
    socket = SocketCreate();

    if (socket != INVALID_HANDLE)
    {
        Print("Socket created successfully");
        ConnectToServer();
    }
    else
    {
        Print("Failed to create socket, error: ", GetLastError());
        return INIT_FAILED;
    }

    return (INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    SocketClose(socket);
    EventKillTimer();
}

//+------------------------------------------------------------------+
//| Timer function                                                     |
//+------------------------------------------------------------------+
void OnTimer()
{
    // Check connection and reconnect if needed
    if (!socket_connected)
    {
        ConnectToServer();
        return;
    }

    // Send heartbeat
    if (TimeLocal() - last_heartbeat > HeartbeatSeconds)
    {
        SendHeartbeat();
    }

    static datetime last_positions_update = 0;
    if (TimeLocal() - last_positions_update > 60)
    {
        SendPositionsUpdate();
        SendHistoryUpdate(); // Add history update
        last_positions_update = TimeLocal();
    }
}

//+------------------------------------------------------------------+
//| Connect to WebSocket server                                        |
//+------------------------------------------------------------------+
void ConnectToServer()
{
    if (SocketConnect(socket, ServerAddress, 5000, 1000))
    {
        Print("Connected to server");
        socket_connected = true;
        last_heartbeat = TimeLocal();
    }
    else
    {
        Print("Connection failed, error: ", GetLastError());
        socket_connected = false;
    }
}

//+------------------------------------------------------------------+
//| Send heartbeat to server                                          |
//+------------------------------------------------------------------+
void SendHeartbeat()
{
    if (socket_connected)
    {
        datetime end_time = TimeCurrent();
        datetime start_time = end_time - PeriodSeconds(PERIOD_D1); // Last 24 hours

        HistorySelect(start_time, end_time);
        int total = HistoryDealsTotal();
        string history_msg = "HISTORY_UPDATE:";

        for (int i = 0; i < total; i++)
        {
            ulong ticket = HistoryDealGetTicket(i);
            if (HistoryDealGetInteger(ticket, DEAL_MAGIC) == client_magic)
            {
                history_msg += StringFormat("ticket=%llu,symbol=%s,type=%s,volume=%.2f,price=%.5f,profit=%.2f,time=%s;",
                                            ticket,
                                            HistoryDealGetString(ticket, DEAL_SYMBOL),
                                            HistoryDealGetInteger(ticket, DEAL_TYPE) == DEAL_TYPE_BUY ? "BUY" : "SELL",
                                            HistoryDealGetDouble(ticket, DEAL_VOLUME),
                                            HistoryDealGetDouble(ticket, DEAL_PRICE),
                                            HistoryDealGetDouble(ticket, DEAL_PROFIT),
                                            TimeToString(HistoryDealGetInteger(ticket, DEAL_TIME)));
            }
        }

        if (history_msg != "HISTORY_UPDATE:")
        {
            uchar data[];
            StringToCharArray(history_msg, data);
            if (SocketSend(socket, data, ArraySize(data)))
            {
                last_heartbeat = TimeLocal();
            }
            else
            {
                socket_connected = false;
            }
        }
        else
        {
            last_heartbeat = TimeLocal(); // Update heartbeat even if no history to send
        }
    }
}

//+------------------------------------------------------------------+
//| Execute trade based on received order                             |
//+------------------------------------------------------------------+
void ExecuteOrder(string message)
{
    // Expected format: "SYMBOL,TYPE,VOLUME,SL,TP"
    string parts[];
    int split = StringSplit(message, ',', parts);

    if (split != 5)
    {
        Print("Invalid order format");
        return;
    }

    string symbol = parts[0];
    string action = parts[1];
    double volume = StringToDouble(parts[2]);
    double sl = StringToDouble(parts[3]);
    double tp = StringToDouble(parts[4]);

    ENUM_ORDER_TYPE order_type;
    if (action == "BUY")
        order_type = ORDER_TYPE_BUY;
    else if (action == "SELL")
        order_type = ORDER_TYPE_SELL;
    else
    {
        Print("Invalid order type: ", action);
        return;
    }

    MqlTick last_tick;
    if (!SymbolInfoTick(symbol, last_tick))
    {
        Print("Failed to get tick data for ", symbol);
        return;
    }

    double price = (order_type == ORDER_TYPE_BUY) ? last_tick.ask : last_tick.bid;

    trade.SetExpertMagicNumber(client_magic);
    if (!trade.PositionOpen(symbol, order_type, volume, price, sl, tp))
    {
        Print("Error opening position: ", GetLastError());
        string error_msg = "TRADE_ERROR:" + IntegerToString(GetLastError());
        uchar data[];
        StringToCharArray(error_msg, data);
        SocketSend(socket, data, ArraySize(data));
    }
    else
    {
        Print("Order executed successfully");
        string trade_msg = StringFormat("TRADE_EXECUTED:symbol=%s,type=%s,volume=%.2f,price=%.5f,sl=%.5f,tp=%.5f,magic=%d",
                                        symbol, action, volume, price, sl, tp, client_magic);
        uchar data[];
        StringToCharArray(trade_msg, data);
        SocketSend(socket, data, ArraySize(data));
    }
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
    if (!socket_connected)
        return;

    uchar rec_buffer[];
    uint size = SocketIsReadable(socket);

    if (size > 0)
    {
        ArrayResize(rec_buffer, size);
        int bytes_read = SocketRead(socket, rec_buffer, size, 1000);

        if (bytes_read > 0)
        {
            string message = CharArrayToString(rec_buffer);
            Print("Received message: ", message);

            if (message != "CONNECTION_ESTABLISHED" && message != "HEARTBEAT")
            {
                ExecuteOrder(message);
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Send current positions to server                                 |
//+------------------------------------------------------------------+
void SendPositionsUpdate()
{
    int total = PositionsTotal();
    string positions_msg = "POSITIONS_UPDATE:";

    for (int i = 0; i < total; i++)
    {
        ulong ticket = PositionGetTicket(i);
        if (PositionSelectByTicket(ticket))
        {
            if (PositionGetInteger(POSITION_MAGIC) == client_magic)
            {
                positions_msg += StringFormat("ticket=%llu,symbol=%s,type=%s,volume=%.2f,price=%.5f,sl=%.5f,tp=%.5f,profit=%.2f;",
                                              ticket,
                                              PositionGetString(POSITION_SYMBOL),
                                              PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "BUY" : "SELL",
                                              PositionGetDouble(POSITION_VOLUME),
                                              PositionGetDouble(POSITION_PRICE_OPEN),
                                              PositionGetDouble(POSITION_SL),
                                              PositionGetDouble(POSITION_TP),
                                              PositionGetDouble(POSITION_PROFIT));
            }
        }
    }

    if (positions_msg != "POSITIONS_UPDATE:")
    {
        uchar data[];
        StringToCharArray(positions_msg, data);
        SocketSend(socket, data, ArraySize(data));
    }
}

//+------------------------------------------------------------------+
//| Send trade history to server                                     |
//+------------------------------------------------------------------+
void SendHistoryUpdate()
{
    datetime end_time = TimeCurrent();
    datetime start_time = end_time - PeriodSeconds(PERIOD_D1) * 7; // Last 7 days for more history

    if (!HistorySelect(start_time, end_time))
    {
        Print("Failed to select history");
        return;
    }

    int total = HistoryDealsTotal();
    string history_msg = "HISTORY_UPDATE:";

    Print("Processing ", total, " historical deals for magic number: ", client_magic);

    for (int i = 0; i < total; i++)
    {
        ulong ticket = HistoryDealGetTicket(i);
        if (ticket > 0)
        {
            long deal_magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
            Print("Checking deal ticket: ", ticket, " with magic: ", deal_magic);

            if (deal_magic == client_magic)
            {
                string deal_type = (HistoryDealGetInteger(ticket, DEAL_TYPE) == DEAL_TYPE_BUY) ? "BUY" : "SELL";
                string deal_entry = (HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_IN) ? "IN" : "OUT";

                string deal_info = StringFormat("ticket=%llu,symbol=%s,type=%s,entry=%s,volume=%.2f,price=%.5f,profit=%.2f,time=%s;",
                                                ticket,
                                                HistoryDealGetString(ticket, DEAL_SYMBOL),
                                                deal_type,
                                                deal_entry,
                                                HistoryDealGetDouble(ticket, DEAL_VOLUME),
                                                HistoryDealGetDouble(ticket, DEAL_PRICE),
                                                HistoryDealGetDouble(ticket, DEAL_PROFIT),
                                                TimeToString((datetime)HistoryDealGetInteger(ticket, DEAL_TIME)));

                Print("Adding deal to history: ", deal_info);
                history_msg += deal_info;
            }
        }
    }

    if (history_msg != "HISTORY_UPDATE:")
    {
        Print("Sending history update: ", history_msg);
        uchar data[];
        StringToCharArray(history_msg, data);
        if (!SocketSend(socket, data, ArraySize(data)))
        {
            Print("Failed to send history update");
        }
    }
    else
    {
        Print("No historical deals found for magic number: ", client_magic);
    }
}