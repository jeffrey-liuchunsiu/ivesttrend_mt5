import os
import json
import requests
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import NoCredentialsError
import constants

# Set the environment variable for the API key
os.environ["YOUTUBE_API_KEY_MATT"] = constants.YOUTUBE_API_KEY_MATT
API_KEY = os.environ["YOUTUBE_API_KEY_MATT"]
print('API_KEY: ', API_KEY)

# Define constants
QUERY = 'elon musk'
MAX_RESULTS = 50  # Maximum allowed by the API
PUBLISHED_AFTER = '2023-02-01'  # Modify the start date as needed
PUBLISHED_BEFORE = '2023-02-15'  # Modify the end date as needed
OUTPUT_JSON_FILE = 'video_data_YouTube_search.json'
S3_BUCKET_NAME = 'investtrend-youtube-img'  # Replace with your bucket name

# Initialize S3 client
s3_client = boto3.client('s3')

def fetch_videos(published_after, published_before, page_token=None):
    """Fetches videos from YouTube API based on the given parameters."""
    url = 'https://www.googleapis.com/youtube/v3/search'
    params = {
        'part': 'snippet',
        'q': QUERY,
        'type': 'video',
        'order': 'date',
        'maxResults': MAX_RESULTS,
        'publishedAfter': published_after,
        'publishedBefore': published_before,
        'key': API_KEY,
        'pageToken': page_token
    }

    response = requests.get(url, params=params)
    print(response.url)  # Add this line for debugging
    response.raise_for_status()
    return response.json()

def sanitize_filename(title):
    """Sanitizes the video title to be a valid filename."""
    return "".join(c for c in title if c.isalnum() or c in (' ', '_')).rstrip()

def save_thumbnail_to_s3(url, title, published_date):
    """Downloads and saves the thumbnail to S3."""
    response = requests.get(url)
    response.raise_for_status()  # Raise an error for bad status codesa
    title_safe = sanitize_filename(title).replace(' ', '_')
    date_folder = published_date.split('T')[0]  # Extract date from published date
    s3_key = f"thumbnails_daily/{date_folder}/{title_safe}.jpg"
    
    try:
        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=response.content, ContentType='image/jpeg')
        print(f"Thumbnail saved to S3: {s3_key}")
        return s3_key
    except NoCredentialsError: 
        print("Credentials not available")
        return None

def print_and_save_videos(videos):
    """Prints video information and saves it to a JSON file."""
    video_data = []
    for video in videos:
        title = video['snippet']['title']
        thumbnail_url = video['snippet']['thumbnails']['high']['url']
        published_date = video['snippet']['publishedAt']
        video_id = video['id']['videoId']
        video_url = f'https://www.youtube.com/watch?v={video_id}'

        print(f'Title: {title}')
        print(f'Thumbnail URL: {thumbnail_url}')
        print(f'Video URL: {video_url}')
        print(
            f'Published Date: {datetime.fromisoformat(published_date[:-1]).strftime("%Y-%m-%d %H:%M:%S")}')
        print('-' * 80)

        thumbnail_s3_key = save_thumbnail_to_s3(thumbnail_url, title, published_date)

        video_data.append({
            'title': title,
            'thumbnail_url': thumbnail_url,
            'thumbnail_s3_key': thumbnail_s3_key,
            'video_url': video_url,
            'published_date': published_date
        })

    with open(OUTPUT_JSON_FILE, 'a') as json_file:
        json.dump(video_data, json_file, indent=4)

if __name__ == "__main__":
    # Example -  You may need to implement `published_after` and `published_before` based on your needs 
    start_date = datetime.strptime(PUBLISHED_AFTER, '%Y-%m-%d')
    end_date = datetime.strptime(PUBLISHED_BEFORE, '%Y-%m-%d')

    all_videos = []  # Initialize a list to store the collected videos

    current_date = start_date  # Start from the provided 'start_date' and update to 'next_date' 
    while current_date <= end_date:  # Loop until 'end_date' is reached
        next_date = current_date + timedelta(days=1) # Calculate the next date in a loop. Update the 'current_date' to 'next_date'
        # Correctly format the date and time 
        published_after = current_date.isoformat() + 'Z'  
        published_before = next_date.isoformat() + 'Z' # Format datetime objects as ISO8601 strings (YYYY-MM-DDTHH:mm:ss.sss) 
        
        next_page_token = None 
        while True:  
            response = fetch_videos(
                published_after, published_before, page_token=next_page_token) # This is where the API call happens (use a YouTube Search API client or library for this part).
            videos = response.get('items', [])  # Get the fetched video data from the API response 
            all_videos.extend(videos) # Store the retrieved videos in the 'all_videos' list

            next_page_token = response.get('nextPageToken')  
            if not next_page_token:  # Check if there are more results (e.g., no more pages to fetch) 
                break

        current_date = next_date # Update 'current_date' to the next day in the loop

    print_and_save_videos(all_videos)  # Call the `print_and_save_videos` function to save the collected videos 

