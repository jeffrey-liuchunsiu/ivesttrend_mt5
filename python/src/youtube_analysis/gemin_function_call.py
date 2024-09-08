import os
import google.generativeai as genai
from dotenv import find_dotenv, load_dotenv
from decimal import Decimal
import json

# Load environment variables from .env file
load_dotenv(find_dotenv())
key = os.getenv('GOOGLE_API_KEY')

# Configure the API key
genai.configure(api_key=key)

def set_light_values(brightness, color_temp):
    """Set the brightness and color temperature of a room light. (mock API).

    Args:
        brightness: Light level from 0 to 100. Zero is off and 100 is full brightness
        color_temp: Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.

    Returns:
        A dictionary containing the set brightness and color temperature.
    """
    return {
        "brightness": brightness,
        "colorTemperature": color_temp
    }
    
model = genai.GenerativeModel(model_name='gemini-1.5-flash',
                              tools=[set_light_values],
                              )

chat = model.start_chat()
response = chat.send_message('Dim the lights so the room feels cozy and warm.')
response.text