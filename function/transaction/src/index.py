import json
import boto3
from datetime import datetime
import os

def handler(event, context):
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
    
    ##?##############################################################
            
    result_1st_transactions = [] 

    if "bt_1st_entries" in test_instance:   
        bt_1st_entries = test_instance["bt_1st_entries"]
        
        for data in bt_1st_entries:
            date_time_obj = datetime.strptime(data['Date'], '%Y-%m-%d %H:%M:%S')
            formatted_price = "{:.2f}".format(float(data['Price']) * 100)
            result_1st_transactions.append({ 
                                            "date_time": date_time_obj,
                                            "trade_type": data['Type'],
                                            "entry": data['Entry'],
                                            "price": formatted_price,
                                            "volume": data['Volume'],
                                            "reason": data['Reason'],
                                            "reason_type": data['Reason_type'],
                                        })
            

    if "bt_1st_exits" in test_instance:   
        bt_1st_exits = test_instance["bt_1st_exits"]
        
        for data in bt_1st_exits:
            date_time_obj = datetime.strptime(data['Date'], '%Y-%m-%d %H:%M:%S')
            formatted_price = "{:.2f}".format(float(data['Price']) * 100)
            result_1st_transactions.append({ 
                                            "date_time": date_time_obj,
                                            "trade_type": data['Type'],
                                            "entry": data['Entry'],
                                            "price": formatted_price,
                                            "volume": data['Volume'],
                                            "reason": data['Reason'],
                                            "reason_type": data['Reason_type'],
                                        })

    # Now sort the result_transactions list by date_time
    result_1st_transactions = sorted(result_1st_transactions, key=lambda x: x['date_time'])

    # If you need to convert the datetime objects back to strings in the final output, do:
    for transaction in result_1st_transactions:
        transaction["date_time"] = transaction["date_time"].strftime('%Y-%m-%d %H:%M:%S')
        
    #?###############################################################
        
    result_2nd_transactions = [] 

    if "bt_2nd_entries" in test_instance:   
        bt_2nd_entries = test_instance["bt_2nd_entries"]
        
        for data in bt_2nd_entries:
            date_time_obj = datetime.strptime(data['Date'], '%Y-%m-%d %H:%M:%S')
            formatted_price = "{:.2f}".format(float(data['Price']) * 100)
            result_2nd_transactions.append({ 
                                            "date_time": date_time_obj,
                                            "trade_type": data['Type'],
                                            "entry": data['Entry'],
                                            "price": formatted_price,
                                            "volume": data['Volume'],
                                            "reason": data['Reason'],
                                            "reason_type": data['Reason_type'],
                                        })
            

    if "bt_2nd_exits" in test_instance:   
        bt_2nd_exits = test_instance["bt_2nd_exits"]
        
        for data in bt_2nd_exits:
            date_time_obj = datetime.strptime(data['Date'], '%Y-%m-%d %H:%M:%S')
            formatted_price = "{:.2f}".format(float(data['Price']) * 100)
            result_2nd_transactions.append({ 
                                            "date_time": date_time_obj,
                                            "trade_type": data['Type'],
                                            "entry": data['Entry'],
                                            "price": formatted_price,
                                            "volume": data['Volume'],
                                            "reason": data['Reason'],
                                            "reason_type": data['Reason_type'],
                                        })

    # Now sort the result_transactions list by date_time
    result_2nd_transactions = sorted(result_2nd_transactions, key=lambda x: x['date_time'])

    # If you need to convert the datetime objects back to strings in the final output, do:
    for transaction in result_2nd_transactions:
        transaction["date_time"] = transaction["date_time"].strftime('%Y-%m-%d %H:%M:%S')
        
    #?###############################################################
    
    result_ft_transactions = []

    if "ft_entries" in test_instance:
        ft_entries = test_instance["ft_entries"]

        for data in ft_entries:
            # Convert Unix timestamp in milliseconds to datetime object
            date_time_obj = datetime.fromtimestamp(int(data['Time_msc']) / 1000.0)
            formatted_price = "{:.2f}".format(float(data['Price']) * 100)
            result_ft_transactions.append({
                "date_time": date_time_obj,
                "ticket_number": data["Ticket"],
                "trade_type": data["Type"],
                "entry": data["Entry"],
                "price": formatted_price,
                "volume": data["Deal_Volume"],
                "reason": data["Reason"],
                "reason_type": data["Comment"],
            })

    if "ft_exits" in test_instance:
        ft_exits = test_instance["ft_exits"]

        for data in ft_exits:
            # Convert Unix timestamp in milliseconds to datetime object
            date_time_obj = datetime.fromtimestamp(int(data['Time_msc']) / 1000.0)
            formatted_price = "{:.2f}".format(float(data['Price']) * 100)
            result_ft_transactions.append({
                "date_time": date_time_obj,
                "ticket_number": data["Ticket"],
                "trade_type": data["Type"],
                "entry": data["Entry"],
                "price": formatted_price,
                "volume": data["Deal_Volume"],
                "reason": data["Reason"],
                "reason_type": data["Comment"],
            })

    # Now sort the result_transactions list by date_time
    result_ft_transactions = sorted(result_ft_transactions, key=lambda x: x['date_time'])

    # If you need to convert the datetime objects back to strings in the final output, do:
    for transaction in result_ft_transactions:
        transaction["date_time"] = transaction["date_time"].strftime('%Y-%m-%d %H:%M:%S')
        
    #?############################################################### 
            
    result =   {
    "tractions": 
      {
        "first_back_test": {
          "roi": test_instance['bt_1st_roi'] if 'bt_1st_roi' in test_instance else None,
          "start_date": test_instance['bt_start_date'],
          "end_date": test_instance['bt_end_date'],
          "investment": test_instance['bt_initial_investment'],
          "max_draw_down": "test", # <-- need to write a function for maxDrawDown
          "market_return": "test", # <-- need to write a function for marketReturn
          "win_loss_ratio": "test", # <-- need to write a function for winLossRatio
          "transactions": result_1st_transactions,
        },
        "second_back_test": {
          "roi": test_instance['bt_2nd_roi'] if 'bt_2nd_roi' in test_instance else None,
          "start_date": test_instance['bt_2nd_start_date'],
          "end_date": test_instance['bt_2nd_end_date'],
          "investment": test_instance['bt_initial_investment'] if 'bt_initial_investment' in test_instance else None,
          "market_return": "test",
          "win_loss_ratio": "test",
          "transactions": result_2nd_transactions,
        },
        "forward_test": {
          "roi": test_instance['ft_roi'] if 'ft_roi' in test_instance else None,
          "start_date": test_instance['ft_start_date'] if 'ft_start_date' in test_instance else None,
          "end_date": test_instance['ft_end_date'] if 'ft_end_date' in test_instance else None,
          "investment": test_instance['ft_initial_investment'] if 'ft_initial_investment' in test_instance else None,
          "max_draw_down": "test",
          "market_return": "test",
          "win_loss_ratio": "test",
          "transactions": result_ft_transactions,
        },
      },
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
