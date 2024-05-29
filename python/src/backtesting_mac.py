
import pandas as pd
import numpy as np
from datetime import datetime
import yfinance as yf
from decimal import Decimal
# import math
# import matplotlib.pyplot as plt

# symbol = "BTC-USD"

# SuperTrend parameters
# atr_period = 10
# multiplier = 3

# Squeeze_momentum parameters
length = 20
mult = 2
length_KC = 20
mult_KC = 1.5


def get_data(symbol, start_date, end_date, time_frame):
    df = yf.download(symbol, start=start_date,
                     end=end_date, interval=time_frame)
    return df


def add_supertrend(df,atr_period,multiplier):

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
    atr = true_range.ewm(alpha=1/atr_period, min_periods=atr_period).mean()
    # df['atr'] = df['tr'].rolling(atr_period).mean()

    # HL2 is simply the average of high and low prices
    hl2 = (high + low) / 2
    # upperband and lowerband calculation
    # notice that final bands are set to be equal to the respective bands
    final_upperband = hl2 + (multiplier * atr)
    final_lowerband = hl2 - (multiplier * atr)

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

    df['Supertrend'] = pd.DataFrame(data=supertrend, index=df.index)
    df['Final Lowerband'] = pd.DataFrame(data=final_lowerband, index=df.index)
    df['Final Upperband'] = pd.DataFrame(data=final_upperband, index=df.index)

    return df


def add_squeeze_momentum(df):
    # calculate BB
    m_avg = df["Close"].rolling(window=length).mean()
    m_std = df["Close"].rolling(window=length).std(ddof=0)
    df['upper_BB'] = m_avg + mult * m_std
    df['lower_BB'] = m_avg - mult * m_std

    # calculate true range
    df['tr0'] = abs(df["High"] - df["Low"])
    df['tr1'] = abs(df["High"] - df["Close"].shift())
    df['tr2'] = abs(df["Low"] - df["Close"].shift())
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)

    # calculate KC
    range_ma = df['tr'].rolling(window=length_KC).mean()
    df['upper_KC'] = m_avg + range_ma * mult_KC
    df['lower_KC'] = m_avg - range_ma * mult_KC

    # calculate bar value
    highest = df["High"].rolling(window=length_KC).max()
    lowest = df["Low"].rolling(window=length_KC).min()
    m1 = (highest + lowest)/2
    df['bar_value'] = (df["Close"] - (m1 + m_avg)/2)
    fit_y = np.array(range(0, length_KC))
    df['bar_value'] = df['bar_value'].rolling(window=length_KC).apply(lambda x: np.polyfit(
        fit_y, x, 1)[0] * (length_KC-1) + np.polyfit(fit_y, x, 1)[1], raw=True)

    df = df.assign(squeeze_momentum_bar_up=lambda x: (
        x['bar_value'] > x['bar_value'].shift()))

    # check for 'squeeze'
    df['squeeze_on'] = (df['lower_BB'] > df['lower_KC']) & (
        df['upper_BB'] < df['upper_KC'])
    df['squeeze_off'] = (df['lower_BB'] < df['lower_KC']) & (
        df['upper_BB'] > df['upper_KC'])

    df["Date"] = df.index

    return df

def _format_investment_value(value):
    if value >= 1_000_000_000:
        return f'{value // 1_000_000_000}B'
    elif value >= 1_000_000:
        return f'{value // 1_000_000}M'
    elif value >= 1_000:
        return f'{value // 1_000}K'
    else:
        return str(value)


def backtest(df, initial_investment, lot_size, sl_size, tp_size, commission):
    print('lot_size: ', lot_size)

    is_uptrend = df['Supertrend']
    close = df['Close'] 
    low = df['Low']
    high = df['High']
    open = df['Open']
    date = df['Date']

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

    squeeze_off = df['squeeze_off']
    # squeeze_bar_value = df['bar_value']
    squeeze_momentum_bar_up = df['squeeze_momentum_bar_up']

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
    entry = []
    exit = []
    equity_per_day = []

    for i in range(1, len(df)):

        # date_str = date[i].strftime('%Y-%m-%d')
        date_str = date[i].strftime('%Y-%m-%d %H:%M:%S')

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

                # share = math.floor(equity / close[i] / 100) * 100
                # equity -= share * close[i]
                
                equity_per_day.append({date_str:str(equity- commission)})
                equity_minus_investment = equity - lot_size * close[i] 

                entry.append({"Date":date_str, "Type": "Buy", "Entry":"Entry in","Price": str(close[i]), 
                            "Volume": str(lot_size), "Reason":"SuperTrend_is_uptrend",
                            "Strategy":"SuperTrend", "Reason_type":"Long"})
                in_position = True
                print(
                    f'Long {lot_size} shares at {round(close[i],2)} on {df.index[i].strftime("%Y/%m/%d")}')
                
                check_completed = True

            elif in_position and direction == "Sell":
                
                # if in position & price is on uptrend -> stop short and entry out
                profit_per_share = -(close[i] - entry_price)
                equity = equity_minus_investment + lot_size * (entry_price+profit_per_share) - commission
                equity_per_day.append({date_str:str(equity)})

                exit.append({"Date":date_str, "Type": "Sell", "Entry":"Entry out","Price": str(close[i]), 
                            "Volume": str(lot_size), "Reason":"SuperTrend_not_downtrend",
                            "Strategy":"SuperTrend", "Reason_type":"Stop short"})
                in_position = False
                direction = None

                print(
                    f'Stop Short at {round(close[i],2)} on {df.index[i].strftime("%Y/%m/%d")}, reason "Not DownTrend"')


                # then long and entry in

                direction = 'Buy'

                max_of_consecutive_2_high_prices = max(high.iloc[i], high.iloc[i-1])
                min_of_consecutive_2_low_prices = min(low.iloc[i], low.iloc[i-1])
                entry_price = close.iloc[i]

                equity_per_day.append({date_str:str(equity- commission)})
                equity_minus_investment = equity - lot_size * close[i] 

                entry.append({"Date":date_str, "Type": "Buy", "Entry":"Entry in","Price": str(close[i]), 
                            "Volume": str(lot_size), "Reason":"SuperTrend_is_uptrend",
                            "Strategy":"SuperTrend", "Reason_type":"Long"})
                in_position = True
                print(
                    f'Long {lot_size} shares at {round(close[i],2)} on {df.index[i].strftime("%Y/%m/%d")}')

                check_completed = True  

        elif not is_uptrend[i]:

            if not in_position:

                direction = 'Sell'

                max_of_consecutive_2_high_prices = max(high.iloc[i], high.iloc[i-1])
                min_of_consecutive_2_low_prices = min(low.iloc[i], low.iloc[i-1])
                entry_price = close.iloc[i]

                # share = math.floor(equity / close[i] / 100) * 100
                # equity -= share * close[i]
                
                equity_per_day.append({date_str:str(equity- commission)})
                equity_minus_investment = equity - lot_size * close[i] 

                entry.append({"Date":date_str, "Type": "Sell", "Entry":"Entry in","Price": str(close[i]), 
                            "Volume": str(lot_size), "Reason":"SuperTrend_is_downtrend",
                            "Strategy":"SuperTrend", "Reason_type":"Short"})
                in_position = True
                print(
                    f'Short {lot_size} shares at {round(close[i],2)} on {df.index[i].strftime("%Y/%m/%d")}')

                check_completed = True

            # if in position & price is not on uptrend -> stop long and entry out
            elif in_position and direction == "Buy": 

                # equity += share * close[i] - commission
                profit_per_share = close[i] - entry_price
                equity = equity_minus_investment + lot_size * (entry_price+profit_per_share) - commission
                equity_per_day.append({date_str:str(equity)})

                exit.append({"Date":date_str, "Type": "Buy", "Entry":"Entry out","Price": str(close[i]), 
                            "Volume": str(lot_size), "Reason":"SuperTrend_not_uptrend",
                            "Strategy":"SuperTrend", "Reason_type":"Stop Long"})
                in_position = False
                direction = None
                print(
                    f'Stop Long at {round(close[i],2)} on {df.index[i].strftime("%Y/%m/%d")}, reason "Not UpTrend"')


                # then short and entry in

                direction = 'Sell'

                max_of_consecutive_2_high_prices = max(high.iloc[i], high.iloc[i-1])
                min_of_consecutive_2_low_prices = min(low.iloc[i], low.iloc[i-1])
                entry_price = close.iloc[i]

                equity_per_day.append({date_str:str(equity - commission)})
                equity_minus_investment = equity - lot_size * close[i] 

                entry.append({"Date":date_str, "Type": "Sell", "Entry":"Entry in","Price": str(close[i]), 
                            "Volume": str(lot_size), "Reason":"SuperTrend_is_downtrend",
                            "Strategy":"SuperTrend", "Reason_type":"Short"})
                in_position = True
                print(
                    f'Short {lot_size} shares at {round(close[i],2)} on {df.index[i].strftime("%Y/%m/%d")}')

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
                    equity_per_day.append({date_str:str(equity)})

                    exit.append({"Date":date_str, "Type": "Buy", "Entry":"Entry out","Price": str(exit_price), 
                                "Volume": str(lot_size),"Reason":"Hit Stop Loss",
                                "Strategy":"SuperTrend", "Reason_type":"Stop Long"})
                    in_position = False
                    direction = None
                    print(
                        f'Stop Long at {round(exit_price,2)} on {df.index[i].strftime("%Y/%m/%d")}, reason "Hit Stop Loss"')

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
                    equity_per_day.append({date_str:str(equity)})

                    exit.append({"Date":date_str, "Type": "Buy", "Entry":"Entry out","Price": str(exit_price), 
                                    "Volume": str(lot_size), "Reason":"Hit Target Profit",
                                    "Strategy":"SuperTrend", "Reason_type":"Stop Long"})
                    in_position = False
                    direction = None
                    print(
                        f'Stop Long at {round(exit_price,2)} on {df.index[i].strftime("%Y/%m/%d")}, reason "Hit Target Profit"')

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
                    equity_per_day.append({date_str:str(equity)})

                    exit.append({"Date":date_str, "Type": "Sell", "Entry":"Entry out","Price": str(exit_price), 
                                    "Volume": str(lot_size), "Reason":"Hit Stop Loss",
                                    "Strategy":"SuperTrend", "Reason_type":"Stop Short"})
                    in_position = False
                    direction = None
                    print(
                        f'Stop Short at {round(exit_price,2)} on {df.index[i].strftime("%Y/%m/%d")}, reason "Hit Stop Loss"')

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
                    equity_per_day.append({date_str:str(equity)})

                    exit.append({"Date":date_str, "Type": "Sell", "Entry":"Entry out","Price": str(exit_price), 
                                "Volume": str(lot_size),"Reason":"Hit Target Profit",
                                "Strategy":"SuperTrend", "Reason_type":"Stop Short"})
                    in_position = False
                    direction = None
                    print(
                        f'Stop Short at {round(exit_price,2)} on {df.index[i].strftime("%Y/%m/%d")}, reason "Hit Target Profit"')

                    check_completed = True

        if not check_completed:
            if not in_position:
                equity_per_day.append({date_str:str(equity)})
            else:
                equity_of_day = equity_minus_investment + lot_size * close[i]
                equity_per_day.append({date_str:str(equity_of_day)})
        
    equity = equity_minus_investment + lot_size * close[i]
                
    earning = equity - initial_investment
    print('initial_investment: ', initial_investment)
    print('equity: ', equity)
    print('earning: ', earning)
    if initial_investment != 0:
        roi = round(earning/initial_investment*100, 2)
    elif initial_investment == 0:
        roi = 0
    final_equity = equity
    print('final_equity: ', final_equity)
    formatted_investment_value = _format_investment_value(initial_investment)

    print(f'Earning from investing ${formatted_investment_value} is ${round(earning, 2)} (ROI = {roi}%)')
    return entry, exit, equity_per_day, final_equity, roi

def find_optimal_parameter(fy_df, strategy, backtest, investment,lot_size, sl_size, tp_size, commission,atr, multiplier ):
    # print('fy_df: ', fy_df.tail())
    # print('run find_optimal_parameter: ')
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
        add_supertrend_df = add_supertrend(fy_df,period,multiplier)
        add_squeeze_momentum_df = add_squeeze_momentum(add_supertrend_df)
        # supertrend = Supertrend(df, period, multiplier)
        # new_df = df.join(supertrend)
        # strategy_df = strategy(fy_df, period, multiplier)
        # new_df = fy_df.join(strategy_df)
        # new_df = new_df[period:]
        # final_equity, roi = backtest(new_df, investment,lot_size, sl_size, tp_size, commission)
        entry, exit, equity_per_day, final_equity, roi = backtest(add_squeeze_momentum_df, investment,lot_size, sl_size, tp_size, commission)
        roi_list.append((period, multiplier, roi))
    
    # print(pd.DataFrame(roi_list, columns=['ATR_period','Multiplier','ROI']))
    
    # return the best parameter set
    
    # print('roi_list: ', roi_list)
    return max(roi_list, key=lambda x:x[2])
