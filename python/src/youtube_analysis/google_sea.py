from googleapiclient.discovery import build

my_api_key = "AIzaSyAkHYR1XJIxVIeXkKDpiS6Lc38DzDBR8Iw" #The API_KEY you acquired
my_cse_id = "1579873697282499a" #The search-engine-ID you created


def google_search(search_term, api_key, cse_id, **kwargs):
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=search_term, cx=cse_id, **kwargs).execute()
    return res['items']


results = google_search('cat', my_api_key, my_cse_id, num=5)
print('results: ', results)
