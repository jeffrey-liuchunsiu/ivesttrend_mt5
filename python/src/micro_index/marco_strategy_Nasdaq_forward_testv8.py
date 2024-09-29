import os
import time
from datetime import datetime, timedelta
import requests
import pandas as pd
import schedule
from dotenv import load_dotenv, find_dotenv
from mt5linux import MetaTrader5
import sys
import csv

# Load environment variables
load_dotenv(find_dotenv())

# Define parameters
SYMBOL = "QQQ.US"
LOT_SIZE = 1.0
STOP_LOSS_PERCENTAGE = 0.10
CPI_RISE_THRESHOLD = 0.03

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

def execute_trade():
    symbol_info = mt5.symbol_info(SYMBOL)
    if symbol_info is None:
        print(f"{SYMBOL} not found.")
        return

    if not symbol_info.visible:
        print(f"{SYMBOL} is not visible, trying to switch on")
        if not mt5.symbol_select(SYMBOL, True):
            print(f"Failed to select {SYMBOL}")
            return

    price = mt5.symbol_info_tick(SYMBOL).ask
    sl = price - (price * STOP_LOSS_PERCENTAGE)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT_SIZE,
        "type": mt5.ORDER_TYPE_BUY,
        "price": price,
        "sl": sl,
        "deviation": 20,
        "comment": "Buy order",
        "type_time": mt5.ORDER_TIME_GTC,
        "magic": 80001234,
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
            10031: "No connection with the trade server",
            10032: "Operation is allowed only for live accounts",
        }
        reason = error_messages.get(result.retcode, "Unknown error")
        print(f"Order failed, retcode={result.retcode}, reason={reason}")
        log_trade("BUY", price, 0, "FAILED", reason)
    else:
        print(f"Order succeeded, retcode={result.retcode}")
        log_trade("BUY", price, result.order, "SUCCESS")
        return result.order

def close_open_position(ticket: int) -> None:
    """
    Closes an open trading position.

    Parameters:
    ticket (int): The ticket number of the position to close.
    
    Returns:
    None
    """
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "position": ticket,
        "volume": LOT_SIZE,
        "type": mt5.ORDER_TYPE_SELL,
        "price": mt5.symbol_info_tick(SYMBOL).bid,
        "deviation": 20,
        "comment": "Close position",
        "type_filling": mt5.ORDER_FILLING_IOC,
        "type_time": mt5.ORDER_TIME_GTC,
    }
    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to close order. The failure code is: {result.retcode}")
        log_trade("SELL", mt5.symbol_info_tick(SYMBOL).bid, ticket, "FAILED", f"Failure code: {result.retcode}")
    else:
        print("Order successfully closed!")
        log_trade("SELL", mt5.symbol_info_tick(SYMBOL).bid, ticket, "SUCCESS")

def get_csv_file_path(filename: str) -> str:
    """
    Returns the full path to a CSV file located in the script directory.

    Parameters:
    filename (str): The name of the CSV file.

    Returns:
    str: The full path to the CSV file.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, filename)

def download_and_process_CPI_excel(url: str, sheet_name: str) -> pd.DataFrame:
    """
    Downloads and processes CPI data from an Excel file.

    Parameters:
    url (str): The URL of the Excel file containing CPI data.
    sheet_name (str): The name of the sheet in the Excel file to process.

    Returns:
    DataFrame: A pandas DataFrame containing the processed CPI data with columns 'DATE' and 'CORESTICKM159SFRBATL'.
    """
    df = pd.read_excel(url, sheet_name=sheet_name)
    df = df.iloc[:, [0, 16]]
    df = df.rename(columns={"Date": "DATE", "12mo.3": "CORESTICKM159SFRBATL"})
    df['DATE'] = pd.to_datetime(df['DATE']).dt.strftime('%Y-%m-%d')
    df = df[["DATE", "CORESTICKM159SFRBATL"]].reset_index(drop=True)
    return df[df["CORESTICKM159SFRBATL"] != "na"]

def save_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves the given DataFrame to a CSV file at the specified file path.

    Parameters:
    df (pd.DataFrame): The DataFrame to save.
    file_path (str): The path where the CSV file will be saved.
    """
    df.to_csv(file_path, index=False)

def download_unrate_csv() -> None:
    """
    Downloads the unemployment rate (UNRATE) data from the FRED website and saves it as a CSV file.

    Returns:
    None
    """
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?bgcolor=%23e1e9f0&chart_type=line&drp=0&fo=open%20sans&graph_bgcolor=%23ffffff&height=450&mode=fred&recession_bars=on&txtcolor=%23444444&ts=12&tts=12&width=1320&nt=0&thu=0&trc=0&show_legend=yes&show_axis_titles=yes&show_tooltip=yes&id=UNRATE&scale=left&cosd=1948-01-01&coed={yesterday}&line_color=%234572a7&link_values=false&line_style=solid&mark_type=none&mw=3&lw=2&ost=-99999&oet=99999&mma=0&fml=a&fq=Monthly&fam=avg&fgst=lin&fgsnd=2020-02-01&line_index=1&transformation=lin&vintage_date={yesterday}&revision_date={yesterday}&nd=1948-01-01"
    
    response = requests.get(url)
    if response.status_code == 200:
        unrate_file_path = get_csv_file_path('UNRATE.csv')
        with open(unrate_file_path, 'wb') as f:
            f.write(response.content)
        print(f"UNRATE.csv downloaded successfully to {unrate_file_path}")
    else:
        print(f"Failed to download UNRATE.csv. Status code: {response.status_code}")

def process_unrate_csv() -> pd.DataFrame:
    """
    Processes the unemployment rate (UNRATE) CSV file.

    Returns:
    pd.DataFrame: A pandas DataFrame containing the processed unemployment rate data.
    """
    unrate_file_path = get_csv_file_path('UNRATE.csv')
    df = pd.read_csv(unrate_file_path)
    return df

def log_trade(action: str, price: float, ticket: int, status: str, reason: str = "") -> None:
    """
    Logs trade information to a CSV file.

    Parameters:
    action (str): The trade action (BUY or SELL).
    price (float): The price at which the trade was executed.
    ticket (int): The ticket number of the trade.
    status (str): The status of the trade (SUCCESS or FAILED).
    reason (str, optional): The reason for failure if the trade failed.

    Returns:
    None
    """
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
    """
    Checks the current market conditions based on CPI and unemployment rate data,
    and executes trades based on predefined entry and exit conditions.

    Returns:
    None
    """
    global in_position, ticket

    # Download, process, and save CPI data
    csv_file_path = get_csv_file_path('CORESTICKM159SFRBATL.csv')
    url = "https://www.atlantafed.org/-/media/documents/datafiles/research/inflationproject/stickprice/stickyprice.xlsx"
    df = download_and_process_CPI_excel(url, "Data")
    save_to_csv(df, csv_file_path)

    # Download and process unemployment rate data
    download_unrate_csv()
    process_unrate_csv()

    # Get historical data
    cpi_file_path = get_csv_file_path('CORESTICKM159SFRBATL.csv')
    unrate_file_path = get_csv_file_path('UNRATE.csv')
    cpi_data = pd.read_csv(cpi_file_path, parse_dates=['DATE'])
    unrate_data = pd.read_csv(unrate_file_path, parse_dates=['DATE'])

    # Calculate rolling averages
    unrate_data['Rolling_Avg'] = unrate_data['UNRATE'].rolling(window=6).mean()
    cpi_data['Rolling_Avg'] = cpi_data['CORESTICKM159SFRBATL'].rolling(window=6).mean()

    latest_date = unrate_data['DATE'].iloc[-1]
    unrate_rolling_avg = unrate_data['Rolling_Avg'].iloc[-1]
    cpi_row = cpi_data[cpi_data['DATE'] == latest_date]

    if not cpi_row.empty:
        cpi_rolling_avg = cpi_row.iloc[0]['Rolling_Avg']
        cpi_pct_change = cpi_row['Rolling_Avg'].pct_change().iloc[-1]

        entry_condition_1 = (unrate_rolling_avg < unrate_data.iloc[-2]['Rolling_Avg']) and (
            cpi_rolling_avg < cpi_data.iloc[-2]['Rolling_Avg'])
        entry_condition_2 = (unrate_rolling_avg > unrate_data.iloc[-2]['Rolling_Avg']) and (
            cpi_pct_change <= -CPI_RISE_THRESHOLD)
        exit_condition = (cpi_pct_change >= CPI_RISE_THRESHOLD)

        print(f"entry_condition_1: {entry_condition_1}")
        print(f"entry_condition_2: {entry_condition_2}")
        print(f"exit_condition: {exit_condition}")

        if (entry_condition_1 or entry_condition_2) and not in_position:
            ticket = execute_trade()
            in_position = True

        if in_position and exit_condition:
            close_open_position(ticket)
            in_position = False

def main():
    while True:
        try:
            if not start_mt5():
                print("Failed to start MT5. Retrying in 10 seconds...")
                time.sleep(10)
                continue

            # Schedule the task every minute
            schedule.every(1).minutes.do(check_market_conditions)

            global ticket, in_position
            ticket = execute_trade()
            in_position = True if ticket is not None else False
            if ticket is not None:
                print(f"Initial trade executed with ticket: {ticket}")

            # Run the scheduler
            while True:
                schedule.run_pending()
                time.sleep(1)

        except KeyboardInterrupt:
            print("Script terminated by user")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            print("Restarting the script in 10 seconds...")
            time.sleep(10)
        finally:
            # Shutdown MT5 connection
            mt5.shutdown()

if __name__ == "__main__":
    main()
