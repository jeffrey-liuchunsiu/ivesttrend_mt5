# %% [markdown]
# ##### Copyright 2024 Google LLC.

# %%
# @title Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# %% [markdown]
# # Gemini API: Function calling config
# 
# <table align="left">
#   <td>
#     <a target="_blank" href="https://colab.research.google.com/github/google-gemini/cookbook/blob/main/quickstarts/Function_calling_config.ipynb"><img src="https://www.tensorflow.org/images/colab_logo_32px.png" />Run in Google Colab</a>
#   </td>
# </table>

# %% [markdown]
# Specifying a `function_calling_config` allows you to control how the Gemini API acts when `tools` have been specified. For example, you can choose to only allow free-text output (disabling function calling), force it to choose from a subset of the functions provided in `tools`, or let it act automatically.
# 
# This guide assumes you are already familiar with function calling. For an introduction, check out the [docs](https://ai.google.dev/docs/function_calling).


# %% [markdown]
# To run the following cell, your API key must be stored it in a Colab Secret named `GOOGLE_API_KEY`. If you don't already have an API key, or you're not sure how to create a Colab Secret, see the [Authentication](https://github.com/google-gemini/gemini-api-cookbook/blob/main/quickstarts/Authentication.ipynb) quickstart for an example.

# %%
import os
import google.generativeai as genai
from dotenv import find_dotenv, load_dotenv
from decimal import Decimal
import json# Load environment variables from .env file
load_dotenv(find_dotenv())
key = os.getenv('GOOGLE_API_KEY')
import google.generativeai as genai

genai.configure(api_key=key)

# %% [markdown]
# ## Set up a model with tools
# 
# This example uses 3 functions that control a simple hypothetical lighting system. Using these functions requires them to be called in a specific order. For example, you must turn the light system on before you can change color.
# 
# While you can pass these directly to the model and let it try to call them correctly, specifying the `function_calling_config` gives you precise control over the functions that are available to the model.

# %%
import yfinance as yf

def get_stock_price(symbol: str):
    """Get the most recent price of a stock."""
    stock = yf.Ticker(symbol)
    price = stock.history(period="1d")['Close'].iloc[-1]
    print(f"TRADEBOT: Most recent price of {symbol} is ${price:.2f}")
    return price

def buy_stock(symbol: str, quantity: int):
    """Buy a specified quantity of a stock."""
    price = get_stock_price(symbol)
    total_cost = price * quantity
    print(f"TRADEBOT: Bought {quantity} shares of {symbol} at ${price:.2f} each. Total cost: ${total_cost:.2f}")

def buy_stock_with_usd(symbol: str, usd_amount: float):
    """Buy as many shares as possible with a given USD amount."""
    price = get_stock_price(symbol)
    quantity = int(usd_amount // price)
    total_cost = price * quantity
    print(f"TRADEBOT: With ${usd_amount:.2f}, you can buy {quantity} shares of {symbol} at ${price:.2f} each. Total cost: ${total_cost:.2f}")
    return quantity, total_cost

def sell_stock(symbol: str, quantity: int):
    """Sell a specified quantity of a stock."""
    price = get_stock_price(symbol)
    total_value = price * quantity
    print(f"TRADEBOT: Sold {quantity} shares of {symbol} at ${price:.2f} each. Total value: ${total_value:.2f}")

def sell_stock_with_usd(symbol: str, usd_amount: float):
    """Sell as many shares as possible with a given USD amount."""
    price = get_stock_price(symbol)
    quantity = int(usd_amount // price)
    total_value = price * quantity
    print(f"TRADEBOT: With ${usd_amount:.2f}, you can sell {quantity} shares of {symbol} at ${price:.2f} each. Total value: ${total_value:.2f}")
    return quantity, total_value


trading_controls = [get_stock_price, buy_stock, sell_stock, buy_stock_with_usd, sell_stock_with_usd]
instruction = "You are a helpful trading bot. You can get stock prices, buy stocks, and sell stocks based on yfinance data.  You can also buy and sell stocks with a given USD amount. Do not perform any other tasks."

model = genai.GenerativeModel(
    "models/gemini-1.5-flash", tools=trading_controls, system_instruction=instruction
)

chat = model.start_chat()

# %% [markdown]
# Create a helper function for setting `function_calling_config` on `tool_config`.

# %%
from google.generativeai.types import content_types
from collections.abc import Iterable


def tool_config_from_mode(mode: str, fns: Iterable[str] = ()):
    """Create a tool config with the specified function calling mode."""
    return content_types.to_tool_config(
        {"function_calling_config": {"mode": mode, "allowed_function_names": fns}}
    )


# %%
tool_config = tool_config_from_mode("auto")

def handle_stock_request(user_message):
    """Handles user requests related to stock trading."""
    tool_config = tool_config_from_mode("auto")
    response = chat.send_message(user_message, tool_config=tool_config)
    
    if response.parts[0].function_call:
        function_name = response.parts[0].function_call.name
        args = response.parts[0].function_call.args
        
        # Mapping function names to actual functions
        function_map = {
            "get_stock_price": get_stock_price,
            "sell_stock": sell_stock,
            "buy_stock": buy_stock,
            "buy_stock_with_usd": buy_stock_with_usd,
            "sell_stock_with_usd": sell_stock_with_usd
        }
        
        # Call the corresponding function if it exists in the map
        func = function_map.get(function_name)
        if func:
            return func(**args)  # Unpack arguments directly
        else:
            return "Unknown function called."
    else:
        return "No function call detected in the response."

# Usage example:
while True:
    user_input = input("Enter your stock-related request: ")
    result = handle_stock_request(user_input)
    print(result)