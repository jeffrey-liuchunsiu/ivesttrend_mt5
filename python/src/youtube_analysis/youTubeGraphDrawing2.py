import json
import os
from datetime import datetime, timedelta
import yfinance as yf
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd

# Load video data from JSON file
json_file_path = '/Users/mattchung/VSCLocal/ivesttrend_mt5/python/src/youtube_analysis/youtube_video_data3LocalAllFolder3.json'
if os.path.exists(json_file_path):
    with open(json_file_path, 'r') as f:
        video_data_list = json.load(f)
else:
    raise FileNotFoundError(f"'{json_file_path}' not found.")

# Fetch Tesla stock data for the last year
tesla = yf.Ticker("TSLA")
end_date = datetime.now()
start_date = end_date - timedelta(days=365)
tesla_data = tesla.history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))

# Convert tesla_data index to naive datetime
tesla_data.index = tesla_data.index.tz_localize(None)

# Define colors for each emotion
emotion_colors = {
    'angry': 'red',
    'disgust': 'green',
    'fear': 'purple',
    'happy': 'yellow',
    'sad': 'blue',
    'surprise': 'orange',
    'neutral': 'grey'
}

# Summarize the sad and happy scores by each day
sad_scores = {}
happy_scores = {}

for video in video_data_list:
    video_date = datetime.strptime(video['published_at'], '%Y-%m-%dT%H:%M:%SZ').date()
    
    if video['dominant_emotion'] == 'sad':
        sad_scores[video_date] = sad_scores.get(video_date, 0) + video['dominant_emotion_value']
    
    if video['dominant_emotion'] == 'happy':
        happy_scores[video_date] = happy_scores.get(video_date, 0) + video['dominant_emotion_value']

# Convert sad_scores and happy_scores to DataFrames
sad_scores_df = pd.DataFrame(list(sad_scores.items()), columns=['Date', 'Sad_Score'])
happy_scores_df = pd.DataFrame(list(happy_scores.items()), columns=['Date', 'Happy_Score'])

# Set the Date as the index
sad_scores_df.set_index('Date', inplace=True)
happy_scores_df.set_index('Date', inplace=True)

# Merge Tesla stock data with sad_scores_df and happy_scores_df
tesla_data['Sad_Score'] = sad_scores_df['Sad_Score']
tesla_data['Happy_Score'] = happy_scores_df['Happy_Score']

# Forward fill the NaN values in the sad and happy score columns
tesla_data['Sad_Score'].fillna(method='ffill', inplace=True)
tesla_data['Happy_Score'].fillna(method='ffill', inplace=True)

# Plotting
plt.figure(figsize=(14, 7))

# Plot Tesla Stock Price
plt.plot(tesla_data.index, tesla_data['Close'], label='Tesla Stock Price', color='black')

# Plot Sad Scores
plt.plot(tesla_data.index, tesla_data['Sad_Score'], label='Sad Score', color='blue')

# Plot Happy Scores
plt.plot(tesla_data.index, tesla_data['Happy_Score'], label='Happy Score', color='red')

# Create custom legend
legend_elements = [
    Line2D([0], [0], marker='o', color='w', label='Tesla Stock Price', markerfacecolor='black', markersize=10),
    Line2D([0], [0], marker='o', color='w', label='Sad Score', markerfacecolor='blue', markersize=10),
    Line2D([0], [0], marker='o', color='w', label='Happy Score', markerfacecolor='yellow', markersize=10)
]
plt.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1, 1))

plt.xlabel('Date')
plt.ylabel('Stock Price / Emotion Scores')
plt.title('Tesla Stock Price and Emotion Scores from Video Data')

# Save the plot with a timestamp identifier
timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
base_dir = 'elon_musk_youtube_analysis3LocalAllFolder'
graph_dir = os.path.join(base_dir, 'graph').replace("\\", "/")
os.makedirs(graph_dir, exist_ok=True)
plot_save_path = os.path.join(graph_dir, f'tesla_stock_vs_emotions_{timestamp}.png').replace("\\", "/")
plt.savefig(plot_save_path)

plt.show()