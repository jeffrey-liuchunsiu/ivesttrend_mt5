import schedule
from datetime import datetime, timedelta, date
import time
import requests
import pytz
import logging
import sys

from get_news_history_for_OpenAI import analyze_news_gemini_request
from test_ollama import analyze_news_combine_request
from utils.mt5_utils import fetch_deals_in_chunks
from server import get_tests_id_by_state

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def make_api_calls(test_ids):
    """Makes an API call for each test ID in the test_ids list."""
    api_url = 'http://18.141.245.200:8000/get_forward_test_result'  # Replace with the actual API URL
    headers = {'Content-Type': 'application/json'}
    
    for test_id in test_ids:
        try:
            payload = {'test_id': test_id}
            response = requests.post(api_url, json=payload, headers=headers)
            
            if response.status_code == 202:
                logging.info(f'Successfully processed test ID {test_id}: {response.json()}')
                time.sleep(20)
            else:
                logging.error(f'Failed to process test ID {test_id}: {response.json()}')
        except Exception as e:
            logging.error(f'Error processing test ID {test_id}: {str(e)}')

def job():
    try:
        # Can test result
        states_to_query = ['Running', 'End']
        test_ids = get_tests_id_by_state('state-index', states_to_query)
        make_api_calls(test_ids)
        
        # News
        end_date = date.today()
        start_date = end_date - timedelta(days=1)
        currency_pair = 'BTCUSD'
        analyze_news_combine_request(currency_pair, start_date.isoformat(), end_date.isoformat(), limit=None)
    except Exception as e:
        logging.error(f'Error in job: {str(e)}')

def another_job():
    try:
        timezone = pytz.timezone("Asia/Hong_Kong")
        utc_from = datetime.now(tz=timezone) - timedelta(days=3)
        logging.info(f'utc_from: {utc_from}')

        utc_from = datetime(utc_from.year, utc_from.month, utc_from.day,
                            hour=utc_from.hour, minute=utc_from.minute, tzinfo=timezone)

        date_to = datetime.now().astimezone(pytz.timezone("Asia/Hong_Kong"))
        date_to = datetime(date_to.year, date_to.month, date_to.day,
                        hour=date_to.hour, minute=date_to.minute, tzinfo=timezone)
        fetch_deals_in_chunks(utc_from, date_to, chunk_size_days=0.5)
    except Exception as e:
        logging.error(f'Error in another_job: {str(e)}')

def run_scheduler():
    schedule.every().day.at("00:01").do(job)
    schedule.every(2).minutes.do(another_job)
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logging.error(f'Error in scheduler: {str(e)}')
            time.sleep(60)  # Wait for a minute before restarting

if __name__ == '__main__':
    while True:
        try:
            job()
            run_scheduler()
        except Exception as e:
            logging.error(f'Critical error: {str(e)}')
            logging.info('Restarting the scheduler...')
            time.sleep(30)  # Wait for a minute before restarting

# if __name__ == "__main__":
#     run_scheduler()