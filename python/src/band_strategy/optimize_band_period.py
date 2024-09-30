import pandas as pd
import numpy as np
from backtest_band_strategy import load_historical_data, SYMBOL, BAND_DEVIATION, INITIAL_CAPITAL

def calculate_lot_size(capital: float, price: float) -> float:
    """Calculate the maximum lot size based on available capital and current price."""
    return capital / price

def backtest_strategy(data: pd.DataFrame, band_period: int) -> float:
    """Run backtest on the provided historical data with a specific band period."""
    # Calculate Bollinger Bands
    data['SMA'] = data['close'].rolling(window=band_period).mean()
    data['STD'] = data['close'].rolling(window=band_period).std()
    data['Upper'] = data['SMA'] + (BAND_DEVIATION * data['STD'])
    data['Lower'] = data['SMA'] - (BAND_DEVIATION * data['STD'])

    in_position = False
    position_side = None
    entry_price = None
    current_capital = INITIAL_CAPITAL
    lot_size = 0

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
            elif current_price < lower_band:
                # Enter BUY position
                in_position = True
                position_side = 'BUY'
                entry_price = current_price
        else:
            if position_side == 'BUY' and current_price > upper_band:
                # Exit BUY position
                exit_price = current_price
                profit = (exit_price - entry_price) * lot_size
                current_capital += profit
                in_position = False
            elif position_side == 'SELL' and current_price < lower_band:
                # Exit SELL position
                exit_price = current_price
                profit = (entry_price - exit_price) * lot_size
                current_capital += profit
                in_position = False

    # If still in position at the end, close the position
    if in_position:
        exit_price = data.iloc[-1]['close']
        if position_side == 'BUY':
            profit = (exit_price - entry_price) * lot_size
        elif position_side == 'SELL':
            profit = (entry_price - exit_price) * lot_size
        current_capital += profit

    return current_capital

def optimize_band_period(data: pd.DataFrame, min_period: int = 10, max_period: int = 200, step: int = 5):
    """Find the optimal band period by testing a range of values."""
    results = []

    for band_period in range(min_period, max_period + 1, step):
        final_capital = backtest_strategy(data, band_period)
        roi = ((final_capital - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
        results.append({'BAND_PERIOD': band_period, 'Final Capital': final_capital, 'ROI': roi})

    results_df = pd.DataFrame(results)
    best_result = results_df.loc[results_df['ROI'].idxmax()]

    print("Optimization Results:")
    print(results_df)
    print("\nBest BAND_PERIOD:")
    print(f"BAND_PERIOD: {best_result['BAND_PERIOD']}")
    print(f"Final Capital: {best_result['Final Capital']:.2f}")
    print(f"ROI: {best_result['ROI']:.2f}%")

    return best_result['BAND_PERIOD']

def main():
    data = load_historical_data()
    if not data.empty:
        best_band_period = optimize_band_period(data)
        print(f"\nRecommended BAND_PERIOD: {best_band_period}")
    else:
        print("No data available to run the optimization.")

if __name__ == "__main__":
    main()