import requests
import os
import urllib
from datetime import datetime, timedelta
import cv2
import tensorflow as tf
import numpy as np
from tensorflow.keras.preprocessing import image
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
model_path = os.path.join(script_dir, 'elon_musk_recognition_model_google4.h5')

# Load the trained model
model = tf.keras.models.load_model(model_path)

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

# Function to preprocess the face image


def preprocess_face(face_img, target_size=(224, 224)):
    face_img = face_img.resize(target_size)
    face_array = image.img_to_array(face_img)
    face_array = np.expand_dims(face_array, axis=0)
    face_array /= 255.0
    return face_array

# Function to detect faces and predict if Elon Musk is in the image


def recognize_elon_musk(image_path):
    try:
        # Detect faces in the image using DeepFace
        detected_faces = DeepFace.extract_faces(
            image_path, detector_backend='opencv', enforce_detection=True)

        # If no face is detected, return
        if not detected_faces:
            print("No face detected in the image.")
            return False, None, None

        # Open the original image
        original_img = Image.open(image_path)
        draw = ImageDraw.Draw(original_img)

        # If multiple faces are detected, DeepFace returns a list of dictionaries
        for face_info in detected_faces:
            face_array = face_info['face']
            facial_area = face_info['facial_area']
            confidence = face_info['confidence']
            print(f"Face detected confidence: {confidence}")

            face_img = Image.fromarray((face_array * 255).astype('uint8'))
            face_array = preprocess_face(face_img)
            prediction = model.predict(face_array)
            print(f"Elon Musk detected confidence: {prediction[0][0]}")
            if prediction[0][0] > 0.9:
                print("Elon Musk detected!")
                draw.rectangle([facial_area['x'], facial_area['y'], facial_area['x'] +
                               facial_area['w'], facial_area['y'] + facial_area['h']], outline="green", width=2)

                # Define the folder to save the image
                save_folder = 'elon_musk_detected_images'
                if not os.path.exists(save_folder):
                    os.makedirs(save_folder)

                # Create a filename and save the image
                filename = os.path.join(
                    save_folder, os.path.basename(image_path))
                original_img.save(filename)
                
                 # !---CP start ---
                img_s3_key = f"thumbnail_detected/{filename}"
                # Save the image to S3
                s3.upload_file(filename, 'investtrend-youtube-img', img_s3_key)
                
                print(f"Image uploaded to S3: {filename}")
                os.remove(filename)
                print(f"Image removed from folder: {filename}")
                # !---CP end ---

                # original_img.show()
                return True, confidence, prediction[0][0]
            else:
                print("Not Elon Musk.")
                draw.rectangle([facial_area['x'], facial_area['y'], facial_area['x'] +
                               facial_area['w'], facial_area['y'] + facial_area['h']], outline="red", width=2)

                # Define the folder to save the image
                save_folder = 'not_elon_musk_detected_images'
                if not os.path.exists(save_folder):
                    os.makedirs(save_folder)

                # Create a filename and save the image
                filename = os.path.join(
                    save_folder, os.path.basename(image_path))
                original_img.save(filename)
                # !---CP start ---
                img_s3_key = f"thumbnail_detected/{filename}"
                # Save the image to S3
                s3.upload_file(filename, 'investtrend-youtube-img', img_s3_key)
                
                print(f"Image uploaded to S3: {filename}")
                os.remove(filename)
                print(f"Image removed from folder: {filename}")
                # !---CP end ---

        # Show the image with detected faces
        
        # original_img.show()
        return False, None, None

    except Exception as e:
        error_message = str(e)
        if error_message.startswith("Face could not be detected in"):
            print("No face detected.")
        else:
            print(f"An error occurred: {e}")
        return False, None, None


API_KEY = os.environ["YOUTUBE_API_KEY"]
PUBLISHED_AFTER = '2024-07-01T00:00:00Z'  # Updated published after date
MAX_PAGES = 1  # Maximum number of pages to fetch (updated)
THUMBNAIL_FOLDER = 'thumbnails_youtube'  # Root folder to save the thumbnails


def get_channel_videos(api_key, channel_id, published_after):
    # Step 1: Get the channel's uploads playlist ID
    channel_url = f'https://www.googleapis.com/youtube/v3/channels'
    channel_params = {
        'part': 'contentDetails',
        'id': channel_id,
        'key': api_key,
    }
    channel_response = requests.get(channel_url, params=channel_params)
    channel_response.raise_for_status()
    channel_data = channel_response.json()
    uploads_playlist_id = channel_data['items'][0]['contentDetails']['relatedPlaylists']['uploads']

    # Step 2: Fetch all videos from the uploads playlist
    videos = []
    playlist_url = 'https://www.googleapis.com/youtube/v3/playlistItems'
    playlist_params = {
        'part': 'snippet',
        'playlistId': uploads_playlist_id,
        'maxResults': 10,
        'key': api_key,
    }
    page_token = None

    while True:
        if page_token:
            playlist_params['pageToken'] = page_token

        playlist_response = requests.get(playlist_url, params=playlist_params)
        playlist_response.raise_for_status()
        playlist_data = playlist_response.json()

        for item in playlist_data['items']:
            published_at = item['snippet']['publishedAt']
            published_date = datetime.strptime(
                published_at, "%Y-%m-%dT%H:%M:%SZ")

            # Stop fetching if the video's published date is before PUBLISHED_AFTER
            if published_date < datetime.strptime(published_after, "%Y-%m-%dT%H:%M:%SZ"):
                return videos

            videos.append(item)

        page_token = playlist_data.get('nextPageToken')
        if not page_token:
            break

    return videos

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
# Choose a model
model = genai.GenerativeModel('gemini-1.5-flash')

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
    sample_file = genai.upload_file(path=file_path, display_name=os.path.basename(file_path))
    print(f"Uploaded file '{sample_file.display_name}' as: {sample_file.uri}")

    # Analyze the image
    response = model.generate_content([sample_file, """you are a elon musk recognizer. Check incoming image is Elon Musk inside or not. If he is inside the image, return a JSON like this: {\"elon_musk_detected\":true, \"face_confidence\":0.96, \"elon_musk_confidence\":0.992961}. Else return a JSON like this: {\"elon_musk_detected\":false, \"face_confidence\":0.05, \"elon_musk_confidence\":0.05}.
                                        - elon_musk_detected (bool): True if Elon Musk is detected, False otherwise.
                                        - face_confidence (float): Confidence score for face detection (between 0 and 1).
                                        - elon_musk_confidence (float): Confidence score for Elon Musk identification (between 0 and 1).
                                        - all digit round up to 0.xx 
                                         """])
    print(f"Image '{os.path.basename(file_path)}': {response.text}")

    # Parse the response
    try:
        result = json.loads(response.text)  # Use json.loads to parse the JSON string
        return result["elon_musk_detected"], result["face_confidence"],result["elon_musk_confidence"]
    except Exception as e:
        print(f"Error parsing response: {e}")
        return {"elon_musk_detected": False, "face_confidence": 0, "elon_musk_confidence": 0}


# Global list to hold video data across all channels
video_data_list = []

# Create the thumbnail root folder if it doesn't exist
if not os.path.exists(THUMBNAIL_FOLDER):
    os.makedirs(THUMBNAIL_FOLDER)

# Load the JSON file containing channel information
with open(os.path.join(script_dir,'youTubeChannelsSimple.json'), 'r') as file:
    data = json.load(file)

# Directory of the script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Directories for images with and without Elon Musk
hv_musk_dir = os.path.join(script_dir, 'hv_musk')
no_hv_musk_dir = os.path.join(script_dir, 'no_hv_musk')

# Ensure the directories exist
os.makedirs(hv_musk_dir, exist_ok=True)
os.makedirs(no_hv_musk_dir, exist_ok=True)

# Iterate through the JSON data and process each channel
for i ,country_info in enumerate(data):
    key = os.getenv('GOOGLE_API_KEY')
    key2 = os.getenv('GOOGLE_API_KEY2')

    # Configure the API key
    if i % 2 == 0:
        genai.configure(api_key=key)
    else: 
        genai.configure(api_key=key2)
    # Choose a model
    model = genai.GenerativeModel('gemini-1.5-flash')
    country = country_info['country']
    for channel in country_info['channels']:
        channel_name = channel['name']
        channel_id = channel['channel_id']

        # Create a folder for each channel
        channel_folder = os.path.join(THUMBNAIL_FOLDER, channel_name.replace(" ", "_"))
        if not os.path.exists(channel_folder):
            os.makedirs(channel_folder)

        # Get all videos of the channel published within the specified period
        videos = get_channel_videos(API_KEY, channel_id, PUBLISHED_AFTER)

        # Download and save the thumbnails, and analyze each thumbnail
        for video in videos:
            title = video['snippet']['title']
            video_id = video['snippet']['resourceId']['videoId']
            published_at = video['snippet']['publishedAt']
            # Change thumbnail quality to 'high'
            thumbnail_url = video['snippet']['thumbnails']['high']['url']
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            # Parse the publication date
            published_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")

            # Create the filename for the thumbnail with the publication date
            filename = f"{published_date.strftime('%Y-%m-%d')}_{video_id}.jpg"

            # Build the full path to save the thumbnail
            save_path = os.path.join(channel_folder, filename).replace("\\", "/")

            # Download the thumbnail and save it to the specified folder
            urllib.request.urlretrieve(thumbnail_url, save_path)

            # Initialize variables for Elon Musk detection and its confidence levels
            elon_musk_detected = False
            face_confidence = None
            elon_musk_confidence = None

            # Recognize Elon Musk in the thumbnail
            try:
                elon_musk_detected, face_confidence, elon_musk_confidence = check_elon_musk_in_image(save_path)
            except Exception as e:
                elon_musk_detected = f"Error recognizing Elon Musk in the thumbnail: {e}"

            # Initialize emotion analysis variable
            emotion_analysis = None
            dominant_emotion = None
            dominant_emotion_value = None

            # If Elon Musk is detected, perform emotion analysis
            if elon_musk_detected:
                try:
                    img = cv2.imread(save_path)
                    emotion_analysis = DeepFace.analyze(img, actions=['emotion'], enforce_detection=True)
                    if emotion_analysis:
                        dominant_emotion = emotion_analysis[0]['dominant_emotion']
                        dominant_emotion_value = emotion_analysis[0]['emotion'][dominant_emotion]
                except Exception as e:
                    error_message = str(e)
                    if error_message.startswith("Face could not be detected in numpy array. Please confirm that the picture is a face photo or consider to set enforce_detection param to False."):
                        emotion_analysis = None
                    else:
                        emotion_analysis = error_message

            # Create a dictionary to hold the video data, including channel name and id
            video_data = {
                'id': f'{channel_id}-{video_id}',
                'channel_name': channel_name,
                'channel_id': channel_id,
                'title': title,
                'video_id': video_id,
                'published_at': published_at,
                'thumbnail_url': thumbnail_url,
                'video_url': video_url,
                'thumbnail_path': save_path,
                'face_confidence': face_confidence,
                'emotion_analysis': emotion_analysis,
                'dominant_emotion': dominant_emotion,
                'dominant_emotion_value': dominant_emotion_value,
                'elon_musk_detected': elon_musk_detected,
                'elon_musk_confidence': elon_musk_confidence,
            }

            if elon_musk_detected:
                try:
                    response = table.get_item(Key={'id': video_data['id']})
                    if 'Item' in response:
                        print(f"Video data already exists in DynamoDB: {video_data['id']}")
                    else:
                        # Insert the video data into DynamoDB
                        video_data = convert_floats_to_decimals(video_data)
                        table.put_item(Item=video_data)
                        print(f"Video data inserted into DynamoDB: {video_data['id']}")
                except Exception as e:
                    print(f"Error checking or inserting video data into DynamoDB: {e}")

                # Move the image to the hv_musk folder
                destination_path = os.path.join(hv_musk_dir, filename)
                shutil.move(save_path, destination_path)
                print(f"Image moved to: {destination_path}")
            else:
                # Move the image to the no_hv_musk folder
                destination_path = os.path.join(no_hv_musk_dir, filename)
                shutil.move(save_path, destination_path)
                print(f"Image moved to: {destination_path}")

            # Add the video data to the global list
            video_data_list.append(video_data)

# Print the global video data list
print("Global video data list:")
print(video_data_list)

# Convert published_at to datetime and extract dominant emotions
for video in video_data_list:
    video['published_at'] = datetime.strptime(
        video['published_at'], '%Y-%m-%dT%H:%M:%SZ')
    if isinstance(video['emotion_analysis'], list) and video['emotion_analysis']:
        emotion_info = video['emotion_analysis'][0]
        if 'dominant_emotion' in emotion_info and 'emotion' in emotion_info:
            video['dominant_emotion'] = emotion_info['dominant_emotion']
            video['dominant_emotion_value'] = emotion_info['emotion'][video['dominant_emotion']]
        else:
            video['dominant_emotion'] = None
            video['dominant_emotion_value'] = None
    else:
        video['dominant_emotion'] = None
        video['dominant_emotion_value'] = None

# Fetch Tesla stock data for the last year
tesla = yf.Ticker("TSLA")
end_date = datetime.now()
start_date = end_date - timedelta(days=365)
tesla_data = tesla.history(start=start_date.strftime(
    '%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))

# Convert tesla_data index to naive datetime
tesla_data.index = tesla_data.index.tz_localize(None)

# Plotting
plt.figure(figsize=(14, 7))
plt.plot(tesla_data.index, tesla_data['Close'], label='Tesla Stock Price')

# Annotate the graph with dominant emotions using scatter plot
index_dates = tesla_data.index

for video in video_data_list:
    if video['dominant_emotion']:
        # Find the closest available date
        target_date = video['published_at']
        closest_index = index_dates.get_indexer(
            [target_date], method='nearest')[0]
        closest_date = index_dates[closest_index]
        closest_price = tesla_data.loc[closest_date]['Close']

        # Print the stock price
        print(f"Video Title: {video['title']}")
        print(f"Published Date: {video['published_at']}")
        print(f"Closest Date: {closest_date}")
        print(f"Tesla Stock Price: {closest_price}")
        print(f"Face Confidence: {video['face_confidence']}")
        print(f"Elon Musk Confidence: {video['elon_musk_confidence']}")
        print(f"Dominant Emotion: {video['dominant_emotion']}")
        print(f"Dominant Emotion Value: {video['dominant_emotion_value']}")
        print("\n")

        # Scatter plot for dominant emotions
        plt.scatter(closest_date, video['dominant_emotion_value'],
                    label=f"{video['dominant_emotion']} ({video['title'][:30]}...)")

plt.xlabel('Date')
plt.ylabel('Stock Price / Emotion Analysis Value')
plt.title('Tesla Stock Price and Dominant Emotions from Video Data')
plt.legend()
plt.grid(True)
# plt.show()
