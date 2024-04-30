import requests
from bs4 import BeautifulSoup
import ollama
import os
from dotenv import load_dotenv
import time
load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
}

url = 'https://www.benzinga.com/markets/cryptocurrency/24/04/38476692/as-bitcoin-plunges-whale-makes-waves-with-77-67m-deposit-into-kraken'
response = requests.get(url, headers=headers)

text = None
if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    
    article_content = soup.find(id='article-body')
    print(article_content.text if article_content else "Content not found")
    text = article_content.text
    response = ollama.chat(model='llama3', messages=[
        {
            'role': 'system',
            'content': f"Only return the number so I can input to a form, Please must not return with other content expect the number",
            'temperature': 0
          },
          {
            'role': 'user',
            'content': f"Given the article content '{article_content.text}', show me a number from -100 to 100 detailing the impact of this headline on stock price, with negative indicating price goes down, and positive indicating price goes up. Only return the number so I can input to a form, Please must not return with other content expect the number",
            'temperature': 0
          },
        ])
    print("Llama3: ",response['message']['content'])
    print("")
else:
    print(f"Failed to retrieve the webpage. Status code: {response.status_code}")
    
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.0-pro-latest:generateContent?key={GOOGLE_API_KEY}"

headers = {
    'Content-Type': 'application/json'
}

data = {
    "contents": [{
        "parts": [{
            "text": f"Given the content '{text}', show me a number from -100 to 100 detailing the impact of this headline on stock price, with negative indicating price goes down, and positive indicating price goes up. Only return number, not with other context"
        }]
    }],
    "generationConfig": {
        "temperature": 0,

    }
}

response = requests.post(url, headers=headers, json=data)
# print('response: ', response.text)
if response.status_code != 200:
    print('response: ', response.text)
    time.sleep(30)
    response = requests.post(url, headers=headers, json=data)

if response.json()["candidates"][0]["finishReason"] == "SAFETY":
    print('response: ', response)
    pass


if response.status_code == 200 and response.json()["candidates"][0]["finishReason"] == "STOP":
    try:
        response_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        print('Gemini: ', response_text)
    except :
        print('response: ', response.text)
    