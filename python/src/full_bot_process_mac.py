# import MetaTrader5 as mt5
import mt5_tradingbot_mac as ft
import backtesting_mac as bt
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import yfinance as yf
import schedule
import time
import threading
# import multiprocessing
import requests
import json
from mt5linux import MetaTrader5
import find_best as mst
mt5 = MetaTrader5(
    # host = 'localhost',
    host = '18.141.245.200',
    port = 18812      
)  

timeframe_minutes = {
    'M1': mt5.TIMEFRAME_M1,
    'M2': mt5.TIMEFRAME_M2,
    'M3': mt5.TIMEFRAME_M3,
    'M4': mt5.TIMEFRAME_M4,
    'M5': mt5.TIMEFRAME_M5,
    'M6': mt5.TIMEFRAME_M6,
    'M10': mt5.TIMEFRAME_M10,
    'M12': mt5.TIMEFRAME_M12,
    'M15': mt5.TIMEFRAME_M15,
    'M20': mt5.TIMEFRAME_M20,
    'M30': mt5.TIMEFRAME_M30,
    'H1': mt5.TIMEFRAME_H1,
    'H2': mt5.TIMEFRAME_H2,
    'H3': mt5.TIMEFRAME_H3,
    'H4': mt5.TIMEFRAME_H4,
    'H6': mt5.TIMEFRAME_H6,
    'H8': mt5.TIMEFRAME_H8,
    'D1': mt5.TIMEFRAME_D1,
    'W1': mt5.TIMEFRAME_W1,
    'MN!': mt5.TIMEFRAME_MN1
}
# from flask import Flask, jsonify, request

# app = Flask(__name__)


class Test:
    def __init__(self, test_strategy_name="SuperTrend", strategy_type = "Trend Following", test_id="TESTING", test_name = "Test", mt5_magic_id = None, bt_symbol='BTC-USD', bt_atr_period=6,bt_multiplier=10,
                 bt_start_date=datetime(2020, 1, 1), bt_end_date=datetime(2023, 3, 1),
                 bt_2nd_start_date=datetime(2023, 3, 1), bt_2nd_end_date=datetime(2023, 6, 30), 
                 bt_time_frame_backward='1d', bt_initial_investment=100000000,
                 bt_lot_size=2000, bt_sl_size=0, bt_tp_size=0, bt_commission = 5,
                 ft_symbol="BTCUSD", ft_start_date=None, ft_end_date=None,
                 ft_time_frame_forward=mt5.TIMEFRAME_M3, ft_initial_investment=100000, ft_lot_size=0.1,
                 ft_sl_size=5000, ft_tp_size=5000):
        self.test_strategy_name = test_strategy_name
        self.strategy_type = strategy_type
        self.bt_symbol = bt_symbol
        self.bt_start_date = datetime.strptime(bt_start_date, "%Y-%m-%d") if isinstance(bt_start_date, str) else bt_start_date
        self.bt_end_date = datetime.strptime(bt_end_date, "%Y-%m-%d") if isinstance(bt_end_date, str) else bt_end_date
        self.bt_2nd_start_date = datetime.strptime(bt_2nd_start_date, "%Y-%m-%d") if isinstance(bt_2nd_start_date, str) else bt_2nd_start_date
        self.bt_2nd_end_date = datetime.strptime(bt_2nd_end_date, "%Y-%m-%d") if isinstance(bt_2nd_end_date, str) else bt_2nd_end_date
        self.bt_time_frame_backward = bt_time_frame_backward
        self.bt_initial_investment = bt_initial_investment
        self.bt_lot_size = bt_lot_size
        self.bt_sl_size = bt_sl_size
        self.bt_tp_size = bt_tp_size
        self.bt_commission = bt_commission
        # self.bt_stop_loss = bt_stop_loss
        # self.bt_target_profit = bt_target_profit

        # forward-testing parameters
        self.ft_symbol = ft_symbol
        self.ft_start_date = ft_start_date
        self.ft_end_date = ft_end_date
        self.ft_time_frame_forward = ft_time_frame_forward
        self.ft_initial_investment = ft_initial_investment
        self.ft_lot_size = ft_lot_size
        self.ft_sl_size = ft_sl_size  # To multiply with point
        self.ft_tp_size = ft_tp_size  # To multiply with point
        
        #back-testing parameters
        self.bt_price_data_with_indicator_1st = None
        self.bt_price_data_with_indicator_2nd = None
        self.bt_price_data_with_indicator_all = None
        self.bt_atr_period = bt_atr_period
        self.bt_multiplier = bt_multiplier
        
        self.bt_1st_roi = None
        self.bt_2nd_roi = None
        self.bt_overall_roi = None

        self.bt_1st_entries = None
        self.bt_2nd_entries = None
        self.bt_overall_entries = None
        
        self.bt_1st_exits = None
        self.bt_2nd_exits = None
        self.bt_overall_exits = None
        
        self.bt_1st_final_equity = None
        self.bt_2nd_final_equity = None
        self.bt_overall_final_equity = None
        
        self.bt_1st_equity_per_day = None
        self.bt_2nd_equity_per_day = None
        self.bt_overall_equity_per_day = None
        # self.bt_roi = None

        self.ft_entries = None
        self.ft_exits = None
        self.ft_final_equity = None
        self.ft_equity_per_day = None
        self.ft_roi = None  

        self.test_id = test_id
        self.test_name = test_name
        self.mt5_magic_id = mt5_magic_id

        self.scheduler = schedule.Scheduler()
        self.state = "Created"
        self.stop_flag_live_trade = False
        self.stop_flag_check_status = False
        self.ft_result_processing = False
        self.ft_getting_result_progress_percentage = 0
        self.elapsed_time = None
        self.estimated_remaining_time = None
        
        self.overall_market_roi = None
        self.overall_max_drawdown = None
        self.overall_win_loss_ratio = None
        self.stock_close_price = None
        self.stock_volume = None
        
        self.s3Key_stock_close_price = None
        self.s3Key_stock_volume = None
        self.s3Key_backtest_data = None
        self.s3Key_forward_test_data = None
        
        
    # Method to update attributes from a dictionary
    def edit_parameters(self, params):
        # Ensure that params is a dictionary
        if not isinstance(params, dict):
            raise TypeError("params must be of type dict")

        # Iterate over the dictionary and set the attributes
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                pass
                # raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{key}'")
                
    def parse_and_convert_parameters(self):
        """
        Parse and convert the input parameters to the appropriate data types.

        This function is called by the constructor to ensure that all of the input parameters are of the correct type.
        """

        # Convert the start and end dates to datetime objects if they are strings.
        self.bt_start_date = datetime.strptime(self.bt_start_date, "%Y-%m-%d") if isinstance(self.bt_start_date, str) else self.bt_start_date
        self.bt_end_date = datetime.strptime(self.bt_end_date, "%Y-%m-%d") if isinstance(self.bt_end_date, str) else self.bt_end_date
        self.bt_2nd_start_date = datetime.strptime(self.bt_2nd_start_date, "%Y-%m-%d") if isinstance(self.bt_2nd_start_date, str) else self.bt_2nd_start_date
        self.bt_2nd_end_date = datetime.strptime(self.bt_2nd_end_date, "%Y-%m-%d") if isinstance(self.bt_2nd_end_date, str) else self.bt_2nd_end_date
        self.ft_start_date = datetime.strptime(self.ft_start_date, "%Y-%m-%d") if isinstance(self.ft_start_date, str) else self.ft_start_date
        self.ft_end_date = datetime.strptime(self.ft_end_date, "%Y-%m-%d") if isinstance(self.ft_end_date, str) else self.ft_end_date

        # Convert the timeframe to an integer if it is a string.
        self.ft_time_frame_forward = timeframe_minutes.get(self.ft_time_frame_forward) if isinstance(self.ft_time_frame_forward, str) else self.ft_time_frame_forward

        # Convert the initial investment, lot size, stop loss size, take profit size, and commission to integers if they are strings.
        self.bt_initial_investment = int(self.bt_initial_investment) if isinstance(self.bt_initial_investment, str) else self.bt_initial_investment
        self.bt_lot_size = float(self.bt_lot_size) if isinstance(self.bt_lot_size, str) else self.bt_lot_size
        self.bt_sl_size = int(self.bt_sl_size) if isinstance(self.bt_sl_size, str) else self.bt_sl_size
        self.bt_tp_size = int(self.bt_tp_size) if isinstance(self.bt_tp_size, str) else self.bt_tp_size
        self.bt_commission = int(self.bt_commission) if isinstance(self.bt_commission, str) else self.bt_commission
        self.ft_initial_investment = int(self.ft_initial_investment) if isinstance(self.ft_initial_investment, str) else self.ft_initial_investment
        self.ft_lot_size = float(self.ft_lot_size) if isinstance(self.ft_lot_size, str) else self.ft_lot_size
        self.ft_sl_size = int(self.ft_sl_size) if isinstance(self.ft_sl_size, str) else self.ft_sl_size
        self.ft_tp_size = int(self.ft_tp_size) if isinstance(self.ft_tp_size, str) else self.ft_tp_size
        self.bt_atr_period = float(self.bt_atr_period) if isinstance(self.bt_atr_period, str) else self.bt_atr_period
        self.bt_multiplier = float(self.bt_multiplier) if isinstance(self.bt_multiplier, str) else self.bt_multiplier
        
    def find_best_parameters_api(self,atr=None, multiplier=None):
        url = "http://findBestLambda-1500609916.ap-southeast-1.elb.amazonaws.com/lambda/find_optimal_parameter"
        first_data = {
            "symbol": str(self.bt_symbol),
            "investment": int(self.bt_initial_investment),
            "commission": int(self.bt_commission),
            "start_date": self.bt_start_date.strftime("%Y-%m-%d"),
            "end_date": self.bt_end_date.strftime("%Y-%m-%d"),
            "interval": str(self.bt_time_frame_backward),
            "lot_size": int(self.bt_lot_size),
            "sl_size": int(self.bt_sl_size),
            "tp_size": int(self.bt_tp_size),
            "atr": int(atr) if atr is not None else None,
            "multiplier": float(multiplier) if multiplier is not None else None
        }
        
        json_data = json.dumps(first_data)
        
        headers = {
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, data=json_data, headers=headers)
        self.bt_atr_period = float(response.json()['ATR Period'])
        self.bt_multiplier = float(response.json()['Multiplier'])

        print(self.bt_start_date.strftime("%Y-%m-%d"))
        print(self.bt_end_date.strftime("%Y-%m-%d"))
        print('self.bt_atr_period: ', self.bt_atr_period)
        print('self.bt_multiplier: ', self.bt_multiplier)
        
    def find_best_parameters(self,atr=None, atr_multiplier=None):
        # data = json.loads(event["body"])
        # print('data: ', data)

        symbol = str(self.bt_symbol)
        investment = int(self.bt_initial_investment)
        commission = int(self.bt_commission)
        start_date = self.bt_start_date.strftime("%Y-%m-%d")
        end_date = self.bt_end_date.strftime("%Y-%m-%d")
        interval = str(self.bt_time_frame_backward)
        lot_size = int(self.bt_lot_size)
        sl_size = int(self.bt_sl_size)
        tp_size = int(self.bt_tp_size)

        atr_period = int(atr) if atr is not None else None
        multiplier = float(atr_multiplier) if atr_multiplier is not None else None
        
        strategy = mst.Supertrend
        backtest = mst.backtest
        
        if atr_period == None or multiplier == None:
            fy_df = mst.get_yf_df(symbol, start_date, end_date, interval)

            atr_period, multiplier, ROI = mst.find_optimal_parameter(fy_df, strategy, backtest, investment, lot_size, sl_size, tp_size,commission,atr_period,multiplier)

        self.bt_atr_period = atr_period
        self.bt_multiplier = multiplier
        
        print(self.bt_start_date.strftime("%Y-%m-%d"))
        print(self.bt_end_date.strftime("%Y-%m-%d"))
        print('self.bt_atr_period: ', self.bt_atr_period)
        print('self.bt_multiplier: ', self.bt_multiplier)


        

    def _update_end_date(self, end_date):
        if end_date and (self.ft_start_date is None or end_date <= self.ft_start_date):
            self.bt_end_date = end_date
        else:
            self.bt_end_date = self.ft_start_date if self.ft_start_date else datetime.now()

    def _fetch_and_visualize_data(self, start_date, end_date, attribute_name,visualize=False):
        past_date = bt.get_data(self.bt_symbol, start_date, end_date, self.bt_time_frame_backward)
        df_super = bt.add_supertrend(past_date, self.bt_atr_period, self.bt_multiplier)
        df_super_squeeze = bt.add_squeeze_momentum(df_super)
        if visualize:
            plt.plot(df_super_squeeze['Close'], label='Close Price')
            plt.plot(df_super_squeeze['Final Lowerband'], 'g', label='Final Lowerband')
            plt.plot(df_super_squeeze['Final Upperband'], 'r', label='Final Upperband')
            plt.legend()
            plt.show()

        setattr(self, attribute_name, df_super_squeeze)    
    

    def bt_get_data_and_add_indicator(self, period=None, start_date=None, end_date=None,visualize=False):
        if start_date:
            self.bt_start_date = start_date
            self._update_end_date(end_date)
            self._fetch_and_visualize_data(self.bt_start_date, self.bt_end_date, 'bt_price_data_with_indicator_all')

        if period:
            period_upper = period.upper()
            if period_upper == "1ST":
                self._fetch_and_visualize_data(self.bt_start_date, self.bt_end_date, 'bt_price_data_with_indicator_1st',visualize)
            elif period_upper == "2ND":
                self._fetch_and_visualize_data(self.bt_2nd_start_date, self.bt_2nd_end_date, 'bt_price_data_with_indicator_2nd',visualize)
            elif period_upper == "ALL":
                self._fetch_and_visualize_data(self.bt_start_date, self.bt_2nd_end_date, 'bt_price_data_with_indicator_all',visualize)

    def fetch_stock_price_and_volume(self, symbol=None, start_date=None, end_date=None):
        symbol = self.bt_symbol if symbol == None else symbol
        start_date = self.bt_start_date if start_date == None else start_date
        end_date = self.bt_2nd_end_date if end_date == None else end_date
        try:
           
            # Fetch historical data from Yahoo Finance
            data = yf.download(symbol, start=start_date, end=end_date)
            

            # Check if the data is empty
            if data.empty:
                return json.dumps({"error": "No data found for the given date range."})

            # Prepare the JSON structure
            stock_close_price_json = {
                "stock_close_price": {
                        "name": "Stock Close Price",
                        "type": "line",
                        "data": [
                            {"date": date.strftime('%Y-%m-%d'), "price": "{:.2f}".format(price)}
                            for date, price in data['Close'].dropna().items()
                        ],
                    },
            }
            
            stock_volume_json = {
                "stock_volume": {
                        "name": "Stock Volume",
                        "type": "line",
                        "data": [
                            {"date": date.strftime('%Y-%m-%d'), "volume": str(int(price)) }
                            for date, price in data['Volume'].dropna().items()
                        ],
                    },
            }

            self.stock_close_price = stock_close_price_json["stock_close_price"]["data"]
            self.stock_volume = stock_volume_json["stock_volume"]["data"]

        except Exception as e:
            # Handle general exceptions
            error_message = f"An error occurred: {str(e)}"
            return json.dumps({"error": error_message})
        
    
    
    def backtest(self, period):
        # Mapping of period keys to their respective data_frame attributes
        period_map = {
            "1ST": ('bt_price_data_with_indicator_1st', 'bt_1st_entries', 'bt_1st_exits', 'bt_1st_roi','bt_1st_final_equity', 'bt_1st_equity_per_day'),
            "2ND": ('bt_price_data_with_indicator_2nd', 'bt_2nd_entries', 'bt_2nd_exits', 'bt_2nd_roi','bt_2nd_final_equity', 'bt_2nd_equity_per_day'),
            "ALL": ('bt_price_data_with_indicator_all', 'bt_overall_entries', 'bt_overall_exits', 'bt_overall_roi','bt_overall_final_equity', 'bt_overall_equity_per_day')
        }

        # Normalize the period to uppercase to ensure case-insensitive matching
        period_key = period.upper()

        # Retrieve the mapping for the provided period; if not found, report an error and return
        if period_key not in period_map:
            print(f"Invalid period: {period}. Valid options are '1ST', '2ND', or 'ALL'.")
            return

        data_frame_attr, entries_attr, exits_attr, roi_attr, final_equity_attr, equity_per_day_attr = period_map[period_key]

        # Fetch the data frame using the mapped attribute name
        data_frame = getattr(self, data_frame_attr, None)
        if data_frame is None:
            print(f"Data frame for period {period} not found.")
            return

        # Perform the backtesting with the data frame
        entry, exit, equity_per_day, final_equity, roi = bt.backtest(
            data_frame, self.bt_initial_investment, self.bt_lot_size, 
            self.bt_sl_size, self.bt_tp_size, self.bt_commission)

        # Update the object's attributes with the results
        setattr(self, entries_attr, entry)
        setattr(self, exits_attr, exit)
        setattr(self, roi_attr, roi)
        setattr(self, final_equity_attr, final_equity)
        setattr(self, equity_per_day_attr, equity_per_day)

        # self.bt_equity_per_day = equity_per_day
        # self.bt_final_equity = final_equity

    # def start_forward_test(self):
    def start_forward_test(self,atr_period=None,multiplier=None):
        ft.start_mt5()
        self.bt_end_date = datetime.now()
        if atr_period == None:
            atr_period = self.bt_atr_period
        # print('self.bt_atr_period: ', type(self.bt_atr_period))
        if multiplier == None:
            multiplier = self.bt_multiplier
        # print('self.bt_multiplier: ', type(self.bt_multiplier))
        

        days_previous = 30
        interval = self.check_mt5_timeframe(self.ft_time_frame_forward)
        if interval >= 1440:
            days_previous = 180
        start_date = datetime.now() - timedelta(days=days_previous)
        ft.start_mt5()
        stock_data = ft.get_rate_data_mt5(
            self.ft_symbol, self.ft_time_frame_forward, start_date)
        if stock_data:
            #! add bt atr and multi -- done
            ft.forward_trade(stock_data, self.ft_lot_size,
                            self.ft_sl_size, self.ft_tp_size, self.ft_start_date, self.test_id,self.mt5_magic_id,atr_period,multiplier)
        else:
            return None
        
    def start_check_trade_status(self):
        ft.start_mt5()
        ft.check_mt5_trade_status(self.ft_symbol, self.test_id)


    def progress_report(self,percentage, elapsed_time, estimated_remaining_time):
        self.elapsed_time = round(elapsed_time,2)
        self.estimated_remaining_time = round(estimated_remaining_time,2)
        self.ft_getting_result_progress_percentage = round(percentage,2)
        # print(f"Function is {percentage:.2f}% complete.")


    def get_forward_test_result(self):
        # self.ft_start_date = datetime.now()
        ft.start_mt5()
        end_date = None
        
        if self.ft_end_date == None:
            end_date = datetime.now()
        else:
            end_date = self.ft_end_date
        print('self.ft_start_date: ', self.ft_start_date)
        print('end_date: ', end_date)
        history_orders = ft.get_forward_test_result(
            self.ft_symbol, self.bt_symbol, self.ft_start_date, end_date, 
            
            self.ft_initial_investment, self.ft_lot_size,
            self.ft_time_frame_forward, self.test_id, self.mt5_magic_id, progress_callback=self.progress_report)
        if history_orders:
            self.ft_roi = history_orders[str(self.ft_symbol)]['roi']
            self.ft_entries = history_orders[str(self.ft_symbol)]['entry_of_deals']
            self.ft_exits = history_orders[str(self.ft_symbol)]['exit_of_deals']
            self.ft_equity_per_day = history_orders[str(self.ft_symbol)]['equity_per_day']
            self.ft_final_equity = history_orders[str(self.ft_symbol)]['final_equity']
            self.ft_result_processing = False
            self.elapsed_time = None
            self.estimated_remaining_time = None
            self.ft_getting_result_progress_percentage = 0
        else:
            return None
        
    def check_mt5_timeframe(self, time_frame):
        timeframe_minutes = {
            mt5.TIMEFRAME_M1: 1,
            mt5.TIMEFRAME_M2: 2,
            mt5.TIMEFRAME_M3: 3,
            mt5.TIMEFRAME_M4: 4,
            mt5.TIMEFRAME_M5: 5,
            mt5.TIMEFRAME_M6: 6,
            mt5.TIMEFRAME_M10: 10,
            mt5.TIMEFRAME_M12: 12,
            mt5.TIMEFRAME_M15: 15,
            mt5.TIMEFRAME_M20: 20,
            mt5.TIMEFRAME_M30: 30,
            mt5.TIMEFRAME_H1: 60,
            mt5.TIMEFRAME_H2: 120,
            mt5.TIMEFRAME_H3: 180,
            mt5.TIMEFRAME_H4: 240,
            mt5.TIMEFRAME_H6: 360,
            mt5.TIMEFRAME_H8: 480,
            mt5.TIMEFRAME_D1: 1440,
            mt5.TIMEFRAME_W1: 10080,
            mt5.TIMEFRAME_MN1: 43200
        }

        if time_frame not in timeframe_minutes:
            print("Invalid timeframe!")
            return None
        else:
            # Get the time interval in minutes for the selected timeframe
            interval = timeframe_minutes[time_frame]
            return interval

    def live_trading(self):
        print('Live trading')
        # A dictionary that maps MetaTrader 5 timeframes to their corresponding time intervals in minutes
        # timeframe_minutes = {
        #     mt5.TIMEFRAME_M1: 1,
        #     mt5.TIMEFRAME_M2: 2,
        #     mt5.TIMEFRAME_M3: 3,
        #     mt5.TIMEFRAME_M4: 4,
        #     mt5.TIMEFRAME_M5: 5,
        #     mt5.TIMEFRAME_M6: 6,
        #     mt5.TIMEFRAME_M10: 10,
        #     mt5.TIMEFRAME_M12: 12,
        #     mt5.TIMEFRAME_M15: 15,
        #     mt5.TIMEFRAME_M20: 20,
        #     mt5.TIMEFRAME_M30: 30,
        #     mt5.TIMEFRAME_H1: 60,
        #     mt5.TIMEFRAME_H2: 120,
        #     mt5.TIMEFRAME_H3: 180,
        #     mt5.TIMEFRAME_H4: 240,
        #     mt5.TIMEFRAME_H6: 360,
        #     mt5.TIMEFRAME_H8: 480,
        #     mt5.TIMEFRAME_D1: 1440,
        #     mt5.TIMEFRAME_W1: 10080,
        #     mt5.TIMEFRAME_MN1: 43200
        # }

        interval = self.check_mt5_timeframe(self.ft_time_frame_forward)

        # Check if the value of self.ft_time_frame_forward is a valid key in the timeframe_minutes dictionary
        # if self.ft_time_frame_forward not in timeframe_minutes:
        #     print("Invalid timeframe!")
        if interval:
        
            # Get the time interval in minutes for the selected timeframe
            # interval = timeframe_minutes[self.ft_time_frame_forward]

            # Schedule the job to run at a specific interval based on the selected timeframe,
            # plus 3 seconds delay
            if interval >= 43200:  # For intervals greater than or equal to 1 month
                self.scheduler.every().month.at("00:00:03").do(
                    self.start_forward_test).tag('monthly', str(interval))

            elif interval >= 10080:  # For intervals greater than or equal to 1 week, but less than 1 month
                self.scheduler.every(interval // 10080).weeks.at("00:00:03").do(
                    self.start_forward_test).tag('weekly', str(interval))

            elif interval >= 1440:  # For intervals greater than or equal to 1 day, but less than 1 week
                self.scheduler.every(interval // 1440).days.at("00:00:03").do(
                    self.start_forward_test).tag('daily', str(interval))

            elif interval >= 60:  # For intervals between 60 minutes and 1 day
                self.scheduler.every(interval // 60).hours.at("00:00:03").do(
                    self.start_forward_test).tag('hourly', str(interval))

            else:  # For intervals less than 60 minutes
                interval_minutes = interval
                for hour in range(0, 24):
                    for minute in range(0, 60, interval_minutes):
                        self.scheduler.every().day.at("{:02d}:{:02d}:03".format(hour, minute)).do(
                            self.start_forward_test).tag('subhourly', str(interval))
        
        # Run the scheduled job continuously
        while True:
            while not self.stop_flag_live_trade:
                self.scheduler.run_pending()
                time.sleep(1)
                print(f"{self.test_id} - Running time frame " + str(self.ft_time_frame_forward))
                

            # mt5.set_callback(self.start_forward_test,
            # mt5.CALLBACK_TYPE.HISTORY)


    # stop_flag = False
    def checking_order_status(self,time_frame):
        print('Checking order status')

        scheduler = schedule.Scheduler()
        # A dictionary that maps MetaTrader 5 timeframes to their corresponding time intervals in minutes
        timeframe_minutes = {
            'S1': 1,
            'S2': 2,
            'S3': 3,
            'S4': 4,
            'S5': 5,
            'S6': 6,
            'S10': 10,
            'S12': 12,
            'S15': 15,
            'S20': 20,
            'S30': 30,
            'H1': 60,
            'H2': 120,
            'H3': 180,
            'H4': 240,
            'H6': 360,
            'H8': 480,
            'D1': 1440,
            'W1': 10080,
            'MN1': 43200
        }

        # Check if the value of time_frame is a valid key in the timeframe_minutes dictionary
        if time_frame not in timeframe_minutes:
            print("Invalid timeframe!")
        else:
            # Get the time interval in minutes for the selected timeframe
            interval = timeframe_minutes[time_frame]

            # Schedule the job to run at a specific interval based on the selected timeframe,
            # plus 3 seconds delay
            if interval >= 43200:  # For intervals greater than or equal to 1 month
                scheduler.every().month.at("00:00:03").do(
                    self.start_check_trade_status).tag('monthly', str(interval))

            elif interval >= 10080:  # For intervals greater than or equal to 1 week, but less than 1 month
                scheduler.every(interval // 10080).weeks.at("00:00:03").do(
                    self.start_check_trade_status).tag('weekly', str(interval))

            elif interval >= 1440:  # For intervals greater than or equal to 1 day, but less than 1 week
                scheduler.every(interval // 1440).days.at("00:00:03").do(
                    self.start_check_trade_status).tag('daily', str(interval))

            elif interval >= 60:  # For intervals between 60 minutes and 1 day
                scheduler.every(interval // 60).hours.at("00:00:03").do(
                    self.start_check_trade_status).tag('hourly', str(interval))

            else:  # For intervals less than 60 minutes
                interval_seconds = interval
                for hour in range(0, 24):
                    for minute in range(0, 60):
                        for second in range(0, 60, interval_seconds):
                            scheduler.every().day.at("{:02d}:{:02d}:{:02d}".format(hour, minute, second)).do(
                                self.start_check_trade_status).tag('second', str(interval))

        # Run the scheduled job continuously
        while True:
            while not self.stop_flag_check_status:
                scheduler.run_pending()
                time.sleep(1)
                print("Running time frame " + str(interval))

            # mt5.set_callback(self.start_forward_test,
            # mt5.CALLBACK_TYPE.HISTORY)

def start_check_status_thread(test_instance):
    print('checking start')
    test_instance.stop_flag_check_status = False
    thread = threading.Thread(target=test_instance.checking_order_status, args=('S3',))
    thread.start()
    # process = multiprocessing.Process(target=test_instance.live_trading)
    # process.start()


def stop_check_status_thread(test_instance):
    test_instance.stop_flag_check_status = True
    print('test_instance.stop_flag_check_status: ', test_instance.stop_flag_check_status)


def start_forward_test_thread(test_instance):
    print('test start')
    test_instance.stop_flag_live_trade = False
    thread = threading.Thread(target=test_instance.live_trading)
    thread.start()
    # process = multiprocessing.Process(target=test_instance.live_trading)
    # process.start()


def stop_forward_test_thread(test_instance):
    test_instance.stop_flag_live_trade = True
    print('test_instance.stop_flag_live_trade: ', test_instance.stop_flag_live_trade)
    


# test_instance = None


# @app.route("/create_test", methods=["POST"])
# def create_test():
#     global test_instance
#     test_instance = Test()  # Create a new test instance from the Test class
#     # You can store the test_instance or perform any required initialization here
#     return jsonify({"message": "Test instance created"})


# @app.route("/start_test", methods=["POST"])
# def start_test():
#     global test_instance
#     if test_instance is None:
#         return jsonify({"error": "Test instance not found"}), 400

#     # if __name__ == "__main__":
#     start_forward_test_thread(test_instance)

#     return jsonify({"message": "Test started"})


# if __name__ == "__main__":
#     app.run()
