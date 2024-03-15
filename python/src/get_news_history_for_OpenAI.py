# https://alpaca.markets/blog/introducing-news-api-for-real-time-fiancial-news/

import os
import json
import websocket
from alpaca_trade_api import REST
import requests
import os
from dotenv import load_dotenv


news_result = []
# news = rest_client.get_news("AAPL", "2023-12-01", "2023-12-10", limit=3)
load_dotenv()

def analyze_news(symbol, start_date, end_date, limit=3):
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
    os.environ["APCA_API_KEY_ID"] = os.getenv("APCA_API_KEY_ID")
    os.environ["APCA_API_SECRET_KEY"] = os.getenv("APCA_API_SECRET_KEY")
    rest_client = REST(os.getenv("APCA_API_KEY_ID"), os.getenv("APCA_API_SECRET_KEY"))

    news_result = []

    news = rest_client.get_news(symbol, start_date, end_date, limit=limit)

    for item_news in news:
        item_result = {}
        current_event = item_news.__dict__["_raw"]
        item_result["id"] = current_event["id"]
        item_result["date_time"] = current_event["created_at"]
        item_result["headline"] = current_event["headline"]

        # Ask ChatGPT its thoughts on the headline
        api_request_body = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": "Only respond with a number from -100 to 100 detailing the impact of the headline on stock price, with negative indicating price goes down, and positive indicating price goes up",
                },
                {
                    "role": "user",
                    "content": f"Given the headline '{current_event['headline']}', show me a number from -100 to 100 detailing the impact of this headline on stock price, with negative indicating price goes down, and positive indicating price goes up",
                },
            ],
        }

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"],
                "Content-Type": "application/json",
            },
            json=api_request_body,
        )

        data = response.json()
        company_impact = int(data["choices"][0]["message"]["content"])
        item_result["headline_impact"] = company_impact

        ticker_symbol = current_event["symbols"]
        item_result["ticker_symbol"] = ticker_symbol

        if company_impact >= 50:
            item_result["excerpt"] = "Buy Stock"
            # Place buy order

        elif company_impact <= -50:
            item_result["excerpt"] = "Sell Stock"
            # Place sell order

        else:
            item_result["excerpt"] = "No action"

        news_result.append(item_result)

    return news_result

if __name__ == "__main__":
    news_results = analyze_news("BTCUSD", "2023-12-01", "2023-12-10", limit=3)
    print(news_results)