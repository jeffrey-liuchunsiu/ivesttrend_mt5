import requests
import os
import urllib
from datetime import datetime, timedelta
import cv2
import tensorflow as tf
import numpy as np
from tensorflow.keras.preprocessing import image # type: ignore
from deepface import DeepFace
from PIL import Image, ImageDraw
import json
import constants
import yfinance as yf
import matplotlib.pyplot as plt
# !---CP start ---
import boto3
from dotenv import find_dotenv, load_dotenv
from decimal import Decimal
import shutil
import PIL.Image


load_dotenv(find_dotenv())

aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
region_name = os.getenv('AWS_REGION')

s3 = boto3.client('s3',aws_access_key_id=aws_access_key_id, 
                          aws_secret_access_key=aws_secret_access_key, 
                          region_name=region_name)

dynamodb = boto3.resource('dynamodb',aws_access_key_id=aws_access_key_id, 
                          aws_secret_access_key=aws_secret_access_key, 
                          region_name=region_name)
table = dynamodb.Table('invest_trend_youtube_dataV4')

os.environ["YOUTUBE_API_KEY"] = constants.YOUTUBE_API_KEY

script_dir = os.path.dirname(__file__)


def convert_floats_to_decimals(data):
    if isinstance(data, list):
        return [convert_floats_to_decimals(item) for item in data]
    elif isinstance(data, dict):
        return {key: convert_floats_to_decimals(value) for key, value in data.items()}
    elif isinstance(data, float) or isinstance(data, (np.float32, np.float64)):
        return Decimal(str(data))
    else:
        return data
    
# !---CP end ---



import os
import google.generativeai as genai
from dotenv import find_dotenv, load_dotenv
from decimal import Decimal
import json

# Load environment variables from .env file
load_dotenv(find_dotenv())
key = os.getenv('GOOGLE_API_KEY')


def check_elon_musk_in_image(file_path):
    """          
    Checks if Elon Musk is present in an image.

    Args:
        file_path (str): The path to the image file.

    Returns:
        dict: A dictionary containing the results of the analysis:
            - elon_musk_detected (bool): True if Elon Musk is detected, False otherwise.
            - face_confidence (float): Confidence score for face detection (between 0 and 1).
            - elon_musk_confidence (float): Confidence score for Elon Musk identification (between 0 and 1).
    """

    # Upload the image
    # sample_file = PIL.Image.open(file_path)
    sample_file = genai.upload_file(path=file_path, display_name=os.path.basename(file_path))
    print(f"Uploaded file '{sample_file.display_name}' as: {sample_file.uri}")
    
    import time

    # Check whether the file is ready to be used.
    while sample_file.state.name == "PROCESSING":
        print('.', end='')
        time.sleep(10)
        sample_file = genai.get_file(sample_file.name)

    if sample_file.state.name == "FAILED":
        raise ValueError(sample_file.state.name)

    # Analyze the image
    response = model.generate_content([sample_file])
    print('response: ', response)
    # response = model.generate_content([sample_file,'i am tell you that elon mask is not the image, and make sure you will not recognize it wrong in the future?'])
    # print(f"Image '{os.path.basename(file_path)}': {response.text}")
    
    genai.delete_file(sample_file.name)

    # Parse the response
    try:
        result = json.loads(response.text)
        return result
    except Exception as e:
        print(f"Error parsing response: {e}")
        return False

# Define the paths
source_dir = "/Users/mattchung/VSCLocal/ivesttrend_mt5/python/src/youtube_analysis/elon_mix"
elon_musk_dir = "/Users/mattchung/VSCLocal/ivesttrend_mt5/python/src/youtube_analysis/hv_musk"
no_elon_musk_dir = "/Users/mattchung/VSCLocal/ivesttrend_mt5/python/src/youtube_analysis/no_hv_musk"

# Ensure destination directories exist
os.makedirs(elon_musk_dir, exist_ok=True)
os.makedirs(no_elon_musk_dir, exist_ok=True)

# Iterate through all files in the source directory
for i, filename in enumerate(os.listdir(source_dir)):
    key = os.getenv('GOOGLE_API_KEY')
    key2 = os.getenv('GOOGLE_API_KEY2')

    # Configure the API key
    if i % 2 == 0:
        genai.configure(api_key=key)
    else: 
        genai.configure(api_key=key2)
        
    model = genai.GenerativeModel(
    model_name='gemini-1.5-pro-latest',
    system_instruction="""You are an Elon Musk (Founder of Tesla) video/image recognizer. Determine if the provided video/image contains Elon Musk, and analyze his emotion if detected.
                            - Please check very carefully if Elon Musk is present in the video/image.
                            - Return a JSON object with "elon_musk_detected": true, "elon_musk_emotion": "<emotion>", and "emotion": { "angry": <value>, "disgust": <value>, "fear": <value>, "happy": <value>, "sad": <value>, "surprise": <value>, "neutral": <value>, "confident": <value> } if Elon Musk is present in the video/image, where <emotion> represents his detected predominant emotion (e.g., "happy", "sad", "neutral") and the values represent the corresponding probabilities.
                            - Return a JSON object with "elon_musk_detected": false, "elon_musk_emotion": null and "emotion": { "angry": null, "disgust": null, "fear": null, "happy": null, "sad": null, "surprise": null, "neutral": null, "confident": null } if Elon Musk is not present in the video/image.
                            - If the video/image is too blurry or you are not very sure if Elon Musk is present in the video/image, return "elon_musk_detected": false, "elon_musk_emotion": null and "emotion": { "angry": null, "disgust": null, "fear": null, "happy": null, "sad": null, "surprise": null, "neutral": null } .
                            - Only return the JSON object, avoid any additional text and avoid ``` or ```json.
                            """,
    generation_config=genai.GenerationConfig(
        temperature=0,
        
    ))
        
    # if filename.lower().endswith(('.mp4')):
    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff','.mp4')):
        source_path = os.path.join(source_dir, filename)
        result = check_elon_musk_in_image(source_path)
        print('result: ', result)
        # Apply the recognize_elon_musk function
        if result["elon_musk_detected"]:
            # Move to elon_musk_dir if the function returns True
            destination_path = os.path.join(elon_musk_dir, filename)
        else:
            # Move to no_elon_musk_dir if the function returns False
            destination_path = os.path.join(no_elon_musk_dir, filename)
        
        # Move the file
        shutil.move(source_path, destination_path)
        print(f"Moved '{filename}' to '{destination_path}'")

print("Processing completed.")