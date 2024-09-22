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

import requests
from bs4 import BeautifulSoup

def web_search(query: str):
    """Performs a web search and returns a summary of the results."""
    url = f"https://www.google.com/search?q={query}"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    # print(soup)
    print(soup.prettify())      
    # Extract the summary from the search results page
    # summary = soup.findall('div', class_='BNeawe')
    # print(summary)
    # if summary is None:
    #     return "No search results found."
    summary = soup.find_all('BNeawe s3v9rd AP7Wnd')
    print(summary)
    summary_text = ""
    for item in summary:
        summary_text += item.find('span').text + "\n"
    
    # Use genai to summarize the text
    model = genai.GenerativeModel("models/gemini-1.5-flash")
    summary = model.generate_content(f"Summarize this html in 2-3 sentences: {soup.prettify()}")
    return summary.text

tools = [web_search]
instruction = "You are a helpful assistant that can perform web searches and summarize the results."

model = genai.GenerativeModel(
    "models/gemini-1.5-flash", tools=tools, system_instruction=instruction
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
    query = response.parts[0].function_call.args['query']
    return web_search(query)
    

# Usage example:
# while True:
    # user_input = input("Enter your stock-related request: ")
user_input = 'i want to know what is python'
result = handle_stock_request(user_input)
print(result)