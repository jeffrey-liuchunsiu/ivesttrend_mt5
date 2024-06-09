import schedule
from datetime import datetime, timedelta
import time
import requests
import pytz

from get_news_history_for_OpenAI import analyze_news_gemini_request
from utils.mt5_utils import fetch_deals_in_chunks
from server import get_tests_id_by_state

def make_api_calls(test_ids):
    """Makes an API call for each test ID in the test_ids list."""
    api_url = 'http://18.141.245.200:8000/get_forward_test_result'  # Replace with the actual API URL
    headers = {'Content-Type': 'application/json'}
    
    for test_id in test_ids:
        payload = {'test_id': test_id}
        response = requests.post(api_url, json=payload, headers=headers)
        
        if response.status_code == 202:
            print(f'Successfully processed test ID {test_id}:', response.json())
            time.sleep(20)
        else:
            print(f'Failed to process test ID {test_id}:', response.json())

def job():
    # Can test result
    states_to_query = ['Running', 'End']
    test_ids = get_tests_id_by_state('state-index', states_to_query)
    make_api_calls(test_ids)
    
    # News
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=1)
    currency_pair = 'BTCUSD'
    analyze_news_gemini_request(currency_pair, start_date, end_date, limit=None)

def another_job():
    timezone = pytz.timezone("Asia/Hong_Kong")
     # Calculate the start date for fetching historical deals
    utc_from = datetime.now(tz=timezone) - timedelta(days=5)  # Adjust this as needed
    print('utc_from: ', utc_from)

    # Convert utc_from to a timezone-aware datetime object
    utc_from = datetime(utc_from.year, utc_from.month, utc_from.day,
                        hour=utc_from.hour, minute=utc_from.minute, tzinfo=timezone)

    # Get current date and time in Hong Kong timezone
    date_to = datetime.now().astimezone(pytz.timezone("Asia/Hong_Kong"))
    date_to = datetime(date_to.year, date_to.month, date_to.day,
                    hour=date_to.hour, minute=date_to.minute, tzinfo=timezone)
    fetch_deals_in_chunks(utc_from, date_to, chunk_size_days=0.5)
    # This is the new job that runs every 5 minutes
    # Add your task logic here

def run_scheduler():
    # Schedule the job every day at 12 am
    schedule.every().day.at("00:01").do(job)
    
    # Schedule another job every 5 minutes
    schedule.every(2).minutes.do(another_job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    run_scheduler()

    # Loop so that the scheduling task keeps running
    while True:
        schedule.run_pending()
        time.sleep(60)  # wait one minute

if __name__ == "__main__":
    run_scheduler()