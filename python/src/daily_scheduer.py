
import schedule
import datetime
import time
import requests

from get_news_history_for_OpenAI import analyze_news_gemini_request
from server import  get_tests_id_by_state

def make_api_calls(test_ids):
    """Makes an API call for each test ID in the test_ids list."""
    api_url = '18.141.245.200:8000/start_forward_test'  # Replace with the actual API URL
    headers = {'Content-Type': 'application/json'}
    
    for test_id in test_ids:
        payload = {'test_id': test_id}
        response = requests.post(api_url, json=payload, headers=headers)
        
        if response.status_code == 200:
            print(f'Successfully processed test ID {test_id}:', response.json())
        else:
            print(f'Failed to process test ID {test_id}:', response.status_code)


def job():
    #can test result
    states_to_query = ['Running', 'End']
    test_ids = get_tests_id_by_state('state-index', states_to_query)
    make_api_calls(test_ids)
    
    #news
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=1)
    currency_pair = 'BTCUSD'
    analyze_news_gemini_request(currency_pair, start_date, end_date, limit=None)
    
    

def run_scheduler():
    # Schedule the job every day at 12 am
    job()
    schedule.every().day.at("00:01").do(job)

    # Loop so that the scheduling task keeps running
    while True:
        schedule.run_pending()
        time.sleep(60)  # wait one minute

if __name__ == "__main__":
    run_scheduler()