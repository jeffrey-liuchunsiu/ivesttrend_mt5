import json
import boto3
from datetime import datetime
import os

def handler(event, context):
    print('received event:')
    print(event)
    
    # Check if event["body"] is a string and needs to be loaded as JSON
    if isinstance(event["body"], str):
        try:
            new_event = json.loads(event["body"])
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Invalid JSON format in the request body'})
            }
    else:
        # If event["body"] is already a dict, use it directly
        new_event = event["body"]
    
    # Check for the presence of 'test_id' in the event
    test_id = new_event.get("test_id")
    if not test_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Missing test_id in the request body'})
        }
    
    # Initialize DynamoDB resource
    dynamodb = boto3.resource('dynamodb')
    tests_table_name = os.environ.get('API_INVESTTRENDAPP_TESTINSTANCETABLE_NAME')
    tests_table = dynamodb.Table(tests_table_name)

    # Attempt to retrieve the item from DynamoDB
    try:
        response = tests_table.get_item(Key={'id': test_id})
    except tests_table.meta.client.exceptions.ClientError as error:
        print(f"DynamoDB ClientError: {str(error)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Error accessing DynamoDB'})
        }

    # Extract the item from the response
    test_instance = response.get('Item')
    
    if not test_instance:
        return {
            'statusCode': 404,
            'body': json.dumps({'message': 'Test instance not found'})
        }
        
    result_bt_overall_equity_per_day = [] 
    
    if "stock_close_price" in test_instance:   
        stock_close_price = test_instance["stock_close_price"]
        
        for data in stock_close_price:
            result_bt_overall_equity_per_day.append({'x': data['date'], 'y': data['price']})
            
    result_bt_overall_entries = [] 
    
    if "bt_overall_entries" in test_instance:   
        bt_overall_entries = test_instance["bt_overall_entries"]
        
        for data in bt_overall_entries:
            date_time_obj = datetime.strptime(data['Date'], '%Y-%m-%d %H:%M:%S')
            date_str = date_time_obj.strftime('%Y-%m-%d')
            formatted_price = "{:.2f}".format(float(data['Price']) * 100)
            result_bt_overall_equity_per_day.append({'x': date_str, 
                                                     'y': formatted_price})
            
    result_bt_overall_exits = [] 
    
    if "bt_overall_exits" in test_instance:   
        bt_overall_exits = test_instance["bt_overall_exits"]
        
        for data in bt_overall_exits:
            date_time_obj = datetime.strptime(data['Date'], '%Y-%m-%d %H:%M:%S')
            date_str = date_time_obj.strftime('%Y-%m-%d')
            formatted_price = "{:.2f}".format(float(data['Price']) * 100)
            result_bt_overall_equity_per_day.append({'x': date_str, 
                                                     'y': formatted_price})
            
    result =   {
    "stock_close_price": 
      {
        "name": "Stock Close Price",
        "type": "line",
        "data": result_bt_overall_equity_per_day,
      },
    "transactions": [
      {
        "bt_overall_entries": {
          "name": "Back Test Entries",
          "type": "scatter",
          "data": result_bt_overall_entries,
        },
        "bt_overall_exits": {
          "name": "Back Test Exits",
          "type": "scatter",
          "data": result_bt_overall_exits,
        },
      },
    ],
    "annotations": {
    "xaxis": [
                {
                    "x": test_instance["bt_start_date"],
                    "label": {
                        "text": "1st Back Test Start Date",
                    },
                },
                {
                    "x": test_instance["bt_2nd_start_date"],
                    "label": {
                        "text": "2nd Back Test Start Date",
                    },
                },
                {
                    "x": test_instance["ft_start_date"]if 'ft_start_date' in test_instance else None,
                    "label": {
                        "text": "Forward Test Start Date",
                    },
                },
            ],
        },
    },

    # Return the response
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
        },
        'body': json.dumps(result)
    }
