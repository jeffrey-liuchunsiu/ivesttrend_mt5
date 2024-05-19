import requests
import json

url = 'https://api.coze.com/open_api/v2/chat'
headers = {
    'Authorization': 'Bearer pat_4KAjgjPQK7BVEuDDMCMJDPHsFZeFdqfy9PdcMLQvuFUgsvo5lRdB3ln1YQiqmQdv',
    'Content-Type': 'application/json',
    'Accept': '*/*',
    'Host': 'api.coze.com',
    'Connection': 'keep-alive'
}
data = {
    "conversation_id": "123",
    "bot_id": "7369229115175813128",
    "user": "216007261594",
    "query": "hello",
    "stream": False
}

response = requests.post(url, headers=headers, data=json.dumps(data))

print(response.status_code)
print(response.json())