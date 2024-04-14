# https://alpaca.markets/blog/introducing-news-api-for-real-time-fiancial-news/

import os
import json
# import websocket
from alpaca_trade_api import REST
import boto3
import requests
import os
from dotenv import load_dotenv
import time
# import google.generativeai as genai


news_result = []
# news = rest_client.get_news("AAPL", "2023-12-01", "2023-12-10", limit=3)
load_dotenv()




def get_dynamodb_item(table, news_id):
    try:
        response = table.get_item(Key={'id': news_id})
        item = response.get('Item', None)
        if item is None:
            print(f"No item found in DynamoDB with news_id: {news_id}")
        return item
    except Exception as e:
        print(f"Error retrieving item from DynamoDB: {e}")
        return None

def put_dynamodb_item(table, item):
    # Set the number of retries and the delay between retries
    retries = 3
    delay = 1

    for i in range(retries):
        try:
            table.put_item(Item=item)
            return
        except Exception as e:
            print(f"Error saving item to DynamoDB: {e}")
            # Sleep for the specified delay before retrying
            time.sleep(delay)
            # Increase the delay between retries
            delay *= 2

def analyze_news(symbol, start_date, end_date, limit=3):
    # Set API keys from environment variables
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
    os.environ["APCA_API_KEY_ID"] = os.getenv("APCA_API_KEY_ID")
    os.environ["APCA_API_SECRET_KEY"] = os.getenv("APCA_API_SECRET_KEY")

    # Initialize DynamoDB table
    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    region_name = os.getenv('AWS_REGION')

    dynamodb = boto3.resource('dynamodb', 
                            aws_access_key_id=aws_access_key_id, 
                            aws_secret_access_key=aws_secret_access_key, 
                            region_name=region_name)

    table = dynamodb.Table('InvestNews-ambqia6vxrcgzfv4zl44ahmlp4-dev')

    # Initialize Alpaca REST API client
    rest_client = REST(os.getenv("APCA_API_KEY_ID"), os.getenv("APCA_API_SECRET_KEY"))

    news_result = []

    # Fetch news from Alpaca API
    news = rest_client.get_news(symbol, start_date, end_date, limit=limit)

    for item_news in news:
        current_event = item_news.__dict__["_raw"]
        print('current_event: ', current_event)
        news_id = str(current_event["id"])

        # Check if news ID is in DynamoDB
        dynamo_item = get_dynamodb_item(table, news_id)
        
        if dynamo_item:
            # print(" Use the data from DynamoDB")
            item_result = dynamo_item
        else:
            # print("Analyze the headline using OpenAI")
            api_request_body = {
                "model": "gpt-3.5-turbo",
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": "Only respond with a number from -100 to 100 detailing the impact of the headline on the stock price, with negative indicating price goes down, and positive indicating price goes up",
                    },
                    {
                        "role": "user",
                        "content": f"Given the headline '{current_event['headline']}', what is the impact of this headline on the stock price, with negative indicating price goes down, and positive indicating price goes up?",
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
            company_impact = int(data["choices"][0]["message"]["content"])

            # Save analyzed data
            item_result = {
                "id": str(news_id),
                "date_time": current_event["created_at"],
                "headline": current_event["headline"],
                "headline_impact": str(company_impact),
                "ticker_symbol": current_event["symbols"],
                "url": current_event["url"],
                "excerpt": "No action"
            }

            if company_impact >= 50:
                item_result["excerpt"] = "Buy Stock"
                # Place buy order logic here

            elif company_impact <= -50:
                item_result["excerpt"] = "Sell Stock"
                # Place sell order logic here

            # Save the result to DynamoDB
            put_dynamodb_item(table, item_result)

        news_result.append(item_result)

    return news_result

# def analyze_news_gemini(symbol, start_date, end_date, limit=3):
#     os.environ["APCA_API_KEY_ID"] = os.getenv("APCA_API_KEY_ID")
#     os.environ["APCA_API_SECRET_KEY"] = os.getenv("APCA_API_SECRET_KEY")
#     rest_client = REST(os.getenv("APCA_API_KEY_ID"), os.getenv("APCA_API_SECRET_KEY"))
    
#     GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
#     genai.configure(api_key=GOOGLE_API_KEY)
    

#     news_result = []

#     news = rest_client.get_news(symbol, start_date, end_date, limit=limit)

#     for item_news in news:
#         item_result = {}
#         current_event = item_news.__dict__["_raw"]
#         item_result["id"] = current_event["id"]
#         item_result["date_time"] = current_event["created_at"]
#         item_result["headline"] = current_event["headline"]

#         # Ask ChatGPT its thoughts on the headline
#         prompt = f"Given the headline '{current_event['headline']}', show me a number from -100 to 100 detailing the impact of this headline on stock price, with negative indicating price goes down, and positive indicating price goes up. Only return number, not with other context"
        
#         model = genai.GenerativeModel('gemini-pro')
#         # model = genai.GenerativeModel('gemini-1.5-pro')
        
#         response = model.generate_content(
#         prompt, 
#         generation_config=genai.types.GenerationConfig(
#             # Only one candidate for now.
        
#             temperature=0)
#         )
#         # response = chat.send_message("Basic on the data, Should I buy " + ticker + "?" + "Give me 1 - 100 mark."+ "just give the mark, no need other context")


#         print('response.text: ', response.text)

#         try:
#             company_impact = int(response.text)
#         except ValueError:
#             company_impact = 0

#         item_result["headline_impact"] = company_impact

#         ticker_symbol = current_event["symbols"]
#         item_result["ticker_symbol"] = ticker_symbol
        
#         if company_impact:

#             if company_impact >= 50:
#                 item_result["excerpt"] = "Buy Stock"
#                 # Place buy order

#             elif company_impact <= -50:
#                 item_result["excerpt"] = "Sell Stock"
#                 # Place sell order

#             else:
#                 item_result["excerpt"] = "No action"

#         news_result.append(item_result)

#     return news_result


def analyze_news_gemini_request(symbol, start_date, end_date, limit=3):
    os.environ["APCA_API_KEY_ID"] = os.getenv("APCA_API_KEY_ID")
    os.environ["APCA_API_SECRET_KEY"] = os.getenv("APCA_API_SECRET_KEY")
    rest_client = REST(os.getenv("APCA_API_KEY_ID"), os.getenv("APCA_API_SECRET_KEY"))
    
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    # genai.configure(api_key=GOOGLE_API_KEY) 
    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    region_name = os.getenv('AWS_REGION')

    dynamodb = boto3.resource('dynamodb', 
                            aws_access_key_id=aws_access_key_id, 
                            aws_secret_access_key=aws_secret_access_key, 
                            region_name=region_name)

    table = dynamodb.Table('InvestNews-ambqia6vxrcgzfv4zl44ahmlp4-dev')
    

    news_result = []

    news = rest_client.get_news(symbol, start_date, end_date, limit=limit)

    for item_news in news:
        current_event = item_news.__dict__["_raw"]
        # print('current_event: ', current_event)
        news_id = str(current_event["id"])

        # Check if news ID is in DynamoDB
        dynamo_item = get_dynamodb_item(table, news_id)
        
        if dynamo_item:
            # print(" Use the data from DynamoDB")
            item_result = dynamo_item
        else:

            # Ask ChatGPT its thoughts on the headline
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent?key={GOOGLE_API_KEY}"

            headers = {
                'Content-Type': 'application/json'
            }

            data = {
                "contents": [{
                    "parts": [{
                        "text": f"Given the headline '{current_event['headline']}', show me a number from -100 to 100 detailing the impact of this headline on stock price, with negative indicating price goes down, and positive indicating price goes up. Only return number, not with other context"
                    }]
                }],
                "generationConfig": {
                    "temperature": 0,

                }
            }

            response = requests.post(url, headers=headers, json=data)
            # print('response: ', response.text)
            response_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            print('response_text: ', response_text)
            if response.status_code == 200:

                try:
                    company_impact = int(response_text)
                except ValueError:
                    company_impact = 0

                            # Save analyzed data
                item_result = {
                    "id": str(news_id),
                    "date_time": current_event["created_at"],
                    "headline": current_event["headline"],
                    "headline_impact": str(company_impact),
                    "ticker_symbol": current_event["symbols"],
                    "url": current_event["url"],
                    "excerpt": "No action"
                }

                if company_impact >= 50:
                    item_result["excerpt"] = "Buy Stock"
                    # Place buy order logic here

                elif company_impact <= -50:
                    item_result["excerpt"] = "Sell Stock"
                    # Place sell order logic here

                # Save the result to DynamoDB
                put_dynamodb_item(table, item_result)

        news_result.append(item_result)
    return news_result
# Example usage:
# Replace 'AAPL', '2023-01-01', '2023-01-31' with your desired symbol and date range
if __name__ == '__main__':
    print(analyze_news_gemini_request('AAPL', '2023-01-01', '2023-02-28'))