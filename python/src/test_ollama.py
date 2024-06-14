import ollama
from bs4 import BeautifulSoup
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
from datetime import datetime,timedelta, date
import calendar


from AI_utils import coze_api, gemini_api, groq_api
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
            print("Item saved to DynamoDB")
            return
        except Exception as e:
            print(f"Error saving item to DynamoDB: {e}")
            # Sleep for the specified delay before retrying
            time.sleep(delay)
            # Increase the delay between retries
            delay *= 2
            
def get_min_date_time():
    # Initialize DynamoDB
    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    region_name = os.getenv('AWS_REGION')

    dynamodb = boto3.resource('dynamodb', 
                            aws_access_key_id=aws_access_key_id, 
                            aws_secret_access_key=aws_secret_access_key, 
                            region_name=region_name)

    # Specify the table name
    table_name = 'InvestNewsMix-ambqia6vxrcgzfv4zl44ahmlp4-dev'
    table = dynamodb.Table(table_name)

    # Initialize the minimum date_time
    min_date = None

    # Scan the table
    response = table.scan(
        ProjectionExpression="date_time",  # Only fetch the date_time attribute
    )

    # Check and update the minimum date_time
    for item in response['Items']:
        current_date = datetime.strptime(item['date_time'], "%Y-%m-%dT%H:%M:%SZ").date()
        if min_date is None or current_date < min_date:
            min_date = current_date

    # Handle pagination if the response is large
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            ProjectionExpression="date_time",
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        for item in response['Items']:
            current_date = datetime.strptime(item['date_time'], "%Y-%m-%dT%H:%M:%SZ").date()
            if min_date is None or current_date < min_date:
                min_date = current_date


    # Add one day to the minimum date
    next_day = min_date + timedelta(days=1)

    return next_day

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
            time.sleep(1)

        news_result.append(item_result)

    return news_result


def analyze_news_combine_request(symbol, start_date, end_date, limit=3):
    
    os.environ["APCA_API_KEY_ID"] = os.getenv("APCA_API_KEY_ID")
    os.environ["APCA_API_SECRET_KEY"] = os.getenv("APCA_API_SECRET_KEY")
    rest_client = REST(os.getenv("APCA_API_KEY_ID"), os.getenv("APCA_API_SECRET_KEY"))
    
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    COZE_API_KEY = os.getenv('COZE_API_KEY')
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    # genai.configure(api_key=GOOGLE_API_KEY) 
    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    region_name = os.getenv('AWS_REGION')

    dynamodb = boto3.resource('dynamodb', 
                            aws_access_key_id=aws_access_key_id, 
                            aws_secret_access_key=aws_secret_access_key, 
                            region_name=region_name)

    table = dynamodb.Table('InvestNewsMix-ambqia6vxrcgzfv4zl44ahmlp4-dev')
    

    news = rest_client.get_news(symbol, start_date, end_date, limit=limit, sort="asc")
    print('news: ', len(news))

    for index, item_news in enumerate(news, start=1):
        # print('item_news: ', item_news)
        if index % 2 == 0:
            GROQ_API_KEY = os.getenv('GROQ_API_KEY_yahoo')
        if index % 2 == 1:
            GROQ_API_KEY = os.getenv('GROQ_API_KEY')
            
        
        item_result = None
        current_event = item_news.__dict__["_raw"]
        # print('current_event: ', current_event)
        news_id = str(current_event["id"])

        # Check if news ID is in DynamoDB
        dynamo_item = get_dynamodb_item(table, news_id)
        
        if dynamo_item:
            print(f"{news_id}: the data from DynamoDB")

        else:

        # Check if news ID is in DynamoDB
            
            old_table = dynamodb.Table('InvestNews-ambqia6vxrcgzfv4zl44ahmlp4-dev')
            dynamo_item = get_dynamodb_item(old_table, news_id)
            gemini_score = None
            if dynamo_item:
                gemini_score = int(dynamo_item['headline_impact'])
        
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
            }

            # url = 'https://www.benzinga.com/markets/cryptocurrency/24/04/38476692/as-bitcoin-plunges-whale-makes-waves-with-77-67m-deposit-into-kraken'
            url = current_event['url']
            print('url: ', url)
            response = requests.get(url, headers=headers)
            article_content = None
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                article_content = soup.find(id='article-body')
                # print(article_content.text if article_content else "Content not found")
                if article_content:
                    article_content = article_content.text
                # print('article_content: ', article_content)
                
                        
                        
                    system_prompt = f"is it commented news or news. if you think that is a new reutrn a score from -100 to 100. if it is a commented news return None .Only respond with a number from -100 to 100 detailing the impact of the content on the {symbol} price, with negative indicating price goes down, and positive indicating price goes up. Must only return number or None, not with other content"    
                    prompt = f"is it commented news or news. if you think that is a new reutrn a score from -100 to 100. if it is a commented news return None. Given the content '{article_content}', Please check if the content is a news or a comment.Then If the content is a comment return show me a number 0.  If the content is news, show me a number from -100 to 100 detailing the impact of this content on {symbol} price, with negative indicating price goes down, and positive indicating price goes up. Must only return number or None, not with other content"
                        
                    llama_score = groq_api (prompt, system_prompt, GROQ_API_KEY, 0,model="llama3-70b-8192")
                    if gemini_score == None:
                        print("Using Gemini api")
                        gemini_score = gemini_api(prompt,GOOGLE_API_KEY,0,"gemini-1.5-flash-latest")
                    else:
                        print("gemini-1.5-flash-latest: " + str(gemini_score))
                    # coze_api (prompt, COZE_API_KEY)
                    
            
                    print("")
                    
                    if llama_score or gemini_score:
                        try:
                            int(gemini_score)
                        except ValueError:
                            gemini_score = 0
                            
                        try:
                            int(llama_score)
                        except ValueError:
                            llama_score = 0
                        
                        company_impact = round((int(llama_score) + int(gemini_score))/2)

                    
                        
                        if company_impact > 100:
                            company_impact = 100
                        elif company_impact < -100:
                            company_impact = -100
                            
                        

                                    # Save analyzed data
                        item_result = {
                            "id": str(news_id),
                            "date_time": current_event["created_at"],
                            "headline": current_event["headline"],
                            "body": article_content,
                            "body_impact_llama": int(llama_score),
                            "body_impact_gemini": int(gemini_score),
                            "body_impact_overall": int(company_impact),
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
                        print(current_event["created_at"])
                        time.sleep(1)

    #         news_result.append(item_result)
    print("Done News Task")
    # return news_result
# Example usage:
# Replace 'AAPL', '2023-01-01', '2023-01-31' with your desired symbol and date range
if __name__ == '__main__':
    symbol = 'BTCUSD'
    
    # Define the start and end dates
    start_year = 2022
    start_month = 1
    start_day = 1
    end_year = date.today().year
    end_month = date.today().month
    end_day = date.today().day

    # Loop through each month from the start date to the end date
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            if (year == end_year and month > end_month):
                break  # Stop if we reach the current month

            if (year == start_year and month < start_month):
                continue  # Skip months before the start month in the start year

            if year == start_year and month == start_month:
                start_date = date(year, month, start_day)
            else:
                start_date = date(year, month, 1)
            
            if year == end_year and month == end_month:
                end_date = date(year, month, end_day)
            else:
                end_date = date(year, month, calendar.monthrange(year, month)[1])

            print('start_date: ', start_date)
            print('end_date: ', end_date)

            analyze_news_combine_request(symbol, start_date.isoformat(), end_date.isoformat(), limit=None)

    # current_start_date = start_date
    # while current_start_date < end_date:

        
    #     current_end_date = current_start_date + relativedelta(months=1)
    #     if current_end_date > end_date:
    #         current_end_date = end_date
            
    #     print('current_start_date: ', current_start_date)
    #     print('end_date: ', end_date)
        
    #     analyze_news_combine_request(
    #         symbol,
    #         start_date=current_start_date.strftime('%Y-%m-%d'),
    #         end_date=current_end_date.strftime('%Y-%m-%d'),
    #         limit=None
    #     )
        
    #     current_start_date = current_end_date