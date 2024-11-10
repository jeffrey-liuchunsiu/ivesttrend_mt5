
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

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
    EventSetTimer(1); // Set timer for connection check and heartbeat
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

    trade.SetExpertMagicNumber(123456);
    if (!trade.PositionOpen(symbol, order_type, volume, price, sl, tp))
    {
        Print("Error opening position: ", GetLastError());
        // Send error response to server
        string error_message = StringFormat("TRADE_EXECUTED:ERROR %s %s %.2f @ %.5f SL:%.5f TP:%.5f",
                                            symbol, action, volume, price, sl, tp);
        SendResponse(error_message);
    }
    else
    {
        Print("Order executed successfully");
        // Send success response to server
        string success_message = StringFormat("TRADE_EXECUTED:SUCCESS %s %s %.2f @ %.5f SL:%.5f TP:%.5f",
                                              symbol, action, volume, price, sl, tp);
        SendResponse(success_message);
    }
}

//+------------------------------------------------------------------+
//| Send response to server                                           |
//+------------------------------------------------------------------+
void SendResponse(string message)
{
    if (socket_connected)
    {
        uchar data[];
        StringToCharArray(message, data);
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