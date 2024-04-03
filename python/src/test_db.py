import boto3
from boto3.dynamodb.conditions import Attr
from dotenv import load_dotenv
import os
load_dotenv()

aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
region_name = os.getenv('AWS_REGION')

# Create a DynamoDB client
dynamodb = boto3.resource('dynamodb', 
                          aws_access_key_id=aws_access_key_id, 
                          aws_secret_access_key=aws_secret_access_key, 
                          region_name=region_name)

# Specify the table name and the column name
table_name = 'TestInstance-ambqia6vxrcgzfv4zl44ahmlp4-dev'
column_name = 'mt5_magic_id'
table = dynamodb.Table(table_name)
# Variable to keep track of the largest 'mt5_magic' value
largest_mt5_magic = None

# Scan operation parameters
scan_kwargs = {
    'ProjectionExpression': "mt5_magic_id",  # Only retrieve the 'mt5_magic' column
    'FilterExpression': Attr('mt5_magic_id').exists()  # Filter out items where 'mt5_magic' may not exist
}

done = False
start_key = None

# Perform the scan
while not done:
    if start_key:
        scan_kwargs['ExclusiveStartKey'] = start_key
    response = table.scan(**scan_kwargs)
    items = response.get('Items', [])

    for item in items:
        mt5_magic_value = item['mt5_magic_id']
        if largest_mt5_magic is None or mt5_magic_value > largest_mt5_magic:
            largest_mt5_magic = mt5_magic_value
    
    start_key = response.get('LastEvaluatedKey', None)
    done = start_key is None

# Output the largest 'mt5_magic' value
print(f"The largest 'mt5_magic' value is: {largest_mt5_magic}")