import requests
import time
import json
import ollama
import re
import math



def gemini_api(prompt,  google_api_key, temperature = 0, model="gemini-1.5-flash-latest"):
    if model == "gemini-1.5-flash-latest":
        time.sleep(5)
    if model == "gemini-1.5-pro-latest":
        time.sleep(31)
    if model == "gemini-1.0-pro-latest":
        time.sleep(5)
        
    # url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={google_api_key}"
    url = f"https://www.investtrend.tech/api/gemini"
    headers = {
        'Content-Type': 'application/json'
    }

    data = {
        "contents": [{
            "parts": [{
                "text": prompt,
            }]
        }],
        "generationConfig": {
            "temperature": temperature,
        }
    }

    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code != 200:
        print('response: ', response.json())
        time.sleep(30)
        response = requests.post(url, headers=headers, json=data)
    
    if response.json()["candidates"][0]["finishReason"] == "SAFETY":
        print('response: ', response.json())
        return "0"
    
    if response.status_code == 200 and response.json()["candidates"][0]["finishReason"] == "STOP":
        try:
            response_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            print(f'{model}: ', response_text)
            return response_text
        except Exception as e:
            print('response: ', response.text, 'Exception:', e)
            return None

def coze_api (prompt, coze_api_key):
    url = 'https://api.coze.com/open_api/v2/chat'
    headers = {
        'Authorization': f'Bearer {coze_api_key}',
        'Content-Type': 'application/json',
        'Accept': '*/*',
        'Host': 'api.coze.com',
        'Connection': 'keep-alive'
    }
    data = {
        "conversation_id": "123",
        "bot_id": "7369229115175813128",
        "user": "216007261594",
        "query": prompt,
        "stream": False
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))
    coze_result = response.json()
    result = coze_result['messages'][0]['content']
    print("Coze_chatGPT: ",result)
    return result

def ollama_local(prompt, temperature, model='llama3'):
    response = ollama.chat(model, messages=[
    {
        'role': 'user',
        'content': prompt,
        'temperature': temperature
    },
    ])
    print("Llama3: ",response['message']['content'])
    result = response['message']['content']
    return result

def openai_api (user_prompt, system_prompt, openai_api_key, temperature=0, model="gpt-3.5-turbo"):
    api_request_body = {
                "model": model,
                "temperature": temperature,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
            }

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": "Bearer " + openai_api_key,
            "Content-Type": "application/json",
        },
        json=api_request_body,
    )

    data = response.json()
    result = data["choices"][0]["message"]["content"]
    return result

def groq_api(user_prompt, system_prompt, groq_api_key, temperature=0, model="llama3-70b-8192"):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "model": model,
        "temperature": temperature
    }

    while True:
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                print(model, ": ", response.json()['choices'][0]['message']['content'])
                time.sleep(3)
                return response.json()['choices'][0]['message']['content']
            elif response.status_code == 429:
                message = response.json()['error']['message']
                time.sleep(20)

                requested_match = re.search(r'Requested ~(\d+)', message)
                retry_after_match = re.search(r'Please try again in ([\d.]+)s', message)

                if requested_match and retry_after_match:
                    requested_value = int(requested_match.group(1))
                    retry_after_value = float(retry_after_match.group(1))
                    retry_after_value_rounded = math.ceil(retry_after_value)
                    if retry_after_value_rounded > 60:
                        retry_after_value_rounded = 60
                    if requested_value <= 2000:
                        time.sleep(retry_after_value_rounded)
                        continue
                    elif requested_value > 2000:
                        model = "llama3-8b-8192"
                        data["model"] = model
                        time.sleep(retry_after_value_rounded)
                        continue
            else:
                response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            time.sleep(1)
            
def groq_api_old(user_prompt, system_prompt, groq_api_key, temperature=0, model="llama3-70b-8192"):
    # print('groq_api_key: ', groq_api_key)
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "messages": [{"role": "system", "content": system_prompt},{"role": "user", "content": user_prompt}],
        "model": model,
        "temperature":temperature
    }

    response = requests.post(url, headers=headers, json=data)
    print('response: ', response.json())
   
    
    if response.status_code == 200:
        print(model,": ", response.json()['choices'][0]['message']['content'])
        time.sleep(3)
        return response.json()['choices'][0]['message']['content']
    if response.status_code == 429:
        # Extract the message
        message = response.json()['error']['message']
        time.sleep(20)

        # Use regex to find the requested and retry-after values
        requested_match = re.search(r'Requested ~(\d+)', message)
        retry_after_match = re.search(r'Please try again in ([\d.]+)s', message)

        # Extract the values if matches are found
        if requested_match and retry_after_match:
            requested_value = int(requested_match.group(1))
            retry_after_value = float(retry_after_match.group(1))
            retry_after_value_rounded = math.ceil(retry_after_value)
            if retry_after_value_rounded > 60:
                retry_after_value_rounded = 60
            if requested_value <= 2000:
                time.sleep(retry_after_value_rounded)
                response = requests.post(url, headers=headers, json=data)
                print(model,": ", response.json()['choices'][0]['message']['content'])
                return response.json()['choices'][0]['message']['content']
            elif requested_value > 2000:
                model = "llama3-8b-8192"
                data = {
                    "messages": [{"role": "system", "content": system_prompt},{"role": "user", "content": user_prompt}],
                    "model": model,
                    "temperature":temperature
                }
                time.sleep(retry_after_value_rounded)
                response = requests.post(url, headers=headers, json=data)
                print(model,": ", response.json()['choices'][0]['message']['content'])
                return response.json()['choices'][0]['message']['content']
    else:
        response.raise_for_status()
        time.sleep(1)
    


