import requests
from dotenv import load_dotenv, find_dotenv
import os
import pandas as pd
load_dotenv(find_dotenv())
ALPHAVANTAGE_API_KEY = os.getenv('ALPHAVANTAGE_API_KEY')


# replace the "demo" apikey below with your own key from https://www.alphavantage.co/support/#api-key
# url = f'https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=AAPL&apikey={ALPHAVANTAGE_API_KEY}'
url = f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=IBM&interval=5min&apikey={ALPHAVANTAGE_API_KEY}'
print(url)
r = requests.get(url)
data = r.json()

# Convert the data to a DataFrame
df = pd.DataFrame(data['Time Series (5min)']).transpose()
df.columns = ['open', 'high', 'low', 'close', 'volume']

print(df)