import boto3
from boto3.dynamodb.conditions import Key, Attr
from dotenv import load_dotenv
from datetime import datetime,timedelta
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

def get_item_by_magic_id():
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
    
def get_last_10_items_by_date_time():
    # Initialize a DynamoDB client
    dynamodb = boto3.resource('dynamodb')
    
    # Specify the table name
    table_name = 'InvestNews-ambqia6vxrcgzfv4zl44ahmlp4-dev'
    table = dynamodb.Table(table_name)

    # Define the query parameters
    start_date = '2024-04-19'
    end_date = '2024-04-20'
    ticker_symbol = 'BTCUSD'
    limit = 3

    # Paginate through the results manually to find the last 10 items
    last_items = []
    exclusive_start_key = None

    while True:
        scan_kwargs = {
            'FilterExpression': Attr('date_time').between(start_date, end_date) &
                        Attr('ticker_symbol').contains(ticker_symbol) 
        }
        
        # Only add ExclusiveStartKey to arguments if it's not None
        if exclusive_start_key:
            scan_kwargs['ExclusiveStartKey'] = exclusive_start_key

        response = table.scan(**scan_kwargs)
        
        items = response.get('Items', [])
        print('items: ', len(items))
        
        filtered_items = [
                item for item in items 
                if int(item['headline_impact']) >= 50 or int(item['headline_impact']) <= -50
            ]
        
        # Prepend to ensure latest items are kept if we exceed 10
        last_items = filtered_items + last_items
        last_items = last_items[-(limit):]  # Keep only the last 10 items

        if 'LastEvaluatedKey' not in response or len(last_items) >= limit:
            break
        exclusive_start_key = response['LastEvaluatedKey']

    print('items: ', len(last_items))

    # Print the retrieved items
    for item in last_items:
        print(item)
        
def get_min_date_time():
    # Initialize DynamoDB
    dynamodb = boto3.resource('dynamodb')

    # Specify the table name
    table_name = 'InvestNews-ambqia6vxrcgzfv4zl44ahmlp4-dev'
    table = dynamodb.Table(table_name)

    # Initialize the minimum date_time
    min_date = None

    # Scan the table
    response = table.scan(
        ProjectionExpression="date_time",  # Only fetch the date_time attribute
    )

    # Check and update the minimum date_time
    for item in response['Items']:
        current_date = datetime.strptime(item['date_time'], "%Y-%m-%dT%H:%M:%SZ").date()
        if min_date is None or current_date < min_date:
            min_date = current_date

    # Handle pagination if the response is large
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            ProjectionExpression="date_time",
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        for item in response['Items']:
            current_date = datetime.strptime(item['date_time'], "%Y-%m-%dT%H:%M:%SZ").date()
            if min_date is None or current_date < min_date:
                min_date = current_date


    # Add one day to the minimum date
    next_day = min_date + timedelta(days=1)

    return next_day

# Example usage
next_day = get_min_date_time()
print("Next day:", next_day)
    
def delete_item():

    # Create a DynamoDB resource
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('InvestNews-ambqia6vxrcgzfv4zl44ahmlp4-dev')

    # Scan the table - only retrieve the primary key attributes
    response = table.scan(
        ProjectionExpression="id", # Replace 'PrimaryKeyAttribute' with your table's actual primary key attribute name
    )

    items = response['Items']

    # Delete each item
    for item in items:
        print('item: ', item)
        table.delete_item(Key=item)

    # Handle pagination if the response is large
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            ProjectionExpression="id",
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        for item in response['Items']:
            print('item: ', item)
            table.delete_item(Key=item)
            
def change_column():
    # Create a DynamoDB client
    dynamodb = boto3.resource('dynamodb', 
                            aws_access_key_id=aws_access_key_id, 
                            aws_secret_access_key=aws_secret_access_key, 
                            region_name=region_name)
    table = dynamodb.Table('InvestNews-ambqia6vxrcgzfv4zl44ahmlp4-dev')

    # Scan the table (Note: Use Query if you have specific criteria for selection)
    response = table.scan()

    attr = Attr('headline_impact').attribute_type('N')
    response = table.scan(FilterExpression = attr)
    items = response['Items']

    while 'LastEvaluatedKey' in response:
        response = table.scan(FilterExpression = attr, ExclusiveStartKey = response['LastEvaluatedKey'])
        items.extend(response['Items'])
    
    
if __name__ == "__main__":
    # delete_item()
    get_last_10_items_by_date_time()
    # get_min_date_time()
    # change_column()