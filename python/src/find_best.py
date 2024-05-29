import pandas as pd
import numpy as np
from datetime import datetime
import math
# import matplotlib.pyplot as plt
import datetime as dt
import requests
from requests_html import HTMLSession
import json
import appdirs as ad
ad.user_cache_dir = lambda *args: "/tmp"
import yfinance as yf

# yf.set_tz_cache_location("/temp/home/sbx_user1051/.cache/py-yfinance")

def get_yfinance_crypto_list(number_of_crypto: int):
    session = HTMLSession()
    num_currencies = number_of_crypto
    resp = session.get(f"https://finance.yahoo.com/crypto?offset=0&count={num_currencies}")
    tables = pd.read_html(resp.html.raw_html)
    df = tables[0].copy()
    symbols_yf_list = df.Symbol.tolist()[0:]
    Name_yf_list = df.Name.tolist()[0:]
    return symbols_yf_list, Name_yf_list

def Supertrend(df, atr_period, multiplier):
    
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    # calculate ATR
    price_diffs = [high - low, 
                   high - close.shift(), 
                   close.shift() - low]
    true_range = pd.concat(price_diffs, axis=1)
    true_range = true_range.abs().max(axis=1)
    # default ATR calculation in supertrend indicator
    atr = true_range.ewm(alpha=1/atr_period,min_periods=atr_period).mean() 
    # df['atr'] = df['tr'].rolling(atr_period).mean()
    
    # HL2 is simply the average of high and low prices
    hl2 = (high + low) / 2
    # upperband and lowerband calculation
    # notice that final bands are set to be equal to the respective bands
    final_upperband = upperband = hl2 + (multiplier * atr)
    final_lowerband = lowerband = hl2 - (multiplier * atr)
    
    # initialize Supertrend column to True
    supertrend = [True] * len(df)
    
    for i in range(1, len(df.index)):
        curr, prev = i, i-1
        
        # if current close price crosses above upperband
        if close[curr] > final_upperband[prev]:
            supertrend[curr] = True
        # if current close price crosses below lowerband
        elif close[curr] < final_lowerband[prev]:
            supertrend[curr] = False
        # else, the trend continues
        else:
            supertrend[curr] = supertrend[prev]
            
            # adjustment to the final bands
            if supertrend[curr] == True and final_lowerband[curr] < final_lowerband[prev]:
                final_lowerband[curr] = final_lowerband[prev]
            if supertrend[curr] == False and final_upperband[curr] > final_upperband[prev]:
                final_upperband[curr] = final_upperband[prev]

        # to remove bands according to the trend direction
        if supertrend[curr] == True:
            final_upperband[curr] = np.nan
        else:
            final_lowerband[curr] = np.nan
    
    return pd.DataFrame({
        'Supertrend': supertrend,
        'Final Lowerband': final_lowerband,
        'Final Upperband': final_upperband
    }, index=df.index)


def backtest(df, initial_investment, lot_size, sl_size, tp_size, commission):
    # print(df.head())
    is_uptrend = df['Supertrend']
    close = df['Close'] 
    low = df['Low']
    high = df['High']
    open = df['Open']
    # date = df['Date']

    # it is the max value of the price of the double peak/double bottom pattern
    max_of_consecutive_2_high_prices = np.nan
    # it is the min value of the price of the double peak/double bottom pattern
    min_of_consecutive_2_low_prices = np.nan
    # It indicates the price of enter after the trigger signal happened.
    # For double bottom, enter only happened when the close price is higher than max_price as shown below.
    # For double peak, enter only happened when the close price is lower than min_price as shown below.
    entry_price = np.nan
    # The exit price of the trade
    exit_price = np.nan

    # squeeze_off = df['squeeze_off']
    # squeeze_bar_value = df['bar_value']
    # squeeze_momentum_bar_up = df['squeeze_momentum_bar_up']

    # initial condition
    in_position = False
    direction = None
    equity = initial_investment
    equity_minus_investment = 0
    profit_per_share = None
    # commission = commission
    # Stoploss=stopLoss
    point_size = 1
    stopLoss = sl_size * point_size
    targetProfit = tp_size * point_size
    # entry = []
    # exit = []
    # equity_per_day = []

    for i in range(1, len(df)):

        # date_str = date[i].strftime('%Y-%m-%d')
        # date_str = date[i]

        check_completed = False

        # if not in position & price is on uptrend -> buy and entry in
        # add squeeze off and momentum bar going up later
        if is_uptrend[i]:

            if not in_position:
                # and is_uptrend[i] and squeeze_off[i] and squeeze_momentum_bar_up[i]:

                direction = 'Buy'

                max_of_consecutive_2_high_prices = max(high.iloc[i], high.iloc[i-1])
                min_of_consecutive_2_low_prices = min(low.iloc[i], low.iloc[i-1])
                entry_price = close.iloc[i]
                
                # equity_per_day.append({date_str:equity- commission})
                equity_minus_investment = equity - lot_size * close[i] 

                # entry.append({"Date":date_str, "Type": "Buy", "Entry":"Entry in","Price": close[i], 
                #             "Volume": lot_size, "Reason":"SuperTrend_is_uptrend",
                #             "Strategy":"SuperTrend", "Reason_type":"Long"})
                in_position = True
                # print(
                #     f'Long {lot_size} shares at {round(close[i],2)} on {df.index[i].strftime("%Y/%m/%d")}')
                
                check_completed = True

            elif in_position and direction == "Sell":
                
                # if in position & price is on uptrend -> stop short and entry out
                profit_per_share = -(close[i] - entry_price)
                equity = equity_minus_investment + lot_size * (entry_price+profit_per_share) - commission
                # equity_per_day.append({date_str:equity})

                # exit.append({"Date":date_str, "Type": "Sell", "Entry":"Entry out","Price": close[i], 
                #             "Volume": lot_size, "Reason":"SuperTrend_not_downtrend",
                #             "Strategy":"SuperTrend", "Reason_type":"Stop short"})
                in_position = False
                direction = None

                # print(
                #     f'Stop Short at {round(close[i],2)} on {df.index[i].strftime("%Y/%m/%d")}, reason "Not DownTrend"')


                # then long and entry in

                direction = 'Buy'

                max_of_consecutive_2_high_prices = max(high.iloc[i], high.iloc[i-1])
                min_of_consecutive_2_low_prices = min(low.iloc[i], low.iloc[i-1])
                entry_price = close.iloc[i]

                # equity_per_day.append({date_str:equity- commission})
                equity_minus_investment = equity - lot_size * close[i] 

                # entry.append({"Date":date_str, "Type": "Buy", "Entry":"Entry in","Price": close[i], 
                #             "Volume": lot_size, "Reason":"SuperTrend_is_uptrend",
                #             "Strategy":"SuperTrend", "Reason_type":"Long"})
                in_position = True
                # print(
                #     f'Long {lot_size} shares at {round(close[i],2)} on {df.index[i].strftime("%Y/%m/%d")}')

                check_completed = True  

        elif not is_uptrend[i]:

            if not in_position:

                direction = 'Sell'

                max_of_consecutive_2_high_prices = max(high.iloc[i], high.iloc[i-1])
                min_of_consecutive_2_low_prices = min(low.iloc[i], low.iloc[i-1])
                entry_price = close.iloc[i]

                # share = math.floor(equity / close[i] / 100) * 100
                # equity -= share * close[i]
                
                # equity_per_day.append({date_str:equity- commission})
                equity_minus_investment = equity - lot_size * close[i] 

                # entry.append({"Date":date_str, "Type": "Sell", "Entry":"Entry in","Price": close[i], 
                #             "Volume": lot_size, "Reason":"SuperTrend_is_downtrend",
                #             "Strategy":"SuperTrend", "Reason_type":"Short"})
                in_position = True
                # print(
                #     f'Short {lot_size} shares at {round(close[i],2)} on {df.index[i].strftime("%Y/%m/%d")}')

                check_completed = True

            # if in position & price is not on uptrend -> stop long and entry out
            elif in_position and direction == "Buy": 

                # equity += share * close[i] - commission
                profit_per_share = close[i] - entry_price
                equity = equity_minus_investment + lot_size * (entry_price+profit_per_share) - commission
                # equity_per_day.append({date_str:equity})

                # exit.append({"Date":date_str, "Type": "Buy", "Entry":"Entry out","Price": close[i], 
                #             "Volume": lot_size, "Reason":"SuperTrend_not_uptrend",
                #             "Strategy":"SuperTrend", "Reason_type":"Stop Long"})
                in_position = False
                direction = None
                # print(
                #     f'Stop Long at {round(close[i],2)} on {df.index[i].strftime("%Y/%m/%d")}, reason "Not UpTrend"')


                # then short and entry in

                direction = 'Sell'

                max_of_consecutive_2_high_prices = max(high.iloc[i], high.iloc[i-1])
                min_of_consecutive_2_low_prices = min(low.iloc[i], low.iloc[i-1])
                entry_price = close.iloc[i]

                # equity_per_day.append({date_str:equity- commission})
                equity_minus_investment = equity - lot_size * close[i] 

                # entry.append({"Date":date_str, "Type": "Sell", "Entry":"Entry in","Price": close[i], 
                #             "Volume": lot_size, "Reason":"SuperTrend_is_downtrend",
                #             "Strategy":"SuperTrend", "Reason_type":"Short"})
                in_position = True
                # print(
                #     f'Short {lot_size} shares at {round(close[i],2)} on {df.index[i].strftime("%Y/%m/%d")}')

                check_completed = True

        if not check_completed:
            
            if direction == 'Buy':

                # if hit stop loss (bar's low is lower than previous 2 consecutive bar's lowest), 
                # stop long and entry out
                if stopLoss != 0 and in_position and low.iloc[i] <= min_of_consecutive_2_low_prices-stopLoss:
                    
                    if (open.iloc[i] >= min_of_consecutive_2_low_prices-stopLoss):
                        exit_price = min_of_consecutive_2_low_prices-stopLoss
                    else:
                        # open is lower than stop loss already, so use open
                        exit_price = open.iloc[i]

                    # equity += share * price3 - commission
                    profit_per_share = exit_price - entry_price
                    equity = equity_minus_investment + lot_size * (entry_price+profit_per_share) - commission
                    # equity_per_day.append({date_str:equity})

                    # exit.append({"Date":date_str, "Type": "Buy", "Entry":"Entry out","Price": exit_price, 
                    #             "Volume": lot_size,"Reason":"Hit Stop Loss",
                    #             "Strategy":"SuperTrend", "Reason_type":"Stop Long"})
                    in_position = False
                    direction = None
                    # print(
                    #     f'Stop Long at {round(exit_price,2)} on {df.index[i].strftime("%Y/%m/%d")}, reason "Hit Stop Loss"')

                    check_completed = True

                # if hit target profit (bar's high is higher than previous 2 consecutive bar's highest), 
                # stop long and entry out
                elif targetProfit != 0 and in_position and high.iloc[i] >= max_of_consecutive_2_high_prices+targetProfit:
                    
                    if (open.iloc[i] <= max_of_consecutive_2_high_prices+targetProfit):
                        exit_price = entry_price+targetProfit
                    else:
                        # open is higher than target profit already, so use open
                        exit_price = open.iloc[i]

                    # equity += share * price3 - commission
                    profit_per_share = exit_price - entry_price
                    equity = equity_minus_investment + lot_size * (entry_price+profit_per_share) - commission
                    # equity_per_day.append({date_str:equity})

                    # exit.append({"Date":date_str, "Type": "Buy", "Entry":"Entry out","Price": exit_price, 
                    #                 "Volume": lot_size, "Reason":"Hit Target Profit",
                    #                 "Strategy":"SuperTrend", "Reason_type":"Stop Long"})
                    in_position = False
                    direction = None
                    # print(
                    #     f'Stop Long at {round(exit_price,2)} on {df.index[i].strftime("%Y/%m/%d")}, reason "Hit Target Profit"')

                    check_completed = True

            if direction == 'Sell':
                # if hit stop loss (bar's high is higher than previous 2 consecutive bar's highest), 
                # stop short and entry out
                if stopLoss != 0 and in_position and high.iloc[i] >= max_of_consecutive_2_high_prices+stopLoss:
                    
                    if (open.iloc[i] <= max_of_consecutive_2_high_prices+stopLoss):
                        exit_price = entry_price+stopLoss
                    else:
                        # open is higher than stop loss already, so use open
                        exit_price = open.iloc[i]

                    # equity += share * price3 - commission
                    profit_per_share = -(exit_price - entry_price)
                    equity = equity_minus_investment + lot_size * (entry_price+profit_per_share) - commission
                    # equity_per_day.append({date_str:equity})

                    # exit.append({"Date":date_str, "Type": "Sell", "Entry":"Entry out","Price": exit_price, 
                    #                 "Volume": lot_size, "Reason":"Hit Stop Loss",
                    #                 "Strategy":"SuperTrend", "Reason_type":"Stop Short"})
                    in_position = False
                    direction = None
                    # print(
                    #     f'Stop Short at {round(exit_price,2)} on {df.index[i].strftime("%Y/%m/%d")}, reason "Hit Stop Loss"')

                    check_completed = True

                # if hit target profit (bar's low is lower than previous 2 consecutive bar's lowest), 
                # stop short and entry out
                elif targetProfit != 0 and in_position and low.iloc[i] <= min_of_consecutive_2_low_prices-targetProfit:
                    
                    if (open.iloc[i] >= min_of_consecutive_2_low_prices-targetProfit):
                        exit_price = min_of_consecutive_2_low_prices-targetProfit
                    else:
                        # open is lower than target profit already, so use open
                        exit_price = open.iloc[i]

                    # equity += share * price3 - commission
                    profit_per_share = -(exit_price - entry_price)
                    equity = equity_minus_investment + lot_size * (entry_price+profit_per_share) - commission
                    # equity_per_day.append({date_str:equity})

                    # exit.append({"Date":date_str, "Type": "Sell", "Entry":"Entry out","Price": exit_price, 
                    #             "Volume": lot_size,"Reason":"Hit Target Profit",
                    #             "Strategy":"SuperTrend", "Reason_type":"Stop Short"})
                    in_position = False
                    direction = None
                    # print(
                    #     f'Stop Short at {round(exit_price,2)} on {df.index[i].strftime("%Y/%m/%d")}, reason "Hit Target Profit"')

                    check_completed = True

        # if not check_completed:
        #     if not in_position:
        #         equity_per_day.append({date_str:equity})
        #     else:
        #         equity_of_day = equity_minus_investment + lot_size * close[i]
        #         equity_per_day.append({date_str:equity_of_day})
    
    earning = equity - initial_investment
    if initial_investment != 0:
        roi = round(earning/initial_investment*100, 2)
    elif initial_investment == 0:
        roi = 0
    final_equity = equity
    # formatted_investment_value = _format_investment_value(initial_investment)
    # print(f'Earning from investing ${formatted_investment_value} is ${round(earning, 2)} (ROI = {roi}%)')
    # print(
    #     f'Earning from investing $100k is ${round(earning,2)} (ROI = {roi}%)')
    # return entry, exit, equity_per_day, final_equity, roi
    return final_equity, roi



def backtest_supertrend(df, investment,commission,print_result,print_detail):
    

    
    # Calculate the ATR
    is_uptrend = df['Supertrend']
    close = df['Close']
    
    # initial condition
    in_position = False
    equity = investment
    commission = commission
    share = 0
    entry = []
    exit = []
    
    for i in range(1, len(df)):
        # print(i)
        # print(is_uptrend[i])
        # print(df.index[i])
        # if not in position & price is on uptrend -> buy
        if not in_position and is_uptrend[i]:
            share = math.floor(equity / close[i] / 100) * 100
            equity -= share * close[i]
            entry.append((i, close[i]))
            in_position = True
            if print_detail is True: 
                print(f'Buy {share} shares at {round(close[i],2)} on {df.index[i].strftime("%Y/%m/%d")}')
        # if in position & price is not on uptrend -> sell
        elif in_position and not is_uptrend[i]:
            equity += share * close[i] - commission
            exit.append((i, close[i]))
            in_position = False
            if print_detail is True: 
                print(f'Sell at {round(close[i],2)} on {df.index[i].strftime("%Y/%m/%d")}')
    # if still in position -> sell all share 
    if in_position:
        equity += share * close[i] - commission
    
    earning = equity - investment
    roi = round(earning/investment*100,2)
    if print_result is True: 
        print(f'Earning from investing ${int(investment/1000/1000)}M is ${round(earning,2)} (ROI = {roi}%)')
        print(" ")
    return entry, exit, roi


def find_optimal_parameter(fy_df, strategy, backtest, investment,lot_size, sl_size, tp_size, commission,atr, multiplier ):
    # predefine several parameter sets- ****change
    atr_period=[]
    atr_multiplier = []
    
    if atr is None:
        atr_period = list(range(1, 20))
    elif atr > 0:
        atr_period = [atr]
        
    if multiplier is None:
        atr_multiplier = [i/2 for i in range(2, 41)]
    elif multiplier > 0:
        atr_multiplier = [multiplier]
    
    roi_list = []
    
    # for each period and multiplier, perform backtest
    for period, multiplier in [(x,y) for x in atr_period for y in atr_multiplier]:
        new_df = fy_df
        # supertrend = Supertrend(df, period, multiplier)
        # new_df = df.join(supertrend)
        strategy_df = strategy(fy_df, period, multiplier)
        new_df = fy_df.join(strategy_df)
        new_df = new_df[period:]
        final_equity, roi = backtest(new_df, investment,lot_size, sl_size, tp_size, commission)
        roi_list.append((period, multiplier, roi))
    
    # print(pd.DataFrame(roi_list, columns=['ATR_period','Multiplier','ROI']))
    
    # return the best parameter set
    return max(roi_list, key=lambda x:x[2])

def get_yf_df(symbol, start_date, end_date,interval='1h',threads=True):
    start_date = dt.datetime.strptime(start_date, '%Y-%m-%d')
    end_date = dt.datetime.strptime(end_date, '%Y-%m-%d')
    df = yf.download(
        tickers=symbol,
        start=start_date.strftime('%Y-%m-%d'),
        end=end_date.strftime('%Y-%m-%d'),
        interval=interval,
        # auto_adjust=True,
        threads=threads,
    )
        
    return df

def get_yf_df_with_best_parameters(symbols, start_date, end_date, atr_period,multiplier):
    # Convert the dates to datetime objects
    start_date = dt.datetime.strptime(start_date, '%Y-%m-%d')
    end_date = dt.datetime.strptime(end_date, '%Y-%m-%d')

    # Add one day to the end date to make sure the last day is included in the range
    end_date += dt.timedelta(days=1)

    # Fetch the data for the given symbol
    df = yf.download(
        tickers=symbols,
        start=start_date.strftime('%Y-%m-%d'),
        end=end_date.strftime('%Y-%m-%d'),
        interval='1h',
        threads=True,
    )

    # Calculate the Supertrend indicator using the ATR period and multiplier
    high = df['High']
    low = df['Low']
    close = df['Close']
    price_diffs = [high - low, high - close.shift(), close.shift() - low]
    tr = pd.concat(price_diffs, axis=1)
    tr = tr.abs().max(axis=1)
    atr = tr.ewm(alpha=1/atr_period, min_periods=atr_period).mean()
    hl2 = (high + low) / 2
    final_upperband = upperband = hl2 + (multiplier * atr)
    final_lowerband = lowerband = hl2 - (multiplier * atr)
    supertrend = [True] * len(df)
    for i in range(1, len(df.index)):
        curr, prev = i, i-1
        if close[curr] > final_upperband[prev]:
            supertrend[curr] = True
        elif close[curr] < final_lowerband[prev]:
            supertrend[curr] = False
        else:
            supertrend[curr] = supertrend[prev]
            if supertrend[curr] == True and final_lowerband[curr] < final_lowerband[prev]:
                final_lowerband[curr] = final_lowerband[prev]
            if supertrend[curr] == False and final_upperband[curr] > final_upperband[prev]:
                final_upperband[curr] = final_upperband[prev]
        if supertrend[curr] == True:
            final_upperband[curr] = np.nan
        else:
            final_lowerband[curr] = np.nan
    supertrend = pd.DataFrame({
        'Supertrend': supertrend,
        'Final Lowerband': final_lowerband,
        'Final Upperband': final_upperband
    }, index=df.index)
    df = df.join(supertrend)
    return df