import requests
import os
import urllib
from datetime import datetime
import cv2
# from deepface import DeepFace
# from imageRecognitionUpdated2 import recognize_elon_musk  # Import the recognize_elon_musk function

import tensorflow as tf
import numpy as np
from tensorflow.keras.preprocessing import image
from deepface import DeepFace
from PIL import Image, ImageDraw
import constants


os.environ["YOUTUBE_API_KEY"] = constants.YOUTUBE_API_KEY

# Ensure the model file exists
model_path = os.path.abspath('/Users/mattchung/VSCLocal/ivesttrend_mt5/python/src/youtube_test/elon_musk_recognition_model.h5')
if not os.path.exists(model_path):
    raise FileNotFoundError(f"Model file not found at {model_path}")

# Load the trained model
model = tf.keras.models.load_model(str(model_path))
print('Model absolute path: ', model_path)


# # Assuming you have the model loaded as 'model'
# model_json = model.to_json()
# with open("elon_musk_recognition_model.json", "w") as json_file:
#     json_file.write(model_json)
# model.save_weights("elon_musk_recognition_model_weights.h5")
# Function to load the model
# def load_model(model_path, compile_with_metrics=False):
#     if not os.path.exists(model_path):
#         raise FileNotFoundError(f"Model file not found: {model_path}")
    
#     model = tf.keras.models.load_model(model_path)
    
#     # Optionally compile the model with metrics
#     if compile_with_metrics:
#         model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
    

# model = load_model('/Users/mattchung/Documents/VSC/invest-trend-internal/chatgpt/elon_musk_recognition_model.h5', compile_with_metrics=True)

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
        detected_faces = DeepFace.extract_faces(image_path, detector_backend='opencv', enforce_detection=False)
        
        # If no face is detected, return
        if not detected_faces:
            print("No face detected in the image.")
            return
        
        # Open the original image
        original_img = Image.open(image_path)
        draw = ImageDraw.Draw(original_img)
        
        # If multiple faces are detected, DeepFace returns a list of dictionaries
        for face_info in detected_faces:
            face_array = face_info['face']
            facial_area = face_info['facial_area']
            
            face_img = Image.fromarray((face_array * 255).astype('uint8'))
            face_array = preprocess_face(face_img)
            prediction = model.predict(face_array)
            print (prediction)
            if prediction[0][0] > 0.5:
                print("Elon Musk detected!")
                draw.rectangle([facial_area['x'], facial_area['y'], facial_area['x'] + facial_area['w'], facial_area['y'] + facial_area['h']], outline="green", width=2)
            else:
                print("Not Elon Musk.")
                draw.rectangle([facial_area['x'], facial_area['y'], facial_area['x'] + facial_area['w'], facial_area['y'] + facial_area['h']], outline="red", width=2)
        
        # Show the image with detected faces
        # original_img.show()
    
    except Exception as e:
        print(f"An error occurred: {e}")


API_KEY = os.environ["YOUTUBE_API_KEY"]
CHANNEL_ID = 'UCvJJ_dzjViJCoLf5uKUTwoA'
PUBLISHED_AFTER = '2024-07-04T00:00:00Z'  # Updated published after date
MAX_PAGES = 1  # Maximum number of pages to fetch (updated)
THUMBNAIL_FOLDER = 'thumbnails'  # Folder to save the thumbnails

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
            published_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")

            # Stop fetching if the video's published date is before PUBLISHED_AFTER
            if published_date < datetime.strptime(published_after, "%Y-%m-%dT%H:%M:%SZ"):
                return videos

            videos.append(item)

        page_token = playlist_data.get('nextPageToken')
        if not page_token:
            break

    return videos

# Create the thumbnail folder if it doesn't exist
if not os.path.exists(THUMBNAIL_FOLDER):
    os.makedirs(THUMBNAIL_FOLDER)

# Get all videos of the channel published within the specified period
videos = get_channel_videos(API_KEY, CHANNEL_ID, PUBLISHED_AFTER)

# Download and save the thumbnails, and analyze each thumbnail
for video in videos:
    title = video['snippet']['title']
    video_id = video['snippet']['resourceId']['videoId']
    published_at = video['snippet']['publishedAt']
    thumbnail_url = video['snippet']['thumbnails']['high']['url']  # Change thumbnail quality to 'high'
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    # Parse the publication date
    published_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
    
    # Create the filename for the thumbnail with the publication date
    filename = f"{published_date.strftime('%Y-%m-%d')}_{video_id}.jpg"

    # Build the full path to save the thumbnail
    save_path = os.path.join(THUMBNAIL_FOLDER, filename).replace("\\", "/")

    # Download the thumbnail and save it to the specified folder
    urllib.request.urlretrieve(thumbnail_url, save_path)

    print(f"Title: {title}")
    print(f"Published At: {published_at}")
    print(f"Thumbnail URL: {thumbnail_url}")
    print(f"Video URL: {video_url}")
    print(f"Thumbnail saved to: {save_path}")


    # Analyze the thumbnail for emotions
    img = cv2.imread(save_path)
    try:
        analyze = DeepFace.analyze(img, actions=['emotion'], enforce_detection=True)
        # Recognize Elon Musk in the thumbnail
        print("Analyzing for Elon Musk in the thumbnail...")
        try:
            recognize_elon_musk(save_path)
            # image_path = 'elon_musk_test/musk2.jpg'
            # recognize_elon_musk(image_path)
        except Exception as e:
            print(f"Error recognizing Elon Musk in the thumbnail: {e}")
        print(f"Emotion Analysis: {analyze}")
    except Exception as e:
        print(f"Error analyzing image: {e}")

    print()

# if __name__ == "__main__":
#     image_path = 'elon_musk_test/musk2.jpg'
#     recognize_elon_musk(image_path)