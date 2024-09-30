import os
import pandas as pd
import numpy as np
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv
from mt5linux import MetaTrader5
import matplotlib.pyplot as plt

# Load environment variables
load_dotenv(find_dotenv())

# Define parameters
SYMBOL = "EURUSD"
LOT_SIZE = 1.0
STOP_LOSS_PIPS = 50
TAKE_PROFIT_PIPS = 10
BAND_PERIOD = 140
BAND_DEVIATION = 2
INITIAL_CAPITAL = 10000  # Set initial capital to 10000 USD

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

def load_historical_data() -> pd.DataFrame:
    """Download historical data using MetaTrader5."""
    if not mt5.initialize():
        print("Failed to initialize MetaTrader5")
        return pd.DataFrame()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # Fetch data for the last 30 days

    # Convert datetime to UNIX timestamp
    start_timestamp = int(start_date.timestamp())
    end_timestamp = int(end_date.timestamp())

    # Ensure that the timestamps are integers
    if not isinstance(start_timestamp, int) or not isinstance(end_timestamp, int):
        print("Start or end timestamp is not an integer.")
        return pd.DataFrame()

    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_timestamp, end_timestamp)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        print("No data fetched from MetaTrader5")
        return pd.DataFrame()

    df = pd.DataFrame(rates)
    df['Datetime'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('Datetime', inplace=True)
    df = df[['open', 'high', 'low', 'close', 'tick_volume']]
    return df

def calculate_lot_size(capital: float, price: float) -> float:
    """Calculate the maximum lot size based on available capital and current price."""
    return capital / price

def backtest_strategy(data: pd.DataFrame) -> None:
    """Run backtest on the provided historical data."""
    # Calculate Bollinger Bands
    data['SMA'] = data['close'].rolling(window=BAND_PERIOD).mean()
    data['STD'] = data['close'].rolling(window=BAND_PERIOD).std()
    data['Upper'] = data['SMA'] + (BAND_DEVIATION * data['STD'])
    data['Lower'] = data['SMA'] - (BAND_DEVIATION * data['STD'])

    in_position = False
    position_side = None
    entry_price = None
    entry_time = None
    current_capital = INITIAL_CAPITAL
    lot_size = 0

    trade_log = []

    for index, row in data.iterrows():
        current_price = row['close']
        upper_band = row['Upper']
        lower_band = row['Lower']

        # Skip rows where Bollinger Bands are NaN
        if pd.isna(upper_band) or pd.isna(lower_band):
            continue

        if not in_position:
            lot_size = calculate_lot_size(current_capital, current_price)
            if current_price > upper_band:
                # Enter SELL position
                in_position = True
                position_side = 'SELL'
                entry_price = current_price
                entry_time = index
                print(f"Entered SELL at {entry_price} on {entry_time}, Lot Size: {lot_size:.2f}")
            elif current_price < lower_band:
                # Enter BUY position
                in_position = True
                position_side = 'BUY'
                entry_price = current_price
                entry_time = index
                print(f"Entered BUY at {entry_price} on {entry_time}, Lot Size: {lot_size:.2f}")
        else:
            if position_side == 'BUY' and current_price > upper_band:
                # Exit BUY position
                exit_price = current_price
                exit_time = index
                profit = (exit_price - entry_price) * lot_size
                current_capital += profit
                trade_log.append({
                    'Entry Time': entry_time,
                    'Exit Time': exit_time,
                    'Position': position_side,
                    'Entry Price': entry_price,
                    'Exit Price': exit_price,
                    'Lot Size': lot_size,
                    'Profit': profit
                })
                print(f"Exited BUY at {exit_price} on {exit_time}, Profit: {profit:.2f}, Current Capital: {current_capital:.2f}")
                in_position = False
            elif position_side == 'SELL' and current_price < lower_band:
                # Exit SELL position
                exit_price = current_price
                exit_time = index
                profit = (entry_price - exit_price) * lot_size
                current_capital += profit
                trade_log.append({
                    'Entry Time': entry_time,
                    'Exit Time': exit_time,
                    'Position': position_side,
                    'Entry Price': entry_price,
                    'Exit Price': exit_price,
                    'Lot Size': lot_size,
                    'Profit': profit
                })
                print(f"Exited SELL at {exit_price} on {exit_time}, Profit: {profit:.2f}, Current Capital: {current_capital:.2f}")
                in_position = False

    # If still in position at the end, close the position
    if in_position:
        exit_price = data.iloc[-1]['close']
        exit_time = data.iloc[-1].name
        if position_side == 'BUY':
            profit = (exit_price - entry_price) * lot_size
        elif position_side == 'SELL':
            profit = (entry_price - exit_price) * lot_size
        current_capital += profit
        trade_log.append({
            'Entry Time': entry_time,
            'Exit Time': exit_time,
            'Position': position_side,
            'Entry Price': entry_price,
            'Exit Price': exit_price,
            'Lot Size': lot_size,
            'Profit': profit
        })
        print(f"Closed {position_side} at {exit_price} on {exit_time}, Profit: {profit:.2f}, Final Capital: {current_capital:.2f}")

    # Create a DataFrame from trade_log
    trades_df = pd.DataFrame(trade_log)

    if not trades_df.empty:
        # Calculate cumulative profit
        trades_df['Cumulative Profit'] = trades_df['Profit'].cumsum()
        # Print the trades
        print(trades_df)

        # Calculate total profit
        total_profit = trades_df['Profit'].sum()

        # Plot equity curve
        plt.figure(figsize=(12, 6))
        plt.plot(trades_df['Exit Time'], trades_df['Cumulative Profit'], marker='o')
        plt.title('Cumulative Profit Over Time')
        plt.xlabel('Time')
        plt.ylabel('Cumulative Profit (USD)')
        plt.grid(True)
        plt.text(0.05, 0.95, f"Total Profit: {total_profit:.2f} USD", transform=plt.gca().transAxes, verticalalignment='top')
        plt.text(0.05, 0.90, f"Initial Capital: {INITIAL_CAPITAL:.2f} USD", transform=plt.gca().transAxes, verticalalignment='top')
        plt.text(0.05, 0.85, f"Final Capital: {current_capital:.2f} USD", transform=plt.gca().transAxes, verticalalignment='top')
        plt.show()
        # Calculate ROI
        roi = ((current_capital - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
        print(f"Total Profit: {total_profit:.2f} USD")
        print(f"Initial Capital: {INITIAL_CAPITAL:.2f} USD")
        print(f"Final Capital: {current_capital:.2f} USD")
        print(f"Final ROI: {roi:.2f}%")
    else:
        print("No trades were made.")

def main():
    data = load_historical_data()
    if not data.empty:
        backtest_strategy(data)
    else:
        print("No data available to run the backtest.")

if __name__ == "__main__":
    main()