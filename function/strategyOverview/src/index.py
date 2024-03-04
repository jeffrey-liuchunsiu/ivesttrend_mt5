import json
import boto3
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
        
    result = {
                "data": [
                    {
                    "stock_crypto": test_instance['bt_symbol'],
                    "strategy_name": test_instance['strategy_type'],
                    "overall_back_test_roi": test_instance['bt_overall_roi'] if 'bt_overall_roi' in test_instance else None,
                    "forward_test_roi": "{:.2f}".format(float(test_instance['ft_roi']) * 100) if 'ft_roi' in test_instance else None,
                    },
                    {
                    "stock_crypto": test_instance['bt_symbol'],
                    "strategy_name": test_instance['test_strategy_name'],
                    "strategy_type": test_instance['strategy_type'],
                    "first_back_test_roi": test_instance['bt_1st_roi'] if 'bt_1st_roi' in test_instance else None,
                    "second_back_test_roi": test_instance['bt_2nd_roi'] if 'bt_2nd_roi' in test_instance else None,
                    "forward_test_roi": "{:.2f}".format(float(test_instance['ft_roi']) * 100) if 'ft_roi' in test_instance else None,
                    "overall_market_roi": "test",
                    "overall_max_drawdown": "test",
                    "overall_win_loss_ratio": "test"
                    }
                ]
            }

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
