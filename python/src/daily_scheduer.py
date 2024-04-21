
import schedule
import datetime
import time

from get_news_history_for_OpenAI import analyze_news_gemini_request


def job():
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=1)
    currency_pair = 'BTCUSD'
    analyze_news_gemini_request(currency_pair, start_date, end_date, limit=None)

def run_scheduler():
    # Schedule the job every day at 12 am
    schedule.every().day.at("00:01").do(job)

    # Loop so that the scheduling task keeps running
    while True:
        schedule.run_pending()
        time.sleep(60)  # wait one minute

if __name__ == "__main__":
    run_scheduler()