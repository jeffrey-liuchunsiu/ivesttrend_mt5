import full_bot_process_mac as full
import os
from dotenv import load_dotenv
import boto3
from flask import Flask, jsonify, request
from flask_cors import CORS
from boto3 import resource
from boto3.dynamodb.conditions import Key,Attr
import pytz 
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
# import mt5_tradingbot_mac as ft
import json
from mt5linux import MetaTrader5
import shortuuid
from threading import Thread

from get_news_history_for_OpenAI import analyze_news, analyze_news_gemini_request
from utils.s3_utils import save_dict_to_s3, delete_object_from_s3, delete_folder_from_s3

mt5 = MetaTrader5(
    # host = 'localhost',
    host = '18.141.245.200',
    port = 18812      
)  

app = Flask(__name__)
CORS(app)

# Load environment variables from .env file

test_instances = []

timeframe_minutes = {
    'M1': mt5.TIMEFRAME_M1,
    'M2': mt5.TIMEFRAME_M2,
    'M3': mt5.TIMEFRAME_M3,
    'M4': mt5.TIMEFRAME_M4,
    'M5': mt5.TIMEFRAME_M5,
    'M6': mt5.TIMEFRAME_M6,
    'M10': mt5.TIMEFRAME_M10,
    'M12': mt5.TIMEFRAME_M12,
    'M15': mt5.TIMEFRAME_M15,
    'M20': mt5.TIMEFRAME_M20,
    'M30': mt5.TIMEFRAME_M30,
    'H1': mt5.TIMEFRAME_H1,
    'H2': mt5.TIMEFRAME_H2,
    'H3': mt5.TIMEFRAME_H3,
    'H4': mt5.TIMEFRAME_H4,
    'H6': mt5.TIMEFRAME_H6,
    'H8': mt5.TIMEFRAME_H8,
    'D1': mt5.TIMEFRAME_D1,
    'W1': mt5.TIMEFRAME_W1,
    'MN!': mt5.TIMEFRAME_MN1
}

load_dotenv()

aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
region_name = os.getenv('AWS_REGION')

dynamodb = boto3.resource('dynamodb', 
                          aws_access_key_id=aws_access_key_id, 
                          aws_secret_access_key=aws_secret_access_key, 
                          region_name=region_name)

# table = dynamodb.Table('test_by_users-dev')
# tests_table = dynamodb.Table('TestInstance-hj4kjln2cvcg5cjw6tik2b2grq-dev')
tests_table = dynamodb.Table('TestInstance-ambqia6vxrcgzfv4zl44ahmlp4-dev')
s3_bucket_name = 'investtrend-test-data'



@app.route("/create_test", methods=["POST"])
def create_test():
    try:
        # Parse request data
        data = request.get_json()
        # test_id = data.get("test_id")
        user = data.get("user")
        # uuid_id = str(uuid.uuid4())
        uuid_id = shortuuid.uuid()[:16]
        
        mt5_magic_id = create_new_magic_id()

        # Validate required fields
        if  not user:
            return jsonify({"error": "Missing 'user' field"}), 400

        # Check if test_id already exists and generate new uuid
        if test_id_exists(tests_table, uuid_id) or test_id_exists_in_memory(test_instances, uuid_id):
            uuid_id = shortuuid.uuid()[:16]

        # Create test instance
        test_instance = create_test_instance(data,uuid_id,mt5_magic_id)
        
        if test_instance is None:
            return jsonify({"error": "Invalid test instance data"}), 400
        
        test_instance.fetch_stock_price_and_volume()
        
        s3Key_stock_close_price = f'{uuid_id}/stock_close_price.json'
        save_dict_to_s3(s3_bucket_name, test_instance.stock_close_price, s3Key_stock_close_price)
        test_instance.s3Key_stock_close_price = s3Key_stock_close_price
        
        s3Key_stock_volume = f'{uuid_id}/stock_volume.json'
        save_dict_to_s3(s3_bucket_name, test_instance.stock_volume, s3Key_stock_volume)
        test_instance.s3Key_stock_volume = s3Key_stock_volume
        
        
        
        update_response = save_test_instance(tests_table, test_instance, user, uuid_id,mt5_magic_id)
        if update_response['ResponseMetadata']['HTTPStatusCode'] == 200:
            # Add test instance to in-memory list and DynamoDB
            test_instance.parse_and_convert_parameters()
            test_instances.append({"test_id": uuid_id, "test_instance": test_instance})

    
        

        return jsonify({
                        "success":True,
                        "test_id":uuid_id,
                        "magic_id":mt5_magic_id,
                        "message": "Test instance created successfully and saved in DynamoDB"
                        }), 201

    except Exception as e:
        return jsonify({"success":False,"error": str(e)}), 500
    
def create_new_magic_id():
    
    largest_mt5_magic = 0

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
        response = tests_table.scan(**scan_kwargs)
        items = response.get('Items', [])

        for item in items:
            mt5_magic_value = item['mt5_magic_id']
            if largest_mt5_magic is None or mt5_magic_value > largest_mt5_magic:
                largest_mt5_magic = mt5_magic_value
        
        start_key = response.get('LastEvaluatedKey', None)
        done = start_key is None


    # Print the largest value
    # print(largest_value)
    
    return int(largest_mt5_magic) + 1

def test_id_exists(table, test_id):
    """Check if a test ID already exists in the provided DynamoDB table."""
    response = table.get_item(Key={'id': test_id})
    return 'Item' in response

def test_id_exists_in_memory(test_instances, test_id):
    """Check if a test ID exists in the in-memory list."""
    return any(instance["test_id"] == test_id for instance in test_instances)

def create_test_instance(data,uuid_id, mt5_magic_id):
    """Create and return a new test instance from request data."""
    try:
        return full.Test(
            test_strategy_name=data["test_strategy_name"],
            strategy_type=data["strategy_type"],
            test_id=uuid_id,
            test_name=data["test_name"],
            mt5_magic_id=int(mt5_magic_id),
            bt_symbol=data["bt_symbol"],
            bt_atr_period=data["bt_atr_period"],
            bt_multiplier=data["bt_multiplier"],
            bt_start_date=datetime.strptime(data["bt_start_date"], "%Y-%m-%d"),
            bt_end_date=datetime.strptime(data["bt_end_date"], "%Y-%m-%d"),
            bt_2nd_start_date=datetime.strptime(data["bt_2nd_start_date"], "%Y-%m-%d"),
            bt_2nd_end_date=datetime.strptime(data["bt_2nd_end_date"], "%Y-%m-%d"),
            bt_time_frame_backward=data["bt_time_frame_backward"],
            bt_initial_investment=data["bt_initial_investment"],
            bt_lot_size=data["bt_lot_size"],
            bt_sl_size=data["bt_sl_size"],
            bt_tp_size=data["bt_tp_size"],
            bt_commission=data["bt_commission"],
            ft_symbol=data["ft_symbol"],
            ft_start_date=data["ft_start_date"],
            ft_end_date=data["ft_end_date"],
            ft_time_frame_forward=data["ft_time_frame_forward"],
            ft_initial_investment=data["ft_initial_investment"],
            ft_lot_size=data["ft_lot_size"],
            ft_sl_size=data["ft_sl_size"],
            ft_tp_size=data["ft_tp_size"]
        )
    except KeyError:  # Missing data fields will raise KeyError
        return None
    
def save_test_instance(table, instance, user, uuid_id,mt5_magic_id):
    """Save a test instance to the provided DynamoDB table."""
    try:
        current_time = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
       
        update_response = table.put_item(Item={
            'id': uuid_id,
            'test_id': uuid_id,
            "test_name": instance.test_name,
            "mt5_magic_id": int(mt5_magic_id),
            'user': user,
            'test_strategy_name': instance.test_strategy_name,
            'strategy_type': instance.strategy_type,
            'bt_symbol': instance.bt_symbol,
            'bt_atr_period': instance.bt_atr_period,
            'bt_multiplier': instance.bt_multiplier,
            'bt_start_date': instance.bt_start_date.strftime("%Y-%m-%d"),
            'bt_end_date': instance.bt_end_date.strftime("%Y-%m-%d"),
            'bt_2nd_start_date': instance.bt_2nd_start_date.strftime("%Y-%m-%d"),
            'bt_2nd_end_date': instance.bt_2nd_end_date.strftime("%Y-%m-%d"),
            'bt_time_frame_backward': instance.bt_time_frame_backward,
            'bt_initial_investment': instance.bt_initial_investment,
            'bt_lot_size': instance.bt_lot_size,
            'bt_sl_size': instance.bt_sl_size,
            'bt_tp_size': instance.bt_tp_size,
            'bt_commission': instance.bt_commission,
            'ft_symbol': instance.ft_symbol,
            'ft_start_date': instance.ft_start_date,
            'ft_end_date': instance.ft_end_date,
            'ft_time_frame_forward': instance.ft_time_frame_forward,
            'ft_initial_investment': instance.ft_initial_investment,
            'ft_lot_size': instance.ft_lot_size,
            'ft_sl_size': instance.ft_sl_size,
            'ft_tp_size': instance.ft_tp_size,
            's3Key_stock_close_price': instance.s3Key_stock_close_price,
            's3Key_stock_volume': instance.s3Key_stock_volume,
            'create_time': current_time,
            'state': "Created"
        })
        return update_response
    except Exception as e:
        print(f"An error occurred while saving the test instance: {str(e)}")
        # Handle the error as per your requirements

@app.route('/find_best_parameters', methods=['POST'])
def find_best_parameters():
    try:
        data = request.get_json()

        # Extract atr and multiplier from the request data, use defaults if not provided
        test_id = data.get('test_id')
        atr = data.get('atr')
        multiplier = data.get('multiplier')
        
        if test_id is None:
            return jsonify({"error": "Missing test_id or user"}), 400

        # Query DynamoDB to find the item based on test_id
        response = tests_table.get_item(Key={'id': test_id})
        if 'Item' not in response:
            return jsonify({"error": "Test instance not found in DynamoDB"}), 404

        item = response['Item']

        # Check if the end_date key exists or if the test is already active
        if 'test_end_date' in item or (item.get('state') != "Created"):
            return jsonify({"error": "Test cannot be started as it has already end or is already running"}), 403

        # Find the test instance in the global list by test_id
        test_instance_data = next(
            (inst for inst in test_instances if inst["test_id"] == test_id), None)

        # If the test instance is not found, return an error
        if test_instance_data is None:
            return jsonify({"error": "Test instance not found"}), 400
        
        # Retrieve the test_instance from the stored data
        test_instance = test_instance_data["test_instance"]
        
        test_instance.parse_and_convert_parameters()
        # test_instance.find_best_parameters_api(atr=atr, multiplier=multiplier)
        test_instance.find_best_parameters(atr=atr, atr_multiplier=multiplier)
        
        update_response = tests_table.update_item(
        Key={'id': test_id},
        UpdateExpression='SET #bt_atr_period = :val1, #bt_multiplier = :val2',
        ExpressionAttributeNames={
            '#bt_atr_period': 'bt_atr_period',
            "#bt_multiplier": "bt_multiplier" # Use ExpressionAttributeNames to avoid conflicts with reserved words
        },
        ExpressionAttributeValues={
            ':val1': str(test_instance.bt_atr_period),
            ':val2': str(test_instance.bt_multiplier)
            
        }
    )
        if update_response['ResponseMetadata']['HTTPStatusCode'] != 200:
            # Call the method from the class instance
            return jsonify({"error": "Failed to update DynamoDB"}), 500
            

        # Prepare the response data
        response_data = {
            "ATR Period": str(test_instance.bt_atr_period),
            "Multiplier": str(test_instance.bt_multiplier),
            # "ROI": str(test_instance.bt_first_roi)
        }

        # Return the response data as JSON
        return jsonify(response_data), 200  # HTTP 200 OK

    except Exception as e:
        # Log the error for debugging
        app.logger.error(f"An error occurred: {str(e)}")

        # Return a JSON response with the error message and a server error status code
        return jsonify({'error': 'An error occurred while processing your request.'}), 500  # HTTP 500 Internal Server Error
    
    
@app.route("/start_forward_test", methods=["POST"])
def start_test():
    # Extract test_id and user from the request data
    test_id = request.json.get("test_id")
    # user = request.json.get("user")  # Assuming user is also sent in the request

    if test_id is None :
        return jsonify({"error": "Missing test_id"}), 400

    # Query DynamoDB to find the item based on test_id
    response = tests_table.get_item(Key={'id': test_id})
    if 'Item' not in response:
        return jsonify({"error": "Test instance not found in DynamoDB"}), 404

    item = response['Item']

    # Check if the end_date key exists or if the test is already active
    if 'test_end_date' in item or (item.get('state') == "Running"):
        return jsonify({"error": "Test cannot be started as it has already running or end"}), 403

    # Find the test instance in the global list by test_id
    test_instance_data = next(
        (inst for inst in test_instances if inst["test_id"] == test_id), None)

    # If the test instance is not found, return an error
    if test_instance_data is None:
        return jsonify({"error": "Test instance not found"}), 400

    # Retrieve the test_instance from the stored data
    test_instance = test_instance_data["test_instance"]
    
    if test_instance.bt_atr_period is None or test_instance.bt_multiplier is None :
        return jsonify({"error": "Please define ATR period and Multiplier"}), 400

    # Update the item in DynamoDB to set active to True and add the current start_time
    # current_time = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    # Define the Hong Kong timezone
    hong_kong = pytz.timezone('Asia/Hong_Kong')

    # Get the current time in UTC, add one day, and then convert to Hong Kong time
    current_time = datetime.now().replace(tzinfo=pytz.utc)
    hong_kong_time = current_time.astimezone(hong_kong)

    # Format the time to the desired string format
    formatted_time = hong_kong_time.strftime('%Y-%m-%d')  # ISO 8601 format in UTC
    update_response = tests_table.update_item(
        Key={'id': test_id},
        UpdateExpression='SET #state = :val1, #ft_start_date = :val2',
        ExpressionAttributeNames={
            '#state': 'state',
            "#ft_start_date": "ft_start_date" # Use ExpressionAttributeNames to avoid conflicts with reserved words
        },
        ExpressionAttributeValues={
            ':val1': "Running",
            ':val2': formatted_time
        }
    )
    if update_response['ResponseMetadata']['HTTPStatusCode'] == 200:
        # Start the test using a function from the 'full' module
        full.start_forward_test_thread(test_instance)
        test_instance.edit_parameters ({"state":"Running","ft_start_date":datetime.strptime(formatted_time, '%Y-%m-%d')})# Uncomment this line if you have the full module

    # Check if the update was successful
    if update_response['ResponseMetadata']['HTTPStatusCode'] != 200:
        return jsonify({"error": "Failed to update DynamoDB"}), 500

    # Return a success message indicating the test has started
    return jsonify({"message": "Test started and DynamoDB updated"})



@app.route("/stop_forward_test", methods=["POST"])
def stop_test():
    # Extract test_id and user from the request data
    test_id = request.json.get("test_id")
    if test_id is None:
        return jsonify({"error": "Missing test_id or user"}), 400

    # Query DynamoDB to find the item based on user and test_id
    response = tests_table.get_item(Key={'id': test_id})
    if 'Item' not in response:
        return jsonify({"error": "Test instance not found"}), 404

    # Find the test instance in the global list by test_id
    test_instance_data = next(
        (inst for inst in test_instances if inst["test_id"] == test_id), None)
    
    # If the test instance is not found, return an error
    if test_instance_data is None:
        return jsonify({"error": "Test instance not found"}), 400

    # Retrieve the test_instance from the stored data
    test_instance = test_instance_data["test_instance"]

    # Stop the test using a function from the 'full' module
    full.stop_forward_test_thread(test_instance)
    
    # Define the Hong Kong timezone
    hong_kong = pytz.timezone('Asia/Hong_Kong')

    # Update the item in DynamoDB to set active to False and add the current end_time
    #!!!!!!!!!!!!!!!!!!!
    current_time = datetime.now().replace(tzinfo=pytz.utc) + timedelta(days=1)
    # current_time = datetime.now().replace(tzinfo=pytz.utc) 
    hong_kong_time = current_time.astimezone(hong_kong)

    # Format the time to the desired string format
    formatted_time = hong_kong_time.strftime('%Y-%m-%d')
    update_response = tests_table.update_item(
        Key={'id': test_id},
        UpdateExpression='SET #state = :val1, #ft_end_date = :val2',
        ExpressionAttributeNames={
            '#state': 'state',
            "#ft_end_date": "ft_end_date" # Use ExpressionAttributeNames to avoid conflicts with reserved words
        },
        ExpressionAttributeValues={
            ':val1': "End",
            ':val2': formatted_time
        }
    )

    if update_response['ResponseMetadata']['HTTPStatusCode'] == 200:
        # Start the test using a function from the 'full' module
        full.stop_forward_test_thread(test_instance)
        test_instance.edit_parameters ({"state":"End","stop_flag_live_trade":True,"ft_end_date":datetime.strptime(formatted_time, '%Y-%m-%d')})# Uncomment this line if you have the full module
    else:
        return jsonify({"error": "Failed to update DynamoDB"}), 500

    # Return a success message indicating the test has stopped
    return jsonify({"message": "Test stopped and DynamoDB updated"})

@app.route("/get_test_instances", methods=["POST"])
def get_test_instances():
    test_id = request.json.get("test_id")

        # Perform the scan operation to retrieve all items from the table
    response = tests_table.get_item(Key={'id': test_id})
    # Extract the items from the response
    test_instances = response.get('Item', [])    

    # Paginate if there are more items to scan
    while 'LastEvaluatedKey' in response:
        response = tests_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        test_instances.extend(response.get('Items', []))

    # Return the list of test instances as JSON
    return jsonify(test_instances)

@app.route("/get_in_memory_test_instances", methods=["POST"])
def get_in_memory_test_instances():
    test_id = request.json.get("test_id")

    test_instance_data = next(
        (inst for inst in test_instances if inst["test_id"] == test_id), None)

    if test_instance_data is None:
        return jsonify({"error": "Test instance not found"})

    test_instance = test_instance_data["test_instance"]
    
    result = {
            'test_id': test_instance.test_id,
            'test_strategy_name': test_instance.test_strategy_name,
            'bt_symbol': test_instance.bt_symbol,
            'bt_atr_period': test_instance.bt_atr_period,
            'bt_multiplier': test_instance.bt_multiplier,
            'bt_start_date': test_instance.bt_start_date.strftime("%Y-%m-%d"),
            'bt_end_date': test_instance.bt_end_date.strftime("%Y-%m-%d"),
            'bt_2nd_start_date': test_instance.bt_2nd_start_date.strftime("%Y-%m-%d"),
            'bt_2nd_end_date': test_instance.bt_2nd_end_date.strftime("%Y-%m-%d"),
            'bt_time_frame_backward': test_instance.bt_time_frame_backward,
            'bt_initial_investment': test_instance.bt_initial_investment,
            'bt_lot_size': test_instance.bt_lot_size,
            'bt_sl_size': test_instance.bt_sl_size,
            'bt_tp_size': test_instance.bt_tp_size,
            'bt_commission': test_instance.bt_commission,
            'ft_symbol': test_instance.ft_symbol,
            'ft_start_date': test_instance.ft_start_date,
            'ft_end_date': test_instance.ft_end_date,
            'ft_time_frame_forward': test_instance.ft_time_frame_forward,
            'ft_initial_investment': test_instance.ft_initial_investment,
            'ft_lot_size': test_instance.ft_lot_size,
            'ft_sl_size': test_instance.ft_sl_size,
            'ft_tp_size': test_instance.ft_tp_size,
            'state': test_instance.state,
            'stop_flag_live_trade': test_instance.stop_flag_live_trade,
            'stop_flag_check_status': test_instance.stop_flag_check_status,
            
            'bt_1st_roi': test_instance.bt_1st_roi,
            'bt_2nd_roi': test_instance.bt_2nd_roi,
            'bt_overall_roi': test_instance.bt_overall_roi,
            'bt_1st_entries': test_instance.bt_1st_entries,
            'bt_2nd_entries': test_instance.bt_2nd_entries,
            'bt_overall_entries': test_instance.bt_overall_entries,
            'bt_1st_exits': test_instance.bt_1st_exits,
            'bt_2nd_exits': test_instance.bt_2nd_exits,
            'bt_overall_exits': test_instance.bt_overall_exits,
            'bt_1st_final_equity': test_instance.bt_1st_final_equity,
            'bt_2nd_final_equity': test_instance.bt_2nd_final_equity,
            'bt_overall_final_equity': test_instance.bt_overall_final_equity,
            'bt_1st_equity_per_day': test_instance.bt_1st_equity_per_day,
            'bt_2nd_equity_per_day': test_instance.bt_2nd_equity_per_day,
            'bt_overall_equity_per_day': test_instance.bt_overall_equity_per_day,
            'ft_entries': test_instance.ft_entries,
            'ft_exits': test_instance.ft_exits,
            'ft_final_equity': test_instance.ft_final_equity,
            'ft_equity_per_day': test_instance.ft_equity_per_day,
            'ft_roi': test_instance.ft_roi
        }

    return jsonify(result), 200


@app.route("/backtesting", methods=["POST"])
def backtesting():

    """
    This function handles backtesting requests.
    It retrieves the test instance, performs backtesting,
    and updates the DynamoDB and S3 with the results.
    """

    # Retrieve the test_id from the request body
    test_id = request.json.get("test_id")

    # Check if the test_id is provided
    if test_id is None:
        return jsonify({"error": "Missing test_id"}), 400

    # Find the test instance data in the test_instances list
    test_instance_data = next(
        (inst for inst in test_instances if inst["test_id"] == test_id), None)

    # Check if the test instance is found
    if test_instance_data is None:
        return jsonify({"error": "Test instance not found"}), 400

    # Retrieve the test_instance from the stored data
    test_instance = test_instance_data["test_instance"]

    # Get data and add technical indicators for different time frames
    test_instance.bt_get_data_and_add_indicator("1ST", visualize=False)
    test_instance.bt_get_data_and_add_indicator("2nd", visualize=False)
    test_instance.bt_get_data_and_add_indicator("all", visualize=False)

    # Perform backtesting for different time frames
    test_instance.backtest("1ST")
    test_instance.backtest("2ND")
    test_instance.backtest("ALL")

    # Create a dictionary to store the backtesting results
    result = {
        "bt_first_roi": test_instance.bt_1st_roi,
        "bt_second_roi": test_instance.bt_2nd_roi,
        "bt_overall_roi": test_instance.bt_overall_roi,
        "bt_1st_entries": test_instance.bt_1st_entries,
        "bt_2nd_entries": test_instance.bt_2nd_entries,
        "bt_overall_entries": test_instance.bt_overall_entries,
        "bt_1st_exits": test_instance.bt_1st_exits,
        "bt_2nd_exits": test_instance.bt_2nd_exits,
        "bt_overall_exits": test_instance.bt_overall_exits,
        "bt_1st_final_equity": test_instance.bt_1st_final_equity,
        "bt_2nd_final_equity": test_instance.bt_2nd_final_equity,
        "bt_overall_final_equity": test_instance.bt_overall_final_equity,
        "bt_1st_equity_per_day": test_instance.bt_1st_equity_per_day,
        "bt_2nd_equity_per_day": test_instance.bt_2nd_equity_per_day,
        "bt_overall_equity_per_day": test_instance.bt_overall_equity_per_day,
    }

    try:
        s3Key = f'{test_id}/backtest_data.json'
        # Update the DynamoDB table with the backtesting results
        tests_table.update_item(
            Key={'id': test_id},
            UpdateExpression='SET bt_1st_roi = :1st_roi, bt_2nd_roi = :2nd_roi, bt_overall_roi = :overall_roi, s3Key_backtest_data = :s3Key_backtest_data',
            ExpressionAttributeValues={
                ':1st_roi': str(test_instance.bt_1st_roi),
                ':2nd_roi': str(test_instance.bt_2nd_roi),
                ':overall_roi': str(test_instance.bt_overall_roi),
                ':s3Key_backtest_data': str(s3Key),
            },
            ReturnValues='NONE')

        # Save the backtesting results to S3
        save_dict_to_s3(s3_bucket_name, result, s3Key)
        test_instance.s3Key_backtest_data = s3Key

    except Exception as e:
        # Log the exception
        print(f"Failed to update DynamoDB/S3: {e}")

        # Revert all result attributes to None
        result = {key: None for key in result}

        # Revert all test_instance attributes related to backtesting to None
        test_instance.bt_1st_roi = None
        test_instance.bt_2nd_roi = None
        test_instance.bt_overall_roi = None
        test_instance.bt_1st_entries = None
        test_instance.bt_2nd_entries = None
        test_instance.bt_overall_entries = None
        test_instance.bt_1st_exits = None
        test_instance.bt_2nd_exits = None
        test_instance.bt_overall_exits = None
        test_instance.bt_1st_final_equity = None
        test_instance.bt_2nd_final_equity = None
        test_instance.bt_overall_final_equity = None
        test_instance.bt_1st_equity_per_day = None
        test_instance.bt_2nd_equity_per_day = None
        test_instance.bt_overall_equity_per_day = None

        return jsonify({"error": "Failed to update DynamoDB"}), 500

    # Return the backtesting results
    return jsonify(result), 200

def process_over_all(over_all):
    # Initialize an empty dictionary to hold the processed data
    processed_data = {}

    # Go through each item in the 'over_all' list
    for item in over_all:
        # Get the prefix based on the 'entry' value
        prefix = "entry_" if item["entry"] == 0 else "exit_"

        # Create a new dictionary with the keys prefixed
        new_item = {f"{prefix}{key}": value for key, value in item.items()}

        # Get the position_id
        position_id = item["position_id"]

        # If this position_id is already in the processed_data dictionary, combine the objects
        if position_id in processed_data:
            processed_data[position_id].update(new_item)
        else:
            processed_data[position_id] = new_item

    # Convert the processed_data dictionary to a list of dictionaries
    processed_list = list(processed_data.values())
    # Remove 'exit_magic' and 'exit_symbol' from all dictionaries in the list
    processed_list = [{k: v for k, v in item.items() if k not in ['exit_magic', 'exit_symbol']} for item in processed_list]

    return processed_list
from datetime import datetime, timedelta


def update_test_instance(test_id, test_instance):
    s3Key = f'{test_id}/forward_test_data.json'
    try:
        test_instance.get_forward_test_result()
        result = {
          "ft_roi": test_instance.ft_roi,
          "ft_entries": test_instance.ft_entries,
          "ft_exits": test_instance.ft_exits,
          "ft_equity_per_day": test_instance.ft_equity_per_day,
          "ft_final_equity": test_instance.ft_final_equity
        }
        
        tests_table.update_item(
            Key={'id': test_id},
            UpdateExpression='SET ft_roi = :ft_roi, s3Key_forward_test_data = :s3Key_forward_test_data',
            ExpressionAttributeValues={
                ':ft_roi': str(result["ft_roi"]),
                ':s3Key_forward_test_data': str(s3Key)
            },
            ReturnValues='NONE'
        )
        
        save_dict_to_s3(s3_bucket_name, result, s3Key)
        test_instance.s3Key_forward_test_data = s3Key
        
        setattr(test_instance, "ft_result_processing", False)
    except Exception as e:
        print(f"Failed to update DynamoDB: {e}")
        for key in ["ft_roi", "ft_entries", "ft_exits", "ft_equity_per_day", "ft_final_equity"]:
            setattr(test_instance, key, None)

@app.route("/get_forward_test_result", methods=["POST"])
def get_test_result():
    test_id = request.json.get("test_id")
    if test_id is None:
        return jsonify({"error": "Missing test_id"}), 400

    test_instance_data = next(
        (inst for inst in test_instances if inst["test_id"] == test_id), None)
    if test_instance_data is None:
        return jsonify({"error": "Test instance not found"}), 400

    # Start the background task for updating the test instance
    test_instance = test_instance_data["test_instance"]
    
    hong_kong = pytz.timezone('Asia/Hong_Kong')
    current_time = datetime.now().replace(tzinfo=pytz.utc)
    hong_kong_time = current_time.astimezone(hong_kong)
    formatted_time = hong_kong_time.strftime('%Y-%m-%d')
    
    # datetime_obj = datetime.strptime(test_instance.ft_start_date, "%Y-%m-%d %H:%M:%S")
    test_instance_date_only = test_instance.ft_start_date.strftime("%Y-%m-%d")
    
    print('formatted_time: ', formatted_time)
    print('test_instance.ft_start_date : ', test_instance.ft_start_date )
    print('test_instance.ft_start_date : ', test_instance.ft_start_date == formatted_time )
    
    
    # if test_instance_date_only == formatted_time:
        
    #     return jsonify({"error": "Cannot get the result on the forward test start date."}), 400
    
    thread = Thread(target=update_test_instance, args=(test_id, test_instance))
    thread.start()
    setattr(test_instance, "ft_result_processing", True)

    # Return an immediate response
    return jsonify({"message": "Test result processing has been started."}), 202

@app.route("/get_forward_test_progress_percentage", methods=["POST"])
def get_forward_test_progress_percentage():
    test_id = request.json.get("test_id")
    if test_id is None:
        return jsonify({"error": "Missing test_id"}), 400

    test_instance_data = next(
        (inst for inst in test_instances if inst["test_id"] == test_id), None)
    if test_instance_data is None:
        return jsonify({"error": "Test instance not found"}), 400

    # Start the background task for updating the test instance
    test_instance = test_instance_data["test_instance"]
    processing = test_instance.ft_result_processing
    if processing:
        percentage = test_instance.ft_getting_result_progress_percentage
        elapsed_time = test_instance.elapsed_time
        estimated_remaining_time = test_instance.estimated_remaining_time

        # Return an immediate response
        return jsonify({"processing":True, "percentage": percentage, "elapsed_time":elapsed_time, "estimated_remaining_time":estimated_remaining_time}), 200
    
    return jsonify({"processing":False, "percentage": None,"elapsed_time":None, "estimated_remaining_time":None}), 500
    

@app.route("/get_test_result_not_thread", methods=["POST"])
def get_test_result_not_thread():
    test_id = request.json.get("test_id")
    if test_id is None:
        return jsonify({"error": "Missing test_id"}), 400

    test_instance_data = next(
        (inst for inst in test_instances if inst["test_id"] == test_id), None)
    if test_instance_data is None:
        return jsonify({"error": "Test instance not found"}), 400
    
    test_instance = test_instance_data["test_instance"]
    result = {
        "test_id": getattr(test_instance, "test_id"),
        "is_processing": getattr(test_instance, "ft_result_processing")
    }

    # Return an immediate response
    return jsonify(result), 200

@app.route("/get_analyze_news", methods=["POST"])
def get_analyze_news():
    test_id = request.json.get("test_id")
    limit = int(request.json.get("limit"))
    start_date = request.json.get("start_date")
    end_date = request.json.get("end_date")
    symbol = request.json.get("symbol")
    impact_above = int(request.json.get("impact_over"))
    impact_below = int(request.json.get("impact_over")) 
    
    table_name = 'InvestNews-ambqia6vxrcgzfv4zl44ahmlp4-dev'
    table = dynamodb.Table(table_name)
    
    if test_id is None:
        return jsonify({"error": "Missing test_id"}), 400
    
    if impact_above < 0 or impact_below > 0:
        return jsonify({"error": "Invalid values for impact_above or impact_below"}), 400
    
    test_instance_data = next(
        (inst for inst in test_instances if inst["test_id"] == test_id), None)
    if test_instance_data is None:
        return jsonify({"error": "Test instance not found"}), 400
    
    test_instance = test_instance_data["test_instance"]
    
    if symbol == None:
        symbol = getattr(test_instance, "ft_symbol")
    if start_date == None:
        start_date = getattr(test_instance, "bt_start_date").strftime("%Y-%m-%d")
    if end_date == None:    
        end_date = datetime.now().strftime("%Y-%m-%d")
    if impact_above == None:
        impact_above = 50 
    if impact_below == None:
        impact_below -50
    if limit == None:
        limit == 10
    
    # news_results = analyze_news_gemini_request(symbol, start_date, end_date, limit)
    
    # Paginate through the results manually to find the last 10 items
    last_items = []
    exclusive_start_key = None

    while True:
        scan_kwargs = {
            'FilterExpression': Attr('date_time').between(start_date, end_date) &
                        Attr('ticker_symbol').contains(symbol) 
        }
        
        # Only add ExclusiveStartKey to arguments if it's not None
        if exclusive_start_key:
            scan_kwargs['ExclusiveStartKey'] = exclusive_start_key

        response = table.scan(**scan_kwargs)
        
        items = response.get('Items', [])
        print('items: ', len(items))
        
        filtered_items = [
                item for item in items 
                if int(item['headline_impact']) >= impact_above or int(item['headline_impact']) <= impact_below
            ]
        
        # Prepend to ensure latest items are kept if we exceed 10
        last_items = filtered_items + last_items
        last_items = last_items[-(limit):]  # Keep only the last 10 items

        if 'LastEvaluatedKey' not in response or len(last_items) >= limit:
            break
        exclusive_start_key = response['LastEvaluatedKey']

    # Return an immediate response
    return jsonify(last_items), 200
 
    
@app.route('/remove_forward_test', methods=['POST'])
def remove_test():
    # Get test_id from the request body
    data = request.json
    test_id = data.get('test_id')

    if not test_id:
        return jsonify({'error': 'test_id is required'}), 400
    
    test_instance_data = next(
        (inst for inst in test_instances if inst["test_id"] == test_id), None)
    if test_instance_data is None:
        return jsonify({"error": "Test instance not found"}), 400
    
    
    try:
        # Delete the item from DynamoDB table
        delete_folder_from_s3(s3_bucket_name, f"{test_id}/")
        response = tests_table.delete_item(
            Key={
                'id': test_id  # Assuming 'test_id' is the partition key
            }
        )
        # Check if the item was actually deleted
        if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
            # Remove the test instance from the local list
            # Stop the test using a function from the 'full' module
            test_instance = test_instance_data["test_instance"]
            full.stop_forward_test_thread(test_instance)
            test_instances[:] = [inst for inst in test_instances if inst["test_id"] != test_id]
            print('test_instances: ', len(test_instances))
            return jsonify({'message': 'Test removed successfully'}), 200
        
            
        else:
            return jsonify({'error': 'Failed to remove test from DynamoDB'}), 500

        
    except ClientError as e:
        # Handle specific DynamoDB errors or general AWS errors
        return jsonify({'error': str(e)}), 500
    
@app.route('/get_tests_by_user', methods=['POST'])
def get_tests_by_user():
    data = request.json
    user = data.get("user")
    test_strategy_name = data.get("test_strategy_name")  # Optional sort key filter

    if not user:
        return jsonify({'error': 'User is required'}), 400

    try:
        key_condition = Key('user').eq(user)
        if test_strategy_name:
            key_condition &= Key('test_strategy_name').eq(test_strategy_name)

        # Perform a query operation using the secondary index
        response = tests_table.query(
            IndexName='user-test_strategy_name-index',  # Use the secondary index
            KeyConditionExpression=key_condition
        )
        items = response.get('Items', [])
        
        # Handle pagination if the dataset is large
        while 'LastEvaluatedKey' in response:
            response = tests_table.query(
                IndexName='user-test_strategy_name-index',  # Use the secondary index
                KeyConditionExpression=key_condition,
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))

        return jsonify(items), 200

    except ClientError as e:
        return jsonify({'error': str(e)}), 500
    
    
def get_tests_by_state(index_name, states, test_instances):

    try:
        # Reference the DynamoDB table
        test_instances_data = []
        # Iterate over the states and perform a separate query for each
        for state in states:
            response = tests_table.query(
                IndexName=index_name,
                KeyConditionExpression=Key('state').eq(state)
            )

            # Check if any items were returned and append them to the list
            if 'Items' in response:
                for item in response['Items']:
                    test_instances_data.append(item)

                # Handle the potential for paginated results
                while 'LastEvaluatedKey' in response:
                    response = tests_table.query(
                        IndexName=index_name,
                        KeyConditionExpression=Key('state').eq(state),
                        ExclusiveStartKey=response['LastEvaluatedKey']
                    )
                    test_instances_data.extend(response['Items'])
        print('test_instances_data: ', len(test_instances_data))
        for test_instance_data in test_instances_data:
            test = full.Test()
            test.edit_parameters(test_instance_data)
            test.parse_and_convert_parameters()
            test_instances.append({"test_id": test.test_id, "test_instance": test})
            
        print_test = [test['test_id'] for test in test_instances]
        print('test_instances: ', print_test)
            
        print("Done re-create test instances.")
    except ClientError as e:
        print(e.response['Error']['Message'])
    except Exception as e:
        print(str(e))
        
def delete_tests_by_state(index_name, states, test_instances):

    try:
        # Reference the DynamoDB table
        test_instances_data = []
        # Iterate over the states and perform a separate delete for each
        for state in states:
            response = tests_table.query(
                IndexName=index_name,
                KeyConditionExpression=Key('state').eq(state)
            )

            # Check if any items were returned and delete them
            if 'Items' in response:
                for item in response['Items']:
                    test_id = item['test_id']
                    tests_table.delete_item(Key={'id':test_id})
                    delete_folder_from_s3(s3_bucket_name, f'{test_id}/')

                # Handle the potential for paginated results
                while 'LastEvaluatedKey' in response:
                    response = tests_table.query(
                        IndexName=index_name,
                        KeyConditionExpression=Key('state').eq(state),
                        ExclusiveStartKey=response['LastEvaluatedKey']
                    )
                    test_instances_data.extend(response['Items'])
                    for item in response['Items']:
                        tests_table.delete_item(Key={'id':item['test_id']})

        print("Done Del all data in Dynamodb")

    except Exception as e:
        print(f"Error deleting tests: {e}")
        return None

def get_running_instances_and_run():
    
    for inst in test_instances :
        if inst["test_instance"].state == "Running":
            full.start_forward_test_thread(inst["test_instance"])
            # print(inst)



if __name__ == "__main__":
 
    states_to_query = ['Created', 'Running', 'End']
    # delete_tests_by_state('state-index', states_to_query, test_instances)
    created_and_running_tests = get_tests_by_state('state-index', states_to_query, test_instances)
    get_running_instances_and_run()
    
    app.run(host="0.0.0.0", port=8000,debug=False, use_reloader=False)
 

#    result =  {
#     "test": [
#       {
#         "testName": "SuperTrend",
#         "backTestRoi": test_instance.bt_roi,
#         "forwardTestRoi": test_instance.ft_roi,
#         "data": {
#           "backTestResult": {
#             "roi": "",
#             "period": "",
#             "investment": "",
#             "maxDrawDown": "",
#             "marketReturn": "",
#             "transactions": [
#               {
#                 "tradeNo": "",
#                 "tradeType": "",
#                 "dateTime": "",
#                 "priceUS": ""
#               }
#             ]
#           },
#           "forwardTestResult": {
#             "roi": test_instance.ft_roi,
#             "period": "",
#             "investment": test_instance.ft_investment,
#             "maxDrawDown": "lowest_exit_profit",
#             "marketReturn": ft_roi,
#             "transactions": [
#               {
#                 "tradeNo": "",
#                 "tradeType": "",
#                 "dateTime": "",
#                 "priceUS": ""
#               }
#             ]
#           }
#         }
#       }
#     ]
#   }
