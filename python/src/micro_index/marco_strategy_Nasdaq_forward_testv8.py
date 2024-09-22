import os
import time
from datetime import datetime, timedelta
import requests
import pandas as pd
import schedule
from dotenv import load_dotenv, find_dotenv
from mt5linux import MetaTrader5

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
            return PermissionError
    else:
        print("MT5 Initialization Failed")
        return ConnectionAbortedError

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
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed, retcode={result.retcode}")
    else:
        print(f"Order succeeded, retcode={result.retcode}")
        return result.order

def close_open_position(ticket):
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
    else:
        print("Order successfully closed!")

def get_csv_file_path(filename):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, filename)

def download_and_process_CPI_excel(url, sheet_name):
    df = pd.read_excel(url, sheet_name=sheet_name)
    df = df.iloc[:, [0, 16]]
    df = df.rename(columns={"Date": "DATE", "12mo.3": "CORESTICKM159SFRBATL"})
    df['DATE'] = pd.to_datetime(df['DATE']).dt.strftime('%Y-%m-%d')
    df = df[["DATE", "CORESTICKM159SFRBATL"]].reset_index(drop=True)
    return df[df["CORESTICKM159SFRBATL"] != "na"]

def save_to_csv(df, file_path):
    df.to_csv(file_path, index=False)

def download_unrate_csv():
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

def process_unrate_csv():
    unrate_file_path = get_csv_file_path('UNRATE.csv')
    df = pd.read_csv(unrate_file_path)
    print("UNRATE.csv head:")
    print(df.head())
    print("\nUNRATE.csv tail:")
    print(df.tail())

def check_market_conditions():
    global in_position, ticket

    # Download, process, and save CPI data
    csv_file_path = get_csv_file_path('CORESTICKM159SFRBATL.csv')
    url = "https://www.atlantafed.org/-/media/documents/datafiles/research/inflationproject/stickprice/stickyprice.xlsx"
    df = download_and_process_CPI_excel(url, "Data")
    save_to_csv(df, csv_file_path)
    print(df.tail())

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
    if not start_mt5():
        return

    # Schedule the task every minute
    schedule.every(1).minutes.do(check_market_conditions)

    global ticket, in_position
    ticket = execute_trade()
    in_position = True
    print(ticket)

    # Run the scheduler
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("Script terminated by user")
    finally:
        # Shutdown MT5 connection
        mt5.shutdown()

if __name__ == "__main__":
    main()
