

code_string = '''
import yfinance as yf
ticker = "AAPL"
df = yf.download(ticker, start="2023-01-01", end="2023-12-31")
print(df.head())
'''

try:
    exec(code_string)
except Exception as e:
    print(f"An error occurred: {e}")