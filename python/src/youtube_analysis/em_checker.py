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

# Define the folder path
folder_path = "/Users/mattchung/VSCLocal/ivesttrend_mt5/python/src/youtube_analysis/elon_musk/train/not_elon_musk"

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
    response = model.generate_content([sample_file, """you are a Elon Musk checker. Check incoming image is Tesla founder, Elon Musk inside or not. If he is inside the image, return a JSON like this: {\"elon_musk_detected\":true, \"face_confidence\":0.96, \"elon_musk_confidence\":0.992961}. Else return a JSON like this: {\"elon_musk_detected\":false, \"face_confidence\":0.05, \"elon_musk_confidence\":0.05}.
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
        return {"elon_musk_detected": False, "face_confidence": 0.1, "elon_musk_confidence": 0.05}

# Iterate through all files in the folder
for filename in os.listdir(folder_path):
    # Check if the file is an image (assuming common image extensions)
    if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
        # Construct the full file path
        file_path = os.path.join(folder_path, filename)

        # Call the function to analyze the image
        analysis_result = check_elon_musk_in_image(file_path)
        print(f"Analysis result: {analysis_result}")

        # Delete the uploaded file (optional)
        # genai.delete_file(sample_file.uri)