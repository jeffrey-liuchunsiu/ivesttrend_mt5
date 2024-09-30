import os
import time
from datetime import datetime, timedelta
import requests
import pandas as pd
import numpy as np
import schedule
from dotenv import load_dotenv, find_dotenv
from mt5linux import MetaTrader5
import sys
import csv

# Load environment variables
load_dotenv(find_dotenv())

# Define parameters
SYMBOL = "EURUSD"
LOT_SIZE = 1
STOP_LOSS_PIPS = 50
TAKE_PROFIT_PIPS = 140
BAND_PERIOD = 20
BAND_DEVIATION = 2

# MT5 connection parameters
MT5_HOST = '18.141.245.200'
MT5_PORT = 18812
MT5_USERNAME = os.getenv('mt5_username')
MT5_PASSWORD = os.getenv('mt5_password')
MT5_SERVER = 'Pepperstone-Demo'
MT5_PATH = "/home/ubuntu/.wine/drive_c/Program Files/Pepperstone MetaTrader 5/terminal64.exe"

# Initialize MT5 connection
mt5 = MetaTrader5(host=MT5_HOST, port=MT5_PORT)

# Global variables
in_position = False
ticket = None

def start_mt5():
    if mt5.initialize(login=int(MT5_USERNAME), password=str(MT5_PASSWORD), server=MT5_SERVER, path=MT5_PATH):
        if mt5.login(login=int(MT5_USERNAME), password=str(MT5_PASSWORD), server=MT5_SERVER):
            print("Login Success")
            return True
        else:
            print("Login Failed")
            return False
    else:
        print("MT5 Initialization Failed")
        return False

def execute_trade(order_type):
    symbol_info = mt5.symbol_info(SYMBOL)
    if symbol_info is None:
        print(f"{SYMBOL} not found.")
        return

    if not symbol_info.visible:
        print(f"{SYMBOL} is not visible, trying to switch on")
        if not mt5.symbol_select(SYMBOL, True):
            print(f"Failed to select {SYMBOL}")
            return

    point = symbol_info.point

    if order_type == mt5.ORDER_TYPE_BUY:
        price = mt5.symbol_info_tick(SYMBOL).ask
        sl = price - STOP_LOSS_PIPS * point
        tp = price + TAKE_PROFIT_PIPS * point
    else:
        price = mt5.symbol_info_tick(SYMBOL).bid
        sl = price + STOP_LOSS_PIPS * point
        tp = price - TAKE_PROFIT_PIPS * point

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT_SIZE,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 80001235,
        "comment": "Band strategy",
        "type_time": mt5.ORDER_TIME_GTC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        error_messages = {
            10004: "Requote",
            10006: "Request rejected",
            10007: "Request canceled by trader",
            10011: "Request processing error",
            10012: "Request canceled by timeout",
            10013: "Invalid request",
            10014: "Invalid volume in the request",
            10015: "Invalid price in the request",
            10016: "Invalid stops in the request",
            10017: "Trade is disabled",
            10018: "Market is closed",
            10019: "Not enough money to complete the request",
            10020: "Prices changed",
            10021: "No quotes to process the request",
            10022: "Invalid order expiration date in the request",
            10024: "Too frequent requests",
            10026: "Autotrading disabled by server",
            10027: "Autotrading disabled by client terminal",
            10030: "Invalid volume",
            10031: "No connection with the trade server",
            10032: "Operation is allowed only for live accounts",
        }
        reason = error_messages.get(result.retcode, "Unknown error")
        print(f"Order failed, retcode={result.retcode}, reason={reason}")
        log_trade("BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL", price, 0, "FAILED", reason)
    else:
        print(f"Order succeeded, retcode={result.retcode}")
        log_trade("BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL", price, result.order, "SUCCESS")
        return result.order

def close_open_position(ticket: int) -> None:
    position = mt5.positions_get(ticket=ticket)
    if position:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": SYMBOL,
            "volume": position[0].volume,
            "type": mt5.ORDER_TYPE_BUY if position[0].type == 1 else mt5.ORDER_TYPE_SELL,
            "price": mt5.symbol_info_tick(SYMBOL).ask if position[0].type == 1 else mt5.symbol_info_tick(SYMBOL).bid,
            "deviation": 20,
            "magic": 80001235,
            "comment": "Close position",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Failed to close order. The failure code is: {result.retcode}")
            log_trade("CLOSE", request["price"], ticket, "FAILED", f"Failure code: {result.retcode}")
        else:
            print("Order successfully closed!")
            log_trade("CLOSE", request["price"], ticket, "SUCCESS")
    else:
        print(f"Position with ticket {ticket} not found.")

def get_csv_file_path(filename: str) -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, filename)

def log_trade(action: str, price: float, ticket: int, status: str, reason: str = "") -> None:
    log_file_path = get_csv_file_path('trade_log.csv')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if not os.path.exists(log_file_path):
        with open(log_file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Timestamp', 'Action', 'Price', 'Ticket', 'Status', 'Reason'])

    with open(log_file_path, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, action, price, ticket, status, reason])

def check_market_conditions() -> None:
    global in_position, ticket

    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, BAND_PERIOD + 1)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    df['SMA'] = df['close'].rolling(window=BAND_PERIOD).mean()
    df['STD'] = df['close'].rolling(window=BAND_PERIOD).std()
    df['Upper'] = df['SMA'] + (BAND_DEVIATION * df['STD'])
    df['Lower'] = df['SMA'] - (BAND_DEVIATION * df['STD'])

    current_price = mt5.symbol_info_tick(SYMBOL).ask
    upper_band = df['Upper'].iloc[-1]
    lower_band = df['Lower'].iloc[-1]

    print(f"Current price: {current_price}")
    print(f"Upper band: {upper_band}")
    print(f"Lower band: {lower_band}")

    if not in_position:
        if current_price > upper_band:
            print("Price above upper band, selling")
            ticket = execute_trade(mt5.ORDER_TYPE_SELL)
            in_position = True if ticket else False
        elif current_price < lower_band:
            print("Price below lower band, buying")
            ticket = execute_trade(mt5.ORDER_TYPE_BUY)
            in_position = True if ticket else False
    else:
        position = mt5.positions_get(ticket=ticket)
        if position:
            if (position[0].type == mt5.POSITION_TYPE_BUY and current_price > upper_band) or \
               (position[0].type == mt5.POSITION_TYPE_SELL and current_price < lower_band):
                print("Closing position")
                close_open_position(ticket)
                in_position = False
                ticket = None
        else:
            print(f"Position with ticket {ticket} not found. Resetting position status.")
            in_position = False
            ticket = None

def main():
    while True:
        try:
            if not start_mt5():
                print("Failed to start MT5. Retrying in 10 seconds...")
                time.sleep(10)
                continue

            while True:
                check_market_conditions()
                time.sleep(60)  # Wait for 1 minute before checking again

        except KeyboardInterrupt:
            print("Script terminated by user")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            print("Restarting the script in 10 seconds...")
            time.sleep(10)
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    main()
