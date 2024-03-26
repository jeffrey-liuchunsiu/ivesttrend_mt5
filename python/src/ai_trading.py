import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from mt5linux import MetaTrader5
import time
import os
import requests
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
import google.generativeai as genai
from IPython.display import display
from IPython.display import Markdown
import textwrap
load_dotenv()

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

# Trading parameters
deviation = 20
symbol = 'BTCUSD'
yf_symbol = 'BTC-USD'
lot_size = 0.1
sl_pips = 20000
tp_pips = 20000
check_interval = 60 * 5 * 12 

# Initialize MT5 connection
def start_mt5():
    if not mt5.initialize(login=int(username), password=str(password), server=str(server), path=str(path)):
        print("initialize() failed, error code =", mt5.last_error())
        quit()

# Ensure MT5 is started
start_mt5()

# Download historical data from Yahoo Finance
# df = yf.download(yf_symbol, start="2023-01-01", end=datetime.today().strftime('%Y-%m-%d'))

def openai_singals():
    symbol = "BTC-USD"

    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)

    # Format the dates in a way that yfinance understands
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    # Download the data
    df = yf.download(tickers=symbol, start=start_date_str, end=end_date_str, interval='1h')

    # 2. Use OpenAI API to analyze the dataframe and provide the signal to trade
    # Prepare the prompt for the OpenAI API
    prompt = f"I want to make a trade every hours and sl and tp set on {sl_pips} pips. Analyze the following stocks/forex data for {symbol} and no need any comment and just return recommend a trade action for next hour(buy, sell, hold): {json.dumps(df.to_json())}"
    # print('prompt: ', prompt)
    api_request_body = {
                "model": "gpt-3.5-turbo",
                # "model": "gpt-4",
                "temperature": 0,
                "messages": [
                    {
                        "role": "user",
                        "content": f"{prompt}",
                    },
                ],
            }

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": "Bearer " + os.getenv("OPENAI_API_KEY"),
            "Content-Type": "application/json",
        },
        json=api_request_body,
    )

    data = response.json()
    print('data: ', data)
    signal = data["choices"][0]["message"]["content"]
    return signal

def gemini_singals():
    GOOGLE_API_KEY = os.getenv('gemini_API')
    genai.configure(api_key=GOOGLE_API_KEY)
    
    def to_markdown(text):
        text = text.replace('•', '  *')
        print('text: ', text)
        return Markdown(textwrap.indent(text, '> ', predicate=lambda _: True))
    
    symbol = "BTC-USD"

    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)

    # Format the dates in a way that yfinance understands
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    # Download the data
    df = yf.download(tickers=symbol, start=start_date_str, end=end_date_str, interval='4h')

    # 2. Use OpenAI API to analyze the dataframe and provide the signal to trade
    # Prepare the prompt for the OpenAI API
    # prompt = f"I want to make a trade every hours. Analyze the following stocks/forex/crypto data for {symbol} and no need any comment and just return recommend a trade action for next hour(buy, sell, hold): {json.dumps(df.to_json())}"
    prompt = f"I want to make a trade every 4 hours. Analyze the following stocks/forex/crypto data for {symbol} and no need any comment and just return recommend a trade action for next 4 hour(buy, sell, hold): {json.dumps(df.to_json())}"
    model = genai.GenerativeModel('gemini-pro')
    # model = genai.GenerativeModel('gemini-1.5-pro')
    response = model.generate_content(
    prompt,
    generation_config=genai.types.GenerationConfig(
        # Only one candidate for now.
     
        temperature=0)
    )
    # response = chat.send_message("Basic on the data, Should I buy " + ticker + "?" + "Give me 1 - 100 mark."+ "just give the mark, no need other context")

    to_markdown(response.text)
    return response.text

# SuperTrend calculation function
def supertrend(df, atr_period=7, multiplier=3):
    high = df['High']
    low = df['Low']
    close = df['Close']
    atr_name = 'ATR_' + str(atr_period)
    st_name = 'SuperTrend_' + str(atr_period) + '_' + str(multiplier)
    
    df[atr_name] = df['High'].rolling(atr_period).std()
    df[st_name] = np.nan
    
    for i in range(atr_period, len(df)):
        if (close.iloc[i-1] <= df.at[df.index[i-1], st_name]) or pd.isna(df.at[df.index[i-1], st_name]):
            df.at[df.index[i], st_name] = (high.iloc[i] + low.iloc[i]) / 2 + multiplier * df.at[df.index[i], atr_name]
        else:
            df.at[df.index[i], st_name] = (high.iloc[i] + low.iloc[i]) / 2 - multiplier * df.at[df.index[i], atr_name]
    
    return df

# Apply SuperTrend calculation to the dataframe
# df = supertrend(df)

# Define the trade function
def trade(action, symbol, lot, sl_points, tp_points,magic,comment, deviation=20):
    # Get the current market information
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Failed to find symbol: {symbol}")
        return False

    # Check if the symbol is available for trading
    if not symbol_info.visible:
        print(f"Symbol {symbol} is not visible, trying to switch on")
        if not mt5.symbol_select(symbol, True):
            print("symbol_select failed, exit")
            return False
    trade_type = None
    # Get the current ask/bid prices
    if action == 'buy':
        trade_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask
        sl = round(price - sl_points * symbol_info.point, 2)  # Rounded Stop loss for a buy order
        tp = round(price + tp_points * symbol_info.point, 2)  # Rounded Take profit for a buy order
    elif action == 'sell':
        trade_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid
        sl = round(price + sl_points * symbol_info.point, 2)  # Rounded Stop loss for a sell order
        tp = round(price - tp_points * symbol_info.point, 2)  # Rounded Take profit for a sell order
    else:
        print("Trade action must be 'buy' or 'sell'")
        return False

    # Define the trade request dictionary with rounded SL and TP
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": trade_type,
        "price": round(price, 2),  # Round entry price to 1 decimal place if required
        "sl": float(sl),
        "tp": float(tp),
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # Send the trade request
    result = mt5.order_send(request)
    print('result: ', result)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to send order :( Retcode={result.retcode}")
        return False
    else:
        print("Order sent successfully!")
        return True

# Main trading loop
try:
    while True:
        time.sleep(check_interval)
        # # Download the latest data
        # df = yf.download(yf_symbol, period="1d", interval="1h")
        
        # # Check if the DataFrame is not empty
        # if df.empty:
        #     print("Failed to download data or data is empty.")
        #     continue
        
        # # Apply SuperTrend calculation
        # df = supertrend(df)
        
        # # Add a 'signal' column based on a simple crossover strategy
        # st_col = 'SuperTrend_' + str(7) + '_' + str(3)  # Adjust if you change the default parameters
        # df['signal'] = np.where(df['Close'] > df[st_col], 'buy', 'sell')
        
        # Get the latest signal
        # latest_signal = df['signal'].iloc[-1]
        latest_signal = openai_singals().upper()
        print(f"The latest signal is: {latest_signal}")


        if latest_signal == 'BUY':
            print("Received BUY signal.")
            trade('buy', symbol, lot=lot_size, sl_points=sl_pips, tp_points=tp_pips,magic=7,comment="ChatGPT")
        elif latest_signal == 'SELL':
            print("Received SELL signal.")
            trade('sell', symbol, lot=lot_size, sl_points=sl_pips, tp_points=tp_pips,magic=7,comment="ChatGPT")
            
        # gemini_singal = gemini_singals().upper()
        # print(f"The latest gemini signal is: {gemini_singal}")
        # if gemini_singal == 'BUY':
        #     print("Received BUY signal.")
        #     trade('buy', symbol, lot=lot_size, sl_points=sl_pips, tp_points=tp_pips,magic=8,comment="Gemini")
        # elif gemini_singal == 'SELL':
        #     print("Received SELL signal.")
        #     trade('sell', symbol, lot=lot_size, sl_points=sl_pips, tp_points=tp_pips,magic=8,comment="Gemini")
        
        # Wait before checking again
        

except KeyboardInterrupt:
    print("\nScript interrupted by user.")

finally:
    # Shutdown MT5 connection
    mt5.shutdown()