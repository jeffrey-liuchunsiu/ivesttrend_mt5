import boto3
import json
import os
from dotenv import find_dotenv, load_dotenv
import random
import string

load_dotenv(find_dotenv())

aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
region_name = os.getenv('AWS_REGION')

def save_dict_to_s3(bucket_name, dict_data, s3_key):
    s3 = boto3.client('s3',aws_access_key_id=aws_access_key_id, 
                          aws_secret_access_key=aws_secret_access_key, 
                          region_name=region_name)
    json_data = json.dumps(dict_data)

    s3.put_object(Body=json_data, Bucket=bucket_name, Key=s3_key)
    
def get_json_data_from_s3(bucket_name, s3_key):
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=bucket_name, Key=s3_key)
    json_data = response['Body'].read().decode('utf-8')
    return json.loads(json_data)

def delete_object_from_s3(bucket_name, s3_key):
    s3 = boto3.client('s3')
    s3.delete_object(Bucket=bucket_name, Key=s3_key)
    print(f"Object {s3_key} deleted from S3 bucket {bucket_name}")
    
def delete_folder_from_s3(bucket_name, folder_prefix):
    s3 = boto3.client('s3')
    objects_to_delete = []

    # List objects in the folder
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=folder_prefix)

    # Add objects to the delete list
    if 'Contents' in response:
        for obj in response['Contents']:
            objects_to_delete.append({'Key': obj['Key']})

    # Delete objects in batches of 1000 (maximum allowed per request)
    while len(objects_to_delete) > 0:
        delete_keys = {'Objects': objects_to_delete[:1000]}
        response = s3.delete_objects(Bucket=bucket_name, Delete=delete_keys)
        if 'Errors' in response:
            print('Failed to delete some objects:')
            for error in response['Errors']:
                print(f" - Object: {error['Key']}, Code: {error['Code']}")
        del objects_to_delete[:1000]

    print(f"Folder {folder_prefix} and its contents deleted from S3 bucket {bucket_name}")
    
    
if __name__ == "__main__":
    print("testing - s3")
    
    def generate_random_json():
        data = {
            "name": ''.join(random.choices(string.ascii_letters, k=5)),
            "age": random.randint(18, 60),
            "email": ''.join(random.choices(string.ascii_lowercase, k=8)) + "@example.com",
            "address": {
                "street": ''.join(random.choices(string.ascii_letters + string.digits, k=10)),
                "city": ''.join(random.choices(string.ascii_letters, k=8)),
                "country": random.choice(["USA", "Canada", "UK", "Australia"])
            },
            "scores": [random.randint(60, 100) for _ in range(5)]
        }
        return data

    # Generate random JSON object
    random_json = generate_random_json()
    bucket_name = 'investtrend-test-data'
    s3_key = 'nqYMDefBwvdMpfNv/'
    # save_dict_to_s3(bucket_name, random_json, s3_key)
    # json_data = get_json_data_from_s3(bucket_name, s3_key)
    # print(json.dumps(json_data, indent=4)) 
    
    delete_folder_from_s3(bucket_name, s3_key)# Print the JSON data