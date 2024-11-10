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
        if (ConnectToServer())
        {
            // Send initial history update after successful connection
            ForceHistoryUpdate();
        }
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
        string heartbeat = "HEARTBEAT";
        uchar data[];
        StringToCharArray(heartbeat, data);
        if (SocketSend(socket, data, ArraySize(data)))
        {
            last_heartbeat = TimeLocal();
        }
        else
        {
            socket_connected = false;
        }
    }

    // Send positions and history updates every minute
    static datetime last_updates = 0;
    if (TimeLocal() - last_updates > 60) // Every 60 seconds
    {
        Print("Sending periodic updates...");
        SendPositionsUpdate();
        SendHistoryUpdate();
        last_updates = TimeLocal();
    }
}

//+------------------------------------------------------------------+
//| Connect to WebSocket server                                        |
//+------------------------------------------------------------------+
bool ConnectToServer()
{
    if (SocketConnect(socket, ServerAddress, 5000, 1000))
    {
        Print("Connected to server");
        socket_connected = true;
        last_heartbeat = TimeLocal();

        // Send initial connection message
        string connect_msg = "CONNECTION_ESTABLISHED";
        uchar connect_data[];
        StringToCharArray(connect_msg, connect_data);
        SocketSend(socket, connect_data, ArraySize(connect_data));

        // Send immediate history update
        Print("Sending initial history update...");
        SendHistoryUpdate();
        return true;
    }
    else
    {
        Print("Connection failed, error: ", GetLastError());
        socket_connected = false;
        return false;
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
    datetime start_time = end_time - PeriodSeconds(PERIOD_D1) * 30; // Last 30 days for more history

    Print("Fetching history from ", TimeToString(start_time), " to ", TimeToString(end_time));

    if (!HistorySelect(start_time, end_time))
    {
        Print("Failed to select history");
        return;
    }

    int total = HistoryDealsTotal();
    string history_msg = "HISTORY_UPDATE:";
    int deals_found = 0;

    Print("Processing ", total, " historical deals");

    for (int i = 0; i < total; i++)
    {
        ulong ticket = HistoryDealGetTicket(i);
        if (ticket > 0)
        {
            // Include all trades regardless of magic number for complete history
            deals_found++;
            string deal_type = (HistoryDealGetInteger(ticket, DEAL_TYPE) == DEAL_TYPE_BUY) ? "BUY" : "SELL";
            string deal_entry = (HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_IN) ? "IN" : "OUT";
            string symbol = HistoryDealGetString(ticket, DEAL_SYMBOL);
            double volume = HistoryDealGetDouble(ticket, DEAL_VOLUME);
            double price = HistoryDealGetDouble(ticket, DEAL_PRICE);
            double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
            datetime deal_time = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
            long deal_magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
            string deal_comment = HistoryDealGetString(ticket, DEAL_COMMENT);

            string deal_info = StringFormat(
                "ticket=%llu,symbol=%s,type=%s,entry=%s,volume=%.2f,price=%.5f,profit=%.2f,time=%s,magic=%d,comment=%s;",
                ticket, symbol, deal_type, deal_entry, volume, price, profit,
                TimeToString(deal_time), deal_magic, deal_comment);

            Print("Adding deal to history: ", deal_info);
            history_msg += deal_info;
        }
    }

    Print("Found ", deals_found, " total deals");

    if (deals_found > 0)
    {
        Print("Sending history update with ", deals_found, " deals");
        uchar data[];
        StringToCharArray(history_msg, data);
        if (!SocketSend(socket, data, ArraySize(data)))
        {
            Print("Failed to send history update");
        }
        else
        {
            Print("History update sent successfully");
        }
    }
    else
    {
        Print("No historical deals found");
    }
}

// Add this function to force a history update
void ForceHistoryUpdate()
{
    Print("Forcing history update...");
    SendHistoryUpdate();
}