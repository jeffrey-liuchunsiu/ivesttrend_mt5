import os
import google.generativeai as genai
from dotenv import find_dotenv, load_dotenv

# Load environment variables from .env file
load_dotenv(find_dotenv())
key = os.getenv('GOOGLE_API_KEY')
import google.generativeai as genai

genai.configure(api_key=key)

model = genai.GenerativeModel(
    model_name='gemini-1.5-pro',
    generation_config={'temperature': 0}
)

response = model.generate_content((
    'Can you provided a python code of supertrend strategy with parameters nad print the result? No with other content, just the string. avoid ```python``` or any ```'''
))

code_string = response.text.strip('`')
if code_string.startswith('python\n'):
    code_string = code_string[7:]
print(code_string)
try:
    exec(code_string)
except Exception as e:
    print(f"An error occurred: {e}")