# -*- coding: utf-8 -*-
"""
Created on Fri Oct  7 16:58:34 2022

@author: Victor lee
"""

from utils.trade_deal_to_json import trade_deals_to_json

# import MetaTrader5 as mt5
from mt5linux import MetaTrader5
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import time
import schedule
import pytz
import yfinance as yf
import json

# import talib as ta
# import yfinance as yf

# lot_size = 0.1
# sl_size = 5000
# tp_size = 5000
# pair = ["BTCUSD"]

mt5 = MetaTrader5(
    # host = 'localhost',
    host = '18.141.245.200',
    port = 18812      
)  

# path = "C:/Program Files/Pepperstone MetaTrader 5/terminal64.exe"
path = "/home/ubuntu/.wine/drive_c/Program Files/Pepperstone MetaTrader 5/terminal64.exe"
# path = "/Users/mattchung/.wine/drive_c/Program Files/Pepperstone MetaTrader 5/terminal64.exe"
server = 'Pepperstone-Demo'
username = 61164970
password = "1loveMt5!"

deviation = 10
# start_date = datetime(2023, 6, 13, 0, 0, 0, tzinfo=pytz.timezone('Hongkong'))

# Function to start Meta Trader 5 (MT5)


# def start_mt5(username, password, server, path):
def start_mt5():
    # Ensure that all variables are the correct type
    uname = int(username)  # Username must be an int
    pword = str(password)  # Password must be a string
    trading_server = str(server)  # Server must be a string
    filepath = str(path)  # Filepath must be a string

    # Attempt to start MT5
    if mt5.initialize(login=uname, password=pword, server=trading_server, path=filepath):
        # Login to MT5
        if mt5.login(login=uname, password=pword, server=trading_server):
            return True
        else:
            print("Login Fail")
            # quit()
            return PermissionError
    else:
        print("MT5 Initialization Failed")
        # quit()
        return ConnectionAbortedError


def connect():
    mt5.initialize()

start_mt5()

def open_pending_position(symbol1, volume1, order_type, test_id, magic, tp_distance=None, sl_distance=None):
    print('magic: ', type(magic))
    magic = int(magic)
    # filling_type = mt5.symbol_info(symbol1).filling_mode
    filling_type = mt5.ORDER_FILLING_IOC
    type1 = None
    point = mt5.symbol_info(symbol1).point
    price = mt5.symbol_info_tick(symbol1).ask
    if order_type == "BUY":
        # type1 = mt5.ORDER_TYPE_BUY_LIMIT
        type1 = mt5.ORDER_TYPE_BUY
        # price = mt5.symbol_info_tick(symbol).ask
        if sl_distance:
            sl = price - (sl_distance * point)
        if (tp_distance):
            tp = price + (tp_distance * point)

    elif order_type == "SELL":
        # type1 = mt5.ORDER_TYPE_SELL_LIMIT
        type1 = mt5.ORDER_TYPE_SELL
        # price = mt5.symbol_info_tick(symbol).bid
        if sl_distance:
            sl = price + (sl_distance * point)
        if (tp_distance):
            tp = price - (tp_distance * point)

    if tp_distance and sl_distance:
        request = {
            # "action": mt5.TRADE_ACTION_PENDING,
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol1,
            "volume": volume1,
            "type": type1,
            "price": price,
            "sl": sl,
            "tp": tp,
            "magic": magic,
            "comment": test_id,
            "type_filling": filling_type,
            "type_time": mt5.ORDER_TIME_GTC,
        }
    elif sl_distance:
        request = {
            # "action": mt5.TRADE_ACTION_PENDING,
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol1,
            "volume": volume1,
            "type": type1,
            "price": price,
            "sl": sl,
            "magic": magic,
            "comment": test_id,
            "type_filling": filling_type,
            "type_time": mt5.ORDER_TIME_GTC,
        }
    elif tp_distance:
        request = {
            # "action": mt5.TRADE_ACTION_PENDING,
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol1,
            "volume": volume1,
            "type": type1,
            "price": price,
            "tp": tp,
            "magic": magic,
            "comment": test_id,
            "type_filling": filling_type,
            "type_time": mt5.ORDER_TIME_GTC,
        }
    else:
        request = {
            # "action": mt5.TRADE_ACTION_PENDING,
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol1,
            "volume": volume1,
            "type": type1,
            "price": price,
            # "price": mt5.symbol_info_tick(symbol1).ask,
            "magic": magic,
            "comment": test_id,
            "type_filling": filling_type,
            "type_time": mt5.ORDER_TIME_GTC,
        }

    info_order = mt5.order_send(request)
    if info_order.retcode == 10009:
        print("### NEW Order for "+symbol1+" is sent and successful ###")
    else:
        print(f"###Error in sending order for {symbol1} ###")
        print("And the retcode is:"+str(info_order.retcode))
    return info_order


def close_open_position(ticket, symbol, volume, order_type, test_id, magic):
    if order_type == "BUY":
        type = mt5.ORDER_TYPE_BUY
    elif order_type == "SELL":
        type = mt5.ORDER_TYPE_SELL
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "position": ticket,
        "volume": volume,
        "type": type,
        "price": mt5.symbol_info_tick(symbol).bid,
        "deviation": deviation,
        "comment": test_id,
        "magic": magic,
        "type_filling": mt5.ORDER_FILLING_IOC,
        "type_time": mt5.ORDER_TIME_GTC
    }
    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print("### Failed to close order ###")
        print("The failure code is:"+str(result.retcode))
    else:
        print("### Order successfully closed! ###")


def update_position(ticket, size=None, tp_distance=None, stop_distance=None):

    ticket_details = position_get_details(ticket)
    symbol = ticket_details["symbol"]
    if symbol is not None:
        filling_type = mt5.symbol_info(symbol).filling_mode
        point = mt5.symbol_info(symbol).point
        order_type = ticket_details["direction"]
        price = ticket_details["price"]

        if (order_type == 0):
            price = mt5.symbol_info_tick(symbol).ask
            if (stop_distance):
                sl = price - (stop_distance * point)
            if (tp_distance):
                tp = price + (tp_distance * point)

        if (order_type == 1):
            price = mt5.symbol_info_tick(symbol).bid
            if (stop_distance):
                sl = price + (stop_distance * point)
            if (tp_distance):
                tp = price - (tp_distance * point)

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": ticket,
            "sl": sl,
            "tp": tp,
            "type_filling": filling_type,
            "type_time": mt5.ORDER_TIME_GTC}

        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print("Failed to send order :(")
            print("The failure code is:"+str(result.retcode))
        else:
            print("Order successfully placed!")


def positions_get(symbol=None):
    if (symbol is None):
        res = mt5.positions_get()
    else:
        res = mt5.positions_get(symbol=symbol)

    if (res is not None and res != ()):
        df = pd.DataFrame(list(res), columns=res[0]._asdict().keys())
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    return pd.DataFrame()


def position_get_details(ticket):
    symbol = None
    price = None
    sl_price = None
    tp_price = None
    direction = None
    for i in mt5.positions_get():
        if i.ticket == ticket:
            symbol = i.symbol
            price = i.price
            sl_price = i.sl
            tp_price = i.tp
            direction = i.type
    D1 = {"ticket": ticket, "symbol": symbol, "direction": direction,
          "price": price, "sl": sl_price, "tp": tp_price}
    return (D1)


def run_trader(symbol, time_frame, lot_size, sl_size, tp_size):
    print("Running trader at", datetime.now())
    # connect()
    start_mt5()
    symbol_data = get_rate_data_mt5(symbol, time_frame)
    forward_trade(symbol_data, lot_size, sl_size, tp_size)


def get_rate_data_mt5(symbol, time_frame, start_date):
    # pairs = ['XAUUSD','HK50','NAS100','USDJPY']
    mt5_data_obj = dict()
    # for pair in pairs:
    utc_from = start_date
    # utc_from = datetime(2023, 1, 1, tzinfo=pytz.timezone('Hongkong'))
    date_to = datetime.now().astimezone(pytz.timezone('Asia/Hong_Kong'))
    date_to = datetime(date_to.year, date_to.month, date_to.day,
                        hour=date_to.hour, minute=date_to.minute)
    utc_from_timestamp = utc_from.timestamp()
    date_to_timestamp = date_to.timestamp()
    # print(utc_from_timestamp)
    # print(date_to_timestamp)
    rates = mt5.copy_rates_range(
        symbol, time_frame, utc_from_timestamp, date_to_timestamp)
    # print(rates)
    # print(type(rates))
    # print(len(rates))
    if rates is not None:
        if len(rates) > 0:
            rates_frame = pd.DataFrame(rates)
            # rates_frame['time'] = pd.to_datetime(rates_frame['time'], unit='s')
            # rates_frame.drop(rates_frame.tail(1).index, inplace=True)
            mt5_data_obj[symbol] = rates_frame
            return mt5_data_obj
    else:
        print("mt5 return empty past data")
        return None    
     

def get_past_data_yfinance(symbol, start_date, end_date, time_frame):
    # use mt5 to get data?
    timeframe = {
            mt5.TIMEFRAME_M1: '1m',
            mt5.TIMEFRAME_M2: '2m',
            # mt5.TIMEFRAME_M3: 3,
            # mt5.TIMEFRAME_M4: 4,
            mt5.TIMEFRAME_M5: '5m',
            # mt5.TIMEFRAME_M6: 6,
            # mt5.TIMEFRAME_M10: 10,
            # mt5.TIMEFRAME_M12: 12,
            mt5.TIMEFRAME_M15: '15m',
            # mt5.TIMEFRAME_M20: 20,
            mt5.TIMEFRAME_M30: '30m',
            mt5.TIMEFRAME_H1: '1h',
            # mt5.TIMEFRAME_H2: 120,
            # mt5.TIMEFRAME_H3: 180,
            # mt5.TIMEFRAME_H4: 240,
            # mt5.TIMEFRAME_H6: 360,
            # mt5.TIMEFRAME_H8: 480,
            mt5.TIMEFRAME_D1: '1d',
            mt5.TIMEFRAME_W1: '1wk',
            mt5.TIMEFRAME_MN1: '1mo'
        }
    if time_frame not in timeframe:
        return "Invalid time frame in yFinance"
    else:
        
        yf_interval = timeframe[time_frame]
        df = yf.download(symbol, start=start_date,
                        end=end_date, interval=yf_interval)
        if df is not None:
            if len(df) > 0:
                return df
        else:
            return None
        
def calculate_time_metrics(start_time, steps_completed, total_steps):
    import time
    elapsed_time = time.time() - start_time 
    progress_fraction = steps_completed / total_steps
    estimated_total_time = elapsed_time / progress_fraction if progress_fraction > 0 else float('inf')
    estimated_remaining_time = estimated_total_time - elapsed_time
    return elapsed_time, estimated_remaining_time
        
def get_forward_test_result(symbol_ft, symbol_bt, start_date, end_date, initial_investment, lot_size, time_frame_ft, test_id, magic, progress_callback=None):
    deal_data = dict()

    def check_test_id(deal):
        if deal.comment == test_id:
            return True
        return False
    
    timezone = pytz.timezone("Asia/Hong_Kong")
    # utc_from = start_date - timedelta(days=180)
    utc_from = start_date 
    
    utc_from = datetime(utc_from.year, utc_from.month, utc_from.day,
                        hour=utc_from.hour, minute=utc_from.minute,tzinfo=timezone)
    utc_form_timestamp = utc_from.timestamp()
    
    # utc_from = datetime(2023, 1, 1, tzinfo=pytz.timezone('Hongkong'))
    date_to = datetime.now().astimezone(pytz.timezone("Asia/Hong_Kong"))+ timedelta(days=1)
    date_to = datetime(date_to.year, date_to.month, date_to.day,
                        hour=date_to.hour, minute=date_to.minute)
    date_to_timestamp = date_to.timestamp()
    
    # utc_from = start_date - datetime.timedelta(days=180)
    # date_to = datetime.now().astimezone(pytz.timezone('Hongkong')) + datetime.timedelta(days=1)
    
    history_deals = mt5.history_deals_get(utc_form_timestamp, date_to_timestamp, group=symbol_ft)
    class_history_deals = filter(check_test_id, history_deals)
    class_history_deals = trade_deals_to_json(class_history_deals)
    # print('class_history_deals: ', class_history_deals)
    # class_history_deals = tuple(class_history_deals)
    # print('class_history_deals: ', class_history_deals)

    # class_history_deals = tuple(class_history_deals)

    previous_position_id = None
    # deals_array = ()
    roi = 0
    profit_per_share = 0
    entry_of_deals = []
    exit_of_deals = []
    df_mt5_deals = pd.DataFrame(columns=['Ticket', 'Order', 'Time', 'Time_msc', 'Type', 'Entry', 
                                             'Magic', 'Position_id','Reason', 'Deal_Volume', 'Price', 
                                             'Commission', 'Swap', 'Profit', 'Fee', 'Symbol',
                                             'Comment', 'External_id'])
    
    equity = initial_investment
    equity_minus_investment = 0
    commission = 0
    in_position = False
    direction = None
    entry_price = None
    # share = lot_size
    equity_per_day = []
    
    total_steps = len(class_history_deals)

    steps_completed = 0
    import time

    test_start_time = time.time()
    print(f"Test start - {len(class_history_deals)}")
    for deal in class_history_deals:
        print('deal: ', deal)
        steps_completed += 1
        if progress_callback:
            elapsed_time, estimated_remaining_time = calculate_time_metrics(test_start_time, steps_completed, total_steps)
            progress_percentage = (steps_completed / total_steps) * 100
            progress_callback(progress_percentage, elapsed_time, estimated_remaining_time)
            
        if deal.magic == magic & deal.comment != test_id:
            deal_item = deal
            
        # if previous_position_id != deal['position_id']:
            # print(deal.position_id)
            # print(type(deal.position_id))
            # deals = mt5.history_deals_get(position=deal['position_id'])

            # deals = trade_deals_to_json(deal)
            # print(deals)
            # deals_array = deals_array+deals
            # for deal_item in deals:

                # deal = trade_deals_to_json(deal)
                # print(deal)
                # print(deal.position_id)
                # print(type(deal))
                # print(deal.position_id)
                # print(type(deal.position_id))
            profit_per_share += deal_item.profit
            # Convert tuple to dictionary
            deal_dict =  {
                        "Ticket": deal_item.ticket,
                        "Order": deal_item.order,
                        "Time": deal_item.time,
                        "Time_msc": deal_item.time_msc,
                        "Type": deal_item.type,
                        "Entry": deal_item.entry,
                        "Magic": deal_item.magic,
                        "Position_id": deal_item.position_id,
                        "Reason": deal_item.reason,
                        "Deal_Volume": deal_item.volume,
                        "Price": deal_item.price,
                        "Commission": deal_item.commission,
                        "Swap": deal_item.swap,
                        "Profit": deal_item.profit,
                        "Fee": deal_item.fee,
                        "Symbol": deal_item.symbol,
                        "Comment": deal_item.comment,
                        "External_id": deal_item.external_id
                        }
            # Convert dictionary to JSON
            json_deal = json.dumps(deal_dict)
            if deal_item.entry == 0:
                entry_of_deals.append({str(key): str(value) for key, value in json.loads(json_deal).items()})
                # print('df_mt5_deals: ', df_mt5_deals)
                # print('df_mt5_deals_type: ', type(df_mt5_deals))
                # print('len(df_mt5_deals): ', len(df_mt5_deals))
                #!!!!!!!!!!!!!!!!!!!!!!!!!
                # df_mt5_deals = df_mt5_deals.append(deal_dict, ignore_index=True)
                df_mt5_deals.loc[len(df_mt5_deals)] = deal_dict
            elif deal_item.entry == 1:
                exit_of_deals.append({str(key): str(value) for key, value in json.loads(json_deal).items()})
                # print('df_mt5_deals: ', df_mt5_deals)
                # print('df_mt5_deals_type: ', type(df_mt5_deals))
                # print('len(df_mt5_deals): ', len(df_mt5_deals))
                # df_mt5_deals = df_mt5_deals.append(deal_dict, ignore_index=True)
                df_mt5_deals.loc[len(df_mt5_deals)] = deal_dict
        # current_deal_position_id = deal['position_id']
        # previous_position_id = current_deal_position_id
    # first_entry = entry[0]
    # investment = first_entry.price*first_entry.volume
    # df_mt5_deals.rename(columns={'Volume': 'Deal_Volume'}, inplace=True)
    # print(df_mt5_deals)


    # get past data from yFinance or MT5
    df_yfinance = get_past_data_yfinance(symbol_bt,start_date, end_date, time_frame_ft)
    df_mt5_past_data = None
    combined_df = None
    time = None
    position_id = None
    close_past_data = None
    deal_price_mt5= None
    order_entry = None
    order_type = None
    commission = None
    
    if isinstance(df_yfinance, str) and df_yfinance == "Invalid time frame in yFinance":

        mt5_data_obj = get_rate_data_mt5(symbol_ft, time_frame_ft, start_date)
        
        if mt5_data_obj:
            # print(mt5_data_obj)
            df_mt5_past_data = mt5_data_obj[symbol_ft]
            df_mt5_past_data['Symbol'] = symbol_ft
            df_mt5_past_data.rename(columns={'time': 'Time'}, inplace=True)
            # print(df_mt5_past_data)
            combined_df = pd.concat([df_mt5_past_data,df_mt5_deals], axis=0, ignore_index=True, sort=False)

            combined_df = combined_df.sort_values('Time').reset_index(drop=True)
            # print(combined_df)
            # filtered_df = combined_df[combined_df['Position_id'].notna()]
            # print(filtered_df)

            time = combined_df['Time']
            position_id = combined_df['Position_id']
            close_past_data = combined_df['close']
            deal_price_mt5= combined_df['Price']
            order_entry = combined_df['Entry']
            order_type = combined_df['Type']
            commission = combined_df['Commission']
        else:
            return None

    else:
        if df_yfinance is not None:
            if len(df_yfinance) > 0:
                df_yfinance['Date'] = df_yfinance.index
                
                # Convert date column to epoch time
                # print(df['Date'])
                # df_yfinance['Time'] = pd.to_datetime(df_yfinance['Date'])
                df_yfinance['Time'] = pd.to_datetime(df_yfinance['Date']).apply(lambda x: int(x.timestamp()))
                df_yfinance.rename(columns={'Volume': 'Market_Volume'}, inplace=True)
                df_yfinance['Symbol'] = symbol_bt
                # print('df_yfinance: ', df_yfinance)
   
                combined_df = pd.concat([df_yfinance, df_mt5_deals], axis=0, ignore_index=True, sort=False)

            

                # after merge past data with deal data, then sort based on time
                combined_df = combined_df.sort_values('Time').reset_index(drop=True)
                # print('combined_df: ', combined_df)
                # print(combined_df)
                # filtered_df = combined_df[combined_df['Position_id'].notna()]
                # print(filtered_df)

                time = combined_df['Time']
                position_id = combined_df['Position_id']
                close_past_data = combined_df['Adj Close']
                deal_price_mt5= combined_df['Price']
                order_entry = combined_df['Entry']
                order_type = combined_df['Type']
                commission = combined_df['Commission']
        else:
            return None

    for i in range(1, len(combined_df)):
        # print(position_id[i])
        # print(pd.isna(position_id[i]))
        date = pd.to_datetime(time[i], unit='s').strftime('%Y-%m-%d %H:%M:%S')
        # print(date)
        # date=datetime.fromtimestamp(time[i]).date()
        # date = date.strftime('%Y-%m-%d')
        # print(date.strftime('%Y-%m-%d'))
        if not pd.isna(position_id[i]):
            # print('had deal')
            # print(date)
            # need to separate into  buy and sell, then entry in and entry out, then add back the shares to equity
            # buy and entry in
            if order_type[i] == 0 and order_entry[i] == 0:
                direction = 'Buy'
                in_position = True
                entry_price = deal_price_mt5[i]
                equity_per_day.append({date:str(equity- commission[i])})
                equity_minus_investment = equity - lot_size * deal_price_mt5[i] - commission[i]
            # reverse buy and entry out
            if order_type[i] == 1 and order_entry[i] == 1:
                if direction == 'Buy':
                    profit_per_share = deal_price_mt5[i] - entry_price
                    equity = equity_minus_investment + lot_size * (entry_price+profit_per_share) - commission[i]
                    equity_per_day.append({date:str(equity)})
                in_position = False
                entry_price = None
                direction = None
            # sell and entry in
            if order_type[i] == 1 and order_entry[i] == 0:
                direction = 'Sell'
                in_position = True
                entry_price = deal_price_mt5[i]
                equity_per_day.append({date:str(equity- commission[i])})
                equity_minus_investment = equity - lot_size * deal_price_mt5[i] - commission[i]
            # reverse sell and entry out
            if order_type[i] == 0 and order_entry[i] == 1:
                if direction == 'Sell':
                    profit_per_share = -(deal_price_mt5[i] - entry_price)
                    equity = equity_minus_investment + lot_size * (entry_price+profit_per_share) - commission[i]
                    equity_per_day.append({date:str(equity)})
                in_position = False
                entry_price = None
                direction = None

        else:
            # print(date)
            # print("equity: "+str(equity))
            # print("initial_investment: "+str(initial_investment))
            if not in_position:
                equity_per_day.append({date:str(equity)})
            else:
                equity_of_day = equity_minus_investment + lot_size * close_past_data[i]
                equity_per_day.append({date:str(equity_of_day)})
            # if equity == initial_investment and not in_position:
            #     equity_per_day.append({date:initial_investment})
            # elif equity == initial_investment and in_position:
            #     equity_of_day = equity_minus_investment + lot_size * close_yf[i]
            #     equity_per_day.append({date:equity_of_day})
            # elif equity != initial_investment and not in_position:
            #     equity_of_day = equity
            #     equity_per_day.append({date:equity_of_day})
            # elif equity != initial_investment and in_position:
            #     equity_of_day = equity_minus_investment + lot_size * close_yf[i]
            #     equity_per_day.append({date:equity_of_day})

    # need to define investment, and initial_investment. Now investment is just what bought in MT5
    earning = equity - initial_investment
    if initial_investment != 0:
        # roi = round(earning/initial_investment*100, 2)
        roi = earning/initial_investment*100
    elif initial_investment == 0:
        roi = 0
    final_equity = equity
    deal_data[symbol_ft] = {"roi": str(roi), "equity_per_day":equity_per_day, "final_equity":str(final_equity),
                            "entry_of_deals": entry_of_deals, "exit_of_deals": exit_of_deals}
    # print('deal_data', deal_data)

    return deal_data

 #! add bt atr and multi para

def forward_trade(symbol_data, lot_size, sl_size, tp_size, start_date, test_id, magic, atr_period,multiplier):
    start_mt5()
    for symbol_ft, df in symbol_data.items():
        df = add_super_trend_indicator(df,atr_period,multiplier)
        df = add_squeeze_momentum_indicator(df)

        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.rename(columns={'time': "date"}, inplace=True)

        last_row = df.iloc[-1, :]
        is_uptrend = last_row['Supertrend']
        close = last_row["close"]
        low = last_row["low"]
        high = last_row["high"]
        open = last_row["open"]
        date = last_row["date"]

        # it is the max value of the price of the double peak/double bottom pattern
        price1 = np.nan
        # it is the min value of the price of the double peak/double bottom pattern
        price0 = np.nan
        # It indicates the price of enter after the trigger signal happened.
        # For double bottom, enter only happened when the close price is higher than price1 as shown below.
        # For double peak, enter only happened when the close price is lower than price0 as shown below.
        price2 = np.nan
        # The exit price of the trade
        price3 = np.nan

        squeeze_off = last_row['squeeze_off']
        squeeze_momentum_bar_up = last_row['squeeze_momentum_bar_up']
        stop_loss = None
        target_profit = None
        had_deal_before = False
        order_type = None
        # initial condition
        order_in_position = mt5.positions_get(symbol=symbol_ft)
        open_price = None
        close_price = None

        def check_test_id(deal):
            if deal.comment == test_id:
                return True
            return False

        class_order_in_position = filter(check_test_id, order_in_position)
        class_order_in_position = tuple(class_order_in_position)
        if len(class_order_in_position) != 0:
            in_position = True
            order_type = class_order_in_position[0].type
        else:
            in_position = False
            # from_date=datetime(2023,1,1).timestamp()
            # to_date=datetime(2023,12,1).timestamp()
            timezone = pytz.timezone("Asia/Hong_Kong")
            utc_from = start_date - timedelta(days=180)
            print('utc_from: ', utc_from)
            
            
            utc_from = datetime(utc_from.year, utc_from.month, utc_from.day,
                            hour=utc_from.hour, minute=utc_from.minute,tzinfo=timezone)
            utc_form_timestamp = utc_from.timestamp()
            
            # utc_from = datetime(2023, 1, 1, tzinfo=pytz.timezone('Hongkong'))
            date_to = datetime.now().astimezone(pytz.timezone("Asia/Hong_Kong"))
            date_to = datetime(date_to.year, date_to.month, date_to.day,
                            hour=date_to.hour, minute=date_to.minute)
            date_to_timestamp = date_to.timestamp()
            
            history_deals = mt5.history_deals_get(utc_form_timestamp, date_to_timestamp, group=symbol_ft)
            # history_deals = mt5.history_deals_get(utc_from, date_to, group=pair)
            
            class_history_deals = filter(check_test_id, history_deals)
            class_history_deals = tuple(class_history_deals)
            if len(class_history_deals) != 0:
                had_deal_before = True
                last_position = class_history_deals[-1].position_id
                last_deals = mt5.history_deals_get(position=last_position)
                open_order_id = last_deals[-2].order
                close_order_id = last_deals[-1].order
                open_order = mt5.history_orders_get(ticket=open_order_id)
                if len(open_order) != 0:
                    stop_loss = open_order[0].sl
                    target_profit = open_order[0].tp
                    order_type = open_order[0].type
                    open_price = open_order[0].price_current
                close_order = mt5.history_orders_get(ticket=close_order_id)
                if len(close_order) != 0:
                    close_price = close_order[0].price_current

        # equity = investment
        commission = 5
        # Stoploss=stopLoss
        share = 0
        entry = []
        exit = []

        # Those are the lists used to log all the entries for the open date,close date,open price, close price of the trade
        trade_type = []
        trade_triggerdate = []
        trade_OpenDate = []
        trade_CloseDate = []
        trade_OpenPrice = []
        trade_ClosePrice = []
        trade_ExitReason = []

        # for i in range(1, len(df)):
        if test_id:
            print(f"test_id: {test_id}")
        if date:
            print(date)
        if in_position:
            print(f"in_position: {in_position}")
        if is_uptrend:
            print(f"is_uptrend: {is_uptrend}")
        # squeeze_off = True
        if squeeze_off:
            print(f"squeeze_off: {squeeze_off}")
        # squeeze_momentum_bar_up = False
        if squeeze_momentum_bar_up:
            print(f"squeeze_momentum_bar_up: {squeeze_momentum_bar_up}")
        if had_deal_before:
            print(f"had_deal_before: {had_deal_before}")
        if order_type:
            print(f"order_type: {order_type}")
        if stop_loss:
            print(f"stop_loss: {stop_loss}")
        if target_profit:
            print(f"target_profit: {target_profit}")
        if open_price:
            print(f"open_price: {open_price}")
        if close_price:
            print(f"close_price: {close_price}")
        
        current_status = {"test_id": test_id if test_id else None, 
                          "date": date if date else None, 
                          "strategy":{
                              "is_uptrend":is_uptrend if is_uptrend else None, 
                              "squeeze_off":squeeze_off if squeeze_off else None,
                              "squeeze_momentum_bar_up":squeeze_momentum_bar_up if squeeze_momentum_bar_up else None
                              },
                          "in_position":in_position if in_position else None,
                          "had_deal_before":had_deal_before if had_deal_before else None, 
                          "order_type_last_deal": order_type if order_type else None,
                          "stop_loss_price_last_open_deal":stop_loss if stop_loss else None, 
                          "target_profit_price_last_open_deal":target_profit if target_profit else None,
                          "open_price_last_open_deal":open_price if open_price else None,
                          "close_price_last_close_deal":close_price if close_price else None}
        print(current_status)

        if not in_position and had_deal_before:

            # order_type (last open deal’s type) equals buy
            if order_type == 0:
                # last closing deal's close price compared to last open deal’s stop loss 
                if close_price <= stop_loss:
                    exit.append((date, close_price))
                    print(
                        f'Closed buy at {stop_loss} on {date.strftime("%Y/%m/%d")}, reason "Buy reached Stop Loss"')
                elif close_price >= target_profit:
                    exit.append((date, close_price))
                    print(
                        f'Closed buy at {target_profit} on {date.strftime("%Y/%m/%d")}, reason "Buy reached Profit Target"')
            
            if order_type == 1:
                if stop_loss <= close_price:
                    exit.append((date, close_price))
                    print(
                        f'Closed sell at {stop_loss} on {date.strftime("%Y/%m/%d")}, reason "Sell reached Stop Loss"')
                elif target_profit >= close_price:
                    exit.append((date, close_price))
                    print(
                        f'Closed sell at {target_profit} on {date.strftime("%Y/%m/%d")}, reason "Sell reached Profit Target"')


        check_completed = False

        # if not in position & price is on uptrend -> buy and entry in
        # add squeeze off and momentum bar going up later
        if is_uptrend:

            if not in_position:
                # if not in position & uptrend, then buy
                res1 = open_pending_position(
                    symbol_ft, lot_size, "BUY", test_id, magic, tp_distance=tp_size, sl_distance=sl_size)
                if res1.retcode == 10009:
                    ticket1 = res1.order
                    size1 = res1.volume
                    entry.append((date, res1.price))
                    # trade_OpenDate.append(date)
                    print(
                        f'Buy {size1} lots at {res1.price} on {date.strftime("%Y/%m/%d")}, reason "SuperTrend UpTrend"')
                else:
                    print("Failed to send BUY order")
                    print("The failure code is: "+str(res1.retcode))


                check_completed = True

            elif in_position and order_type == 1: 
                
                # if uptrend and in sell position then "Close sell, then buy"

                ticket = class_order_in_position[0].ticket
                close_open_position(ticket, symbol_ft, lot_size, "BUY", test_id, magic)

                res1 = open_pending_position(
                    symbol_ft, lot_size, "BUY", test_id, magic, tp_distance=tp_size, sl_distance=sl_size)
                if res1.retcode == 10009:
                    ticket1 = res1.order
                    size1 = res1.volume
                    entry.append((date, res1.price))
                    # trade_OpenDate.append(date)
                    print(
                        f'Sell {size1} lots at {res1.price} on {date.strftime("%Y/%m/%d")}, reason "SuperTrend Not DownTrend anymore"')

                else:
                    print("Failed to send BUY order")
                    print("The failure code is: "+str(res1.retcode))
                


                check_completed = True  

        elif not is_uptrend:

            if not in_position:

                # if not in position & downtrend, then "sell"
                res1 = open_pending_position(
                    symbol_ft, lot_size, "SELL", test_id, magic, tp_distance=tp_size, sl_distance=sl_size)
                if res1.retcode == 10009:
                    ticket1 = res1.order
                    size1 = res1.volume
                    entry.append((date, res1.price))
                    # trade_OpenDate.append(date)
                    print(
                        f'Sell {size1} lots at {res1.price} on {date.strftime("%Y/%m/%d")}, reason "SuperTrend DownTrend"')
                else:
                    print("Failed to send SELL order")
                    print("The failure code is: "+str(res1.retcode))


                check_completed = True

        if not check_completed:
            if not in_position:
                print("Currently: Not in position")
                print("### No indicator triggered action ###")
            else:
                print(f"Currently: In position {order_in_position}")
                print("### No indicator triggered action ###")


def check_mt5_trade_status(symbol_ft, test_id):
    date = None
    stop_loss = 0
    target_profit = 0
    had_deal_before = False
    order_type = None
    # initial condition
    order_in_position = mt5.positions_get(symbol=symbol_ft)
    open_price = None
    close_price = None

    # entry = []
    exit = []

    def check_test_id(deal):
        if deal.comment == test_id:
            return True
        return False

    class_order_in_position = filter(check_test_id, order_in_position)
    class_order_in_position = tuple(class_order_in_position)
    if len(class_order_in_position) != 0:
        in_position = True
        order_type = class_order_in_position[0].type
        date = datetime.now().astimezone(pytz.timezone("Asia/Hong_Kong"))
    else:
        in_position = False
        # from_date=datetime(2023,1,1).timestamp()
        # to_date=datetime(2023,12,1).timestamp()
        timezone = pytz.timezone("Asia/Hong_Kong")
        utc_from = datetime.now().astimezone(pytz.timezone("Asia/Hong_Kong")) - timedelta(days=180)

        utc_from = datetime(utc_from.year, utc_from.month, utc_from.day,
                        hour=utc_from.hour, minute=utc_from.minute,tzinfo=timezone)
        utc_from_timestamp = utc_from.timestamp()

        # utc_from = datetime(2023, 1, 1, tzinfo=pytz.timezone('Hongkong'))
        date_to = datetime.now().astimezone(pytz.timezone("Asia/Hong_Kong"))
        date = date_to
        date_to = datetime(date_to.year, date_to.month, date_to.day,
                        hour=date_to.hour, minute=date_to.minute)
        date_to_timestamp = date_to.timestamp()

        history_deals = mt5.history_deals_get(utc_from_timestamp, date_to_timestamp, group=symbol_ft)
        # history_deals = mt5.history_deals_get(utc_from, date_to, group=pair)

        class_history_deals = filter(check_test_id, history_deals)
        class_history_deals = tuple(class_history_deals)
        if len(class_history_deals) != 0:
            had_deal_before = True
            last_position = class_history_deals[-1].position_id
            last_deals = mt5.history_deals_get(position=last_position)
            open_order_id = last_deals[-2].order
            close_order_id = last_deals[-1].order
            open_order = mt5.history_orders_get(ticket=open_order_id)
            if len(open_order) != 0:
                stop_loss = open_order[0].sl
                target_profit = open_order[0].tp
                order_type = open_order[0].type
                open_price = open_order[0].price_current
            close_order = mt5.history_orders_get(ticket=close_order_id)
            if len(close_order) != 0:
                close_price = close_order[0].price_current
    
    
    if not in_position and had_deal_before:

        # order_type (last open deal’s type) equals buy
        if order_type == 0:
            # last closing deal's close price compared to last open deal’s stop loss 
            if close_price <= stop_loss:
                exit.append((date, close_price))
                print(
                    f'Closed buy at {stop_loss} on {date.strftime("%Y/%m/%d")}, reason "Buy reached Stop Loss"')
            elif close_price >= target_profit:
                exit.append((date, close_price))
                print(
                    f'Closed buy at {target_profit} on {date.strftime("%Y/%m/%d")}, reason "Buy reached Profit Target"')
        
        if order_type == 1:
            if stop_loss <= close_price:
                exit.append((date, close_price))
                print(
                    f'Closed sell at {stop_loss} on {date.strftime("%Y/%m/%d")}, reason "Sell reached Stop Loss"')
            elif target_profit >= close_price:
                exit.append((date, close_price))
                print(
                    f'Closed sell at {target_profit} on {date.strftime("%Y/%m/%d")}, reason "Sell reached Profit Target"')

    # if not check_completed:
    if not in_position:
        print("Currently: Not in position")
        # print("### No indicator triggered action ###")
    else:
        print(f"Currently: In position {order_in_position}")
        # print("### No indicator triggered action ###")

################################
##### Trading strategies ######
################################

#! add find best
# atr_period = 10
# multiplier = 3

# symbol = 'AAPL'
# df = yf.download(symbol, start='2020-01-01')


def add_super_trend_indicator(df,atr_period,multiplier):

    high = df["high"]
    low = df["low"]
    close = df["close"]

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

    # return pd.DataFrame({
    #     'Supertrend': supertrend,
    #     'Final Lowerband': final_lowerband,
    #     'Final Upperband': final_upperband
    # }, index=df.index)


# def add_super_trend_indicator(df):
#     supertrend_indicator = super_trend(df)
#     df = df.join(supertrend_indicator)
#     return df


# parameter setup
length = 20
mult = 2
length_KC = 20
mult_KC = 1.5


def add_squeeze_momentum_indicator(df):
    # calculate BB
    m_avg = df["close"].rolling(window=length).mean()
    m_std = df["close"].rolling(window=length).std(ddof=0)
    df['upper_BB'] = m_avg + mult * m_std
    df['lower_BB'] = m_avg - mult * m_std

    # calculate true range
    df['tr0'] = abs(df["high"] - df["low"])
    df['tr1'] = abs(df["high"] - df["close"].shift())
    df['tr2'] = abs(df["low"] - df["close"].shift())
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)

    # calculate KC
    range_ma = df['tr'].rolling(window=length_KC).mean()
    df['upper_KC'] = m_avg + range_ma * mult_KC
    df['lower_KC'] = m_avg - range_ma * mult_KC

    # calculate bar value
    highest = df["high"].rolling(window=length_KC).max()
    lowest = df["low"].rolling(window=length_KC).min()
    m1 = (highest + lowest)/2
    df['bar_value'] = (df["close"] - (m1 + m_avg)/2)
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

    return df


# def add_squeeze_momentum_indicator(df):
#     squeeze_momentum_indicator = squeeze_momentum(df)
#     df1 = df.join(squeeze_momentum_indicator)
#     return df1


################################
##### Scheduled Tasks ######
################################

# this is for sample only, no use
def live_trading():
    symbol="BTCUSD"
    schedule.every().hour.at(":00").do(run_trader, symbol, mt5.TIMEFRAME_M15)
    schedule.every().hour.at(":15").do(run_trader, symbol, mt5.TIMEFRAME_M15)
    schedule.every().hour.at(":30").do(run_trader, symbol, mt5.TIMEFRAME_M15)
    schedule.every().hour.at(":45").do(run_trader, symbol, mt5.TIMEFRAME_M15)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    print("MT5 tradingbot is being executed...")
    live_trading()
