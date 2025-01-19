import full_bot_process_mac as full
import os
from dotenv import load_dotenv
import boto3
from flask import Flask, jsonify, request, abort, send_file
from flask_cors import CORS
from boto3 import resource
from boto3.dynamodb.conditions import Key,Attr
import pytz 
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
# import mt5_tradingbot_mac as ft
import json
import math
import requests
from mt5linux import MetaTrader5
import shortuuid
from threading import Thread
import re
from dateutil.parser import parse as parse_date
import yfinance as yf
from decimal import Decimal
import asyncio
import matplotlib.pyplot as plt
from io import BytesIO
import yfinance as yf
import matplotlib
matplotlib.use('Agg')  # Use the 'Agg' backend for non-GUI rendering
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


from get_news_history_for_OpenAI import analyze_news, analyze_news_gemini_request
from utils.tg_utils import add_user_to_channel, create_tg_channel, generate_invite_link
from utils.s3_utils import save_dict_to_s3, delete_object_from_s3, delete_folder_from_s3, get_json_data_from_s3

print("Matt Hello")

mt5 = MetaTrader5(
    # host = 'localhost',
    host = '18.141.245.200',
    port = 18812      
)  

app = Flask(__name__)
CORS(app,resource={
    r"/*":{
        "origins":"*"
    }
})

# Load environment variables from .env file

test_instances = []

time_frame_exchange = {
    '1D' : 'D1',
    '5M' : 'M5'
}

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
user_table = dynamodb.Table('User-ambqia6vxrcgzfv4zl44ahmlp4-dev')
s3_bucket_name = 'investtrend-test-data'

from telethon import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest, DeleteChannelRequest


api_id = os.getenv('api_id')
api_hash = os.getenv('api_hash')
phone = os.getenv('phone')


loop = asyncio.get_event_loop()

# async def create_channel():
#     result = await client(CreateChannelRequest(
#         title='My New Channel',
#         about='This is a description of my new channel',
#         megagroup=False  # True if you want to create a supergroup instead of a channel
#     ))

#     print(f'Channel created with ID: {result.chats[0].id}')
#     return result.chats[0].id



def decimal_default(obj):
    """
    JSON serialization default handler for Decimal objects.

    This function is used as a default handler for JSON serialization when 
    encountering Decimal objects. It converts the Decimal object to a float 
    for serialization. If the object is not a Decimal, it raises a TypeError.

    Args:
        obj: Object to be serialized.

    Returns:
        float: Serialized Decimal object.

    Raises:
        TypeError: If obj is not a Decimal object.
    """

    # Check if the object is an instance of Decimal
    if isinstance(obj, Decimal):  # Check if obj is a Decimal object
        # Convert the Decimal object to a float for serialization
        return float(obj)  # Return the float value of the Decimal object

    # Raise a TypeError if the object is not a Decimal
    raise TypeError("Object of type Decimal is not JSON serializable")  # Raise an error for non-Decimal objects



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
        bt_start_date = datetime.strptime(data["bt_start_date"], "%Y-%m-%d")
        bt_end_date = datetime.strptime(data["bt_end_date"], "%Y-%m-%d")
        
        days_between = (bt_end_date - bt_start_date).days

        # Validate required fields
        if not user:
            return jsonify({"error": "Missing 'user' field"}), 400
        
        if days_between < 7:
            return jsonify({"error": "the test period can not less than 7 days"}), 400
        
        if not data["bt_lot_size"] and not data["bt_initial_investment"]:
            return jsonify({"error": "Please input lot size or initial investment"}), 400
        
        if data["bt_lot_size"] and data["bt_initial_investment"]:
            return jsonify({"error": "You can only input lot size or initial investment"}), 400
        
        if data["bt_lot_size"] :
            if float(data["bt_lot_size"]) < 0.01 or float(data["bt_lot_size"]) > 10000:
                return jsonify({"error": "Lot size must not less than 0.01 or more then 10000"}), 400
        
        if data["bt_initial_investment"]:
            if int(data["bt_initial_investment"]) < 100:
                return jsonify({"error": "Initial Investment must not less than 100"}), 400

        # Check if test_id already exists and generate new uuid
        if test_id_exists(tests_table, uuid_id) or test_id_exists_in_memory(test_instances, uuid_id):
            uuid_id = shortuuid.uuid()[:16]

        # Create test instance
        test_instance = create_test_instance(data, uuid_id, mt5_magic_id, user)
        
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
    
def create_new_magic_id_old():
    
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

def create_new_magic_id():
    
    mt5_history_table = dynamodb.Table('investtrend_mt5_history_deals')
    
    largest_mt5_magic = 0

    # Scan operation parameters
    scan_kwargs = {
        'ProjectionExpression': "magic",  # Only retrieve the 'mt5_magic' column
        'FilterExpression': Attr('magic').exists()  # Filter out items where 'mt5_magic' may not exist
    }

    done = False
    start_key = None

    # Perform the scan
    while not done:
        if start_key:
            scan_kwargs['ExclusiveStartKey'] = start_key
        response = mt5_history_table.scan(**scan_kwargs)
        items = response.get('Items', [])

        for item in items:
            mt5_magic_value = item['magic']
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

def get_stock_price_on_date(symbol, date):
    """Fetches the closing price of a stock symbol on a specific date."""
    stock = yf.Ticker(symbol)
    hist = stock.history(start=date, end=date + timedelta(days=1))
    return hist['Close'][0]

def round_down_to_appropriate(value):
    """Round down the value dynamically based on its magnitude."""
    try:
        if value >= 10000:
            result = math.floor(value / 10000) * 10000
        elif value >= 1000:
            result = math.floor(value / 1000) * 1000
        elif value >= 100:
            result = math.floor(value / 100) * 100
        elif value >= 10:
            result = math.floor(value / 10) * 10
        elif value >= 1:
            result = math.floor(value)
        elif value >= 0.1:
            result = math.floor(value / 0.1) * 0.1
        elif value >= 0.01:
            result = math.floor(value / 0.01) * 0.01
        else:
            result = math.floor(value / 0.001) * 0.001  # Handle very small numbers

        # Format the result to avoid floating-point precision issues
        return float(f"{result:.12g}")
    except TypeError:
        return "Error: Input value must be a number."
    except Exception as e:
        return f"An error occurred: {str(e)}"

    
def round_up_to_appropriate(value):
    """Round up the value dynamically based on its logarithmic magnitude."""
    if value == 0:
        return 0
    magnitude = math.floor(math.log10(abs(value)))
    rounding_factor = 10 ** magnitude
    return math.ceil(value / rounding_factor) * rounding_factor

def create_test_instance(data, uuid_id, mt5_magic_id, user):
    """Create and return a new test instance from request data, including stock price and lot calculation."""
    bt_start_date = datetime.strptime(data["bt_start_date"], "%Y-%m-%d")
    # bt_end_date = datetime.strptime(data["bt_end_date"], "%Y-%m-%d")
    
    # days_between = (bt_end_date - bt_start_date).days
    
    # if days_between > 356:
    #     test_range = 90
    # elif days_between > 90:
    #     test_range = 30
    # elif days_between > 30:
    #     test_range = 7
    # elif days_between > 7:
    #     test_range = 3
    # else:
    #     test_range = 3  # In case the duration is less than or equal to 7 days
        
    lot_size = None
    initial_investment = None
        
    if data["bt_lot_size"]:   
        lot_size = float(data["bt_lot_size"])
    if data["bt_initial_investment"]:     
        initial_investment = int(data["bt_initial_investment"])
        
    symbol_price = get_stock_price_on_date(data["bt_symbol"], bt_start_date)
    rounded_lots = None
    rounded_initial_investment = None
    
    print('initial_investment: ', initial_investment)
    if  initial_investment:
        new_lot_size = initial_investment / symbol_price
        rounded_lots = round_down_to_appropriate(new_lot_size)
        rounded_initial_investment = initial_investment
        print('rounded_initial_investment: ', rounded_initial_investment)
        print('rounded_lots: ', rounded_lots)
        
    if  lot_size:
        new_initial_investment = lot_size * symbol_price
        rounded_initial_investment = round_up_to_appropriate(new_initial_investment)
        rounded_lots = lot_size
        print('rounded_initial_investment: ', rounded_initial_investment)
        print('rounded_lots: ', rounded_lots)
        

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
            # bt_start_date=bt_start_date,
            # bt_end_date=bt_end_date - timedelta(days=test_range),
            # bt_2nd_start_date=bt_end_date - timedelta(days=test_range),
            # bt_2nd_end_date=bt_end_date,
            bt_start_date=data["bt_start_date"],
            bt_end_date=data["bt_end_date"],
            bt_2nd_start_date=data["bt_2nd_start_date"],
            bt_2nd_end_date=data["bt_2nd_end_date"],
            validation_period=data["validation_period"],
            bt_time_frame_backward=data["bt_time_frame_backward"],
            bt_initial_investment=rounded_initial_investment,
            bt_lot_size=rounded_lots,
            bt_sl_size=data["bt_sl_size"],
            bt_tp_size=data["bt_tp_size"],
            bt_commission=data["bt_commission"],
            ft_symbol=data["ft_symbol"],
            ft_start_date=data["ft_start_date"],
            ft_end_date=data["ft_end_date"],
            ft_time_frame_forward=time_frame_exchange[data['bt_time_frame_backward']],
            ft_initial_investment=rounded_initial_investment,
            ft_lot_size=rounded_lots,
            ft_sl_size=data["bt_sl_size"],
            ft_tp_size=data["bt_tp_size"],
            user=user,
            tg_username=data['tg_username'],
            tg_enable=data['tg_enable']
            
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
            'validation_period': instance.validation_period,
            'bt_time_frame_backward': instance.bt_time_frame_backward,
            'bt_initial_investment': str(instance.bt_initial_investment),
            'bt_lot_size': str(instance.bt_lot_size),
            'bt_sl_size': instance.bt_sl_size,
            'bt_tp_size': instance.bt_tp_size,
            'bt_commission': instance.bt_commission,
            'ft_symbol': instance.ft_symbol,
            'ft_start_date': instance.ft_start_date,
            'ft_end_date': instance.ft_end_date,
            'ft_time_frame_forward': instance.ft_time_frame_forward,
            'ft_initial_investment': str(instance.bt_initial_investment),
            'ft_lot_size': str(instance.ft_lot_size),
            'ft_sl_size': instance.ft_sl_size,
            'ft_tp_size': instance.ft_tp_size,
            's3Key_stock_close_price': instance.s3Key_stock_close_price,
            's3Key_stock_volume': instance.s3Key_stock_volume,
            'tg_username': instance.tg_username,
            'tg_enable': instance.tg_enable,
            'create_time': current_time,
            'state': "Created"
        })
        return update_response
    except Exception as e:
        print(f"An error occurred while saving the test instance: {str(e)}")
        # Handle the error as per your requirements

def start_find_best_process(test_id, test_instance, atr, multiplier):
    try:
        test_instance.find_best_parameters(atr=atr, atr_multiplier=multiplier)
        
        tests_table.update_item(
            Key={'id': test_id},
            UpdateExpression='SET #bt_atr_period = :val1, #bt_multiplier = :val2',
            ExpressionAttributeNames={
                '#bt_atr_period': 'bt_atr_period',
                '#bt_multiplier': 'bt_multiplier'
            },
            ExpressionAttributeValues={
                ':val1': str(test_instance.bt_atr_period),
                ':val2': str(test_instance.bt_multiplier)
            }
        )
    except AttributeError as e:
        print(f"Attribute error occurred: {e}")
    except KeyError as e:
        print(f"Key error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    
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
    #     test_instance.find_best_parameters(atr=atr, atr_multiplier=multiplier)
        
    #     update_response = tests_table.update_item(
    #     Key={'id': test_id},
    #     UpdateExpression='SET #bt_atr_period = :val1, #bt_multiplier = :val2',
    #     ExpressionAttributeNames={
    #         '#bt_atr_period': 'bt_atr_period',
    #         "#bt_multiplier": "bt_multiplier" # Use ExpressionAttributeNames to avoid conflicts with reserved words
    #     },
    #     ExpressionAttributeValues={
    #         ':val1': str(test_instance.bt_atr_period),
    #         ':val2': str(test_instance.bt_multiplier)
            
    #     }
    # )
    #     if update_response['ResponseMetadata']['HTTPStatusCode'] != 200:
    #         # Call the method from the class instance
    #         return jsonify({"error": "Failed to update DynamoDB"}), 500
            

    #     # Prepare the response data
    #     response_data = {
    #         "ATR Period": str(test_instance.bt_atr_period),
    #         "Multiplier": str(test_instance.bt_multiplier),
    #         # "ROI": str(test_instance.find_best_temp_roi)
    #     }

    #     # Return the response data as JSON
    #     return jsonify(response_data), 200  # HTTP 200 OK
    
        # Start the background task for updating the test instance
        if test_instance.find_best_result_processing == True:
            return jsonify({
            "success": False,
            "message": "The find best parameters has already started. Please wait for the current task to finish."
        }), 403
        
        thread = Thread(target=start_find_best_process, args=(test_id, test_instance, atr, multiplier ))
        thread.start()
        setattr(test_instance, "find_best_parameters_processing", True)

        # Return an immediate response indicating that processing has started
        return jsonify({
            "success": True,
            "message": "The find best parameters has been started."
        }), 202

    except Exception as e:
        # Log the error for debugging
        app.logger.error(f"An error occurred: {str(e)}")

        # Return a JSON response with the error message and a server error status code
        return jsonify({'error': 'An error occurred while processing your request.'}), 500  # HTTP 500 Internal Server Error

@app.route("/get_find_best_parameters_progress_percentage", methods=["POST"])
def get_find_best_parameters_progress_percentage():
    test_id = request.json.get("test_id")
    if test_id is None:
        return jsonify({"error": "Missing test_id"}), 400

    test_instance_data = next(
        (inst for inst in test_instances if inst["test_id"] == test_id), None)
    if test_instance_data is None:
        return jsonify({"error": "Test instance not found"}), 400
    
    # Start the background task for updating the test instance
    test_instance = test_instance_data["test_instance"] 
    if test_instance.find_best_result_processing == False:
        return jsonify({"processing":False, 
                    "percentage": None,
                    "elapsed_time":None, 
                    "estimated_remaining_time":None,
                    "current_atr" : test_instance.bt_atr_period,
                    "current_multiplier" : test_instance.bt_multiplier,
                    "message": "No find best parameters is currently running. Please start find best parameters first."}), 202
        
    # if test_instance.find_best_result_processing == False and test_instance.find_best_state == "Best":
    #     jsonify({"processing":False, 
    #                 "percentage": None,
    #                 "elapsed_time":None, 
    #                 "estimated_remaining_time":None,
    #                 "message": "Find best parameters is already complete. No find best parameters is currently running. Please start the find best parameters again."}), 403
            
    processing = test_instance.find_best_result_processing
    if processing:
        percentage = test_instance.find_best_getting_result_progress_percentage
        elapsed_time = test_instance.find_best_elapsed_time
        estimated_remaining_time = test_instance.find_best_estimated_remaining_time
        if elapsed_time and estimated_remaining_time : 
            if elapsed_time > 0 and estimated_remaining_time > 0 : 
                # Return an immediate response
                return jsonify({"processing":True, 
                                "percentage": percentage, 
                                "elapsed_time":elapsed_time, 
                                "estimated_remaining_time":estimated_remaining_time, 
                                "current_atr" : None,
                                "current_multiplier" : None,
                                "message": "The find best parameters is calculating"}), 200
    else:
        return jsonify({"processing":False, 
                        "state":0, 
                        "percentage": None,
                        "elapsed_time":None, 
                        "estimated_remaining_time":None,
                        "message": "The forward test result have not been started yet."}), 206
    
@app.route('/edit_test', methods=['POST'])
def edit_test():
    try:
        data = request.get_json()
        test_id = data.get('test_id')
        
        if not test_id:
            return jsonify({
                    "success": False,
                    "test_id" : test_id,
                    "message": "Missing test id"
                    }), 400
            
        # Check all fields for None values
        # for key, value in data.items():
        #     if value is None:
        #         abort(400, description=f"{key} cannot be None")
        
        if not data["bt_lot_size"] and not data["bt_initial_investment"]:
            return jsonify({
                    "success": False,
                    "test_id" : test_id,
                    "message": "Please input lot size or initial investment"
                    }), 400
        if data["bt_lot_size"] and data["bt_initial_investment"]:
            return jsonify({
                    "success": False,
                    "test_id" : test_id,
                    "message": "You can only input lot size or initial investment"
                    }), 400
        
        if data["bt_lot_size"] :
            if float(data["bt_lot_size"]) < 0.01 or float(data["bt_lot_size"]) > 10000:
                return jsonify({
                    "success": False,
                    "test_id" : test_id,
                    "message": "Lot size must not less than 0.01 or more then 10000"
                    }), 400
                
        if data["bt_initial_investment"]:
            if int(data["bt_initial_investment"]) < 100:
                return jsonify({
                    "success": False,
                    "test_id" : test_id,
                    "message": "Initial Investment must not less than 100"
                    }), 400
                
        # Convert specified fields from str to int
        integer_fields = ['bt_sl_size', 'bt_tp_size', 'bt_commission']
        for field in integer_fields:
            if field in data and data[field].isdigit():  # Checks if the field is a digit string
                data[field] = int(data[field])
            elif field in data:  # If present but not a digit string, return an error
                return jsonify({
                    "success": False,
                    "test_id" : test_id,
                    "message": f"Invalid value for '{field}'. Expected a numeric string."
                    }), 400
                
        field = 'bt_initial_investment'
        if field in data:
            if data[field] :
                try:
                    # Try to convert to float
                    data[field] = int(data[field])
                except ValueError:
                    # If conversion fails, return an error
                    return jsonify({
                        "success": False,
                        "test_id": test_id,
                        "message": f"Invalid value for '{field}'. Expected a numeric string."
                    }), 400
                
        field = 'bt_lot_size'
        if field in data:
            if data[field] :
                try:
                    # Try to convert to float
                    data[field] = float(data[field])
                except ValueError:
                    # If conversion fails, return an error
                    return jsonify({
                        "success": False,
                        "test_id": test_id,
                        "message": f"Invalid value for '{field}'. Expected a numeric string."
                    }), 400
                
        data = {
            "test_id": data.get('test_id'),
            "bt_atr_period": data.get('bt_atr_period'),
            "bt_multiplier": data.get('bt_multiplier'),
            "bt_start_date": data.get('bt_start_date'),
            "bt_end_date": data.get('bt_end_date'),
            "bt_2nd_start_date": data.get('bt_2nd_start_date'),
            "bt_2nd_end_date": data.get('bt_2nd_end_date'),
            "validation_period": data.get('validation_period'),
            "bt_time_frame_backward": data.get('bt_time_frame_backward'),
            "bt_initial_investment": data.get('bt_initial_investment'),
            "bt_lot_size": data.get('bt_lot_size'),
            "bt_sl_size": data.get('bt_sl_size'),
            "bt_tp_size": data.get('bt_tp_size'),
            "bt_commission": data.get('bt_commission')
        }
                
        

        response = tests_table.get_item(Key={'id': test_id})
        if 'Item' not in response:
            return jsonify({
                    "success": False,
                    "test_id" : test_id,
                    "message": "Test instance not found in DynamoDB"
                    }), 400
            
        # Find the test instance in the global list by test_id
        test_instance_data = next(
            (inst for inst in test_instances if inst["test_id"] == test_id), None)
        
        # If the test instance is not found, return an error
        if test_instance_data is None:
            return jsonify({
                    "success": False,
                    "test_id" : test_id,
                    "message": "Test instance not found"
                    }), 400
        
        # Retrieve the test_instance from the stored data
        test_instance = test_instance_data["test_instance"]

        original_item = response['Item']
        if 'test_end_date' in original_item or original_item.get('state') != "Created":
            return jsonify({
                "success": False,
                "test_id" : test_id,
                "message": "Test cannot be edited as it has ended or is already running"
                }), 400
            
        lot_size = None
        initial_investment = None
            
        if data["bt_lot_size"]:   
            lot_size = float(data["bt_lot_size"])
        if data["bt_initial_investment"]:     
            initial_investment = int(data["bt_initial_investment"])
        yf_bt_start_date = datetime.strptime(data["bt_start_date"], "%Y-%m-%d")    
        symbol_price = get_stock_price_on_date(test_instance.bt_symbol, yf_bt_start_date)
        rounded_lots = None
        rounded_initial_investment = None
        
        print('initial_investment: ', initial_investment)
        if  initial_investment:
            new_lot_size = initial_investment / symbol_price
            rounded_lots = round_down_to_appropriate(new_lot_size)
            rounded_initial_investment = initial_investment
            print('rounded_initial_investment: ', rounded_initial_investment)
            print('rounded_lots: ', rounded_lots)
            
        if  lot_size:
            new_initial_investment = lot_size * symbol_price
            rounded_initial_investment = round_up_to_appropriate(new_initial_investment)
            rounded_lots = lot_size
            print('rounded_initial_investment: ', rounded_initial_investment)
            print('rounded_lots: ', rounded_lots) 
            

        test_instance.bt_atr_period= data.get('bt_atr_period')
        test_instance.bt_multiplier= data.get('bt_multiplier')
        test_instance.bt_start_date= data.get('bt_start_date')
        test_instance.bt_end_date= data.get('bt_end_date')
        test_instance.bt_2nd_start_date= data.get('bt_2nd_start_date')
        test_instance.bt_2nd_end_date= data.get('bt_2nd_end_date')
        test_instance.validation_period= data.get('validation_period')
        test_instance.bt_time_frame_backward= data.get('bt_time_frame_backward')
        test_instance.bt_initial_investment= str(rounded_initial_investment)
        test_instance.bt_lot_size= rounded_lots
        test_instance.bt_sl_size= data.get('bt_sl_size')
        test_instance.bt_tp_size= data.get('bt_tp_size')
        test_instance.bt_commission= data.get('bt_commission') 
        test_instance.ft_time_frame_forward = time_frame_exchange[data['bt_time_frame_backward']]
        test_instance.ft_initial_investment = str(rounded_initial_investment)
        test_instance.ft_lot_size = rounded_lots
        test_instance.ft_sl_size = data.get('bt_sl_size')
        test_instance.ft_tp_size = data.get('bt_tp_size')
        
        

        update_response = tests_table.update_item(
            Key={'id': test_id},
            UpdateExpression=(
                'SET #bt_start_date = :bt_start_date, '
                '#bt_end_date = :bt_end_date, '
                '#bt_2nd_start_date = :bt_2nd_start_date, '
                '#bt_2nd_end_date = :bt_2nd_end_date, '
                '#validation_period = :validation_period, '
                '#bt_atr_period = :bt_atr_period, '
                '#bt_multiplier = :bt_multiplier, '
                '#bt_time_frame_backward = :bt_time_frame_backward, '
                '#bt_initial_investment = :bt_initial_investment, '
                '#bt_lot_size = :bt_lot_size, '
                '#bt_sl_size = :bt_sl_size, '
                '#bt_tp_size = :bt_tp_size, '
                '#bt_commission = :bt_commission, '
                '#ft_time_frame_forward = :ft_time_frame_forward, '
                '#ft_initial_investment = :ft_initial_investment, '
                '#ft_lot_size = :ft_lot_size, '
                '#ft_sl_size = :ft_sl_size, '
                '#ft_tp_size = :ft_tp_size'
            ),
            ExpressionAttributeNames={
                '#bt_start_date': 'bt_start_date',
                '#bt_end_date': 'bt_end_date',
                '#bt_2nd_start_date': 'bt_2nd_start_date',
                '#bt_2nd_end_date': 'bt_2nd_end_date',
                '#validation_period': 'validation_period',
                '#bt_atr_period': 'bt_atr_period',
                '#bt_multiplier': 'bt_multiplier',
                '#bt_time_frame_backward': 'bt_time_frame_backward',
                '#bt_initial_investment': 'bt_initial_investment',
                '#bt_lot_size': 'bt_lot_size',
                '#bt_sl_size': 'bt_sl_size',
                '#bt_tp_size': 'bt_tp_size',
                '#bt_commission': 'bt_commission',
                '#ft_time_frame_forward': 'ft_time_frame_forward',
                '#ft_initial_investment': 'ft_initial_investment',
                '#ft_lot_size': 'ft_lot_size',
                '#ft_sl_size': 'ft_sl_size',
                '#ft_tp_size': 'ft_tp_size'
            },
            ExpressionAttributeValues={
                ':bt_start_date': test_instance.bt_start_date,
                ':bt_end_date': test_instance.bt_end_date,
                ':bt_2nd_start_date': test_instance.bt_2nd_start_date,
                ':bt_2nd_end_date': test_instance.bt_2nd_end_date,
                ':validation_period': str(test_instance.validation_period),
                ':bt_atr_period': str(test_instance.bt_atr_period),
                ':bt_multiplier': str(test_instance.bt_multiplier),
                ':bt_time_frame_backward': str(test_instance.bt_time_frame_backward),
                ':bt_initial_investment': str(test_instance.bt_initial_investment),
                ':bt_lot_size': str(test_instance.bt_lot_size),
                ':bt_sl_size': str(test_instance.bt_sl_size),
                ':bt_tp_size': str(test_instance.bt_tp_size),
                ':bt_commission': str(test_instance.bt_commission),
                ':ft_time_frame_forward': str(test_instance.ft_time_frame_forward),
                ':ft_initial_investment': str(rounded_initial_investment),
                ':ft_lot_size': str(rounded_lots),
                ':ft_sl_size': str(test_instance.bt_sl_size),
                ':ft_tp_size': str(test_instance.bt_tp_size)
            }
        )
        if update_response['ResponseMetadata']['HTTPStatusCode'] != 200:
            return jsonify({
                "success": False,
                "test_id" : test_id,
                "message": "Failed to update DynamoDB"
                }), 400
            
        test_instance.parse_and_convert_parameters() 
        test_instance.fetch_stock_price_and_volume()
        
        s3Key_stock_close_price = test_instance.s3Key_stock_close_price
        save_dict_to_s3(s3_bucket_name, test_instance.stock_close_price, s3Key_stock_close_price)
        
        s3Key_stock_volume = test_instance.s3Key_stock_volume
        save_dict_to_s3(s3_bucket_name, test_instance.stock_volume, s3Key_stock_volume)

        return jsonify({
            "success": True,
            "test_id" : test_id,
            "message": "Test parameters updated successfully"
            }), 200

    except Exception as e:
        return jsonify({
                "success": False,
                "test_id" : test_id,
                "message": str(e)
                }), 500
    
@app.route("/start_forward_test", methods=["POST"])
def start_test():
    try:
        # Extract test_id from the request data
        test_id = request.json.get("test_id")
        # user = request.json.get("user")  # Assuming user is also sent in the request

        if test_id is None:
            return jsonify({"error": "Missing test_id"}), 400

        # Query DynamoDB to find the item based on test_id
        try:
            response = tests_table.get_item(Key={'id': test_id})
        except Exception as e:
            return jsonify({"error": "Error querying DynamoDB", "details": str(e)}), 500

        if 'Item' not in response:
            return jsonify({"error": "Test instance not found in DynamoDB"}), 404

        item = response['Item']

        # Check if the end_date key exists or if the test is already active
        if 'test_end_date' in item or (item.get('state') == "Running"):
            return jsonify({"error": "Test cannot be started as it has already running or ended"}), 403

        try:
            # Find the test instance in the global list by test_id
            test_instance_data = next(
                (inst for inst in test_instances if inst["test_id"] == test_id), None)
        except Exception as e:
            return jsonify({"error": "Error finding test instance", "details": str(e)}), 500

        # If the test instance is not found, return an error
        if test_instance_data is None:
            return jsonify({"error": "Test instance not found"}), 400

        # Retrieve the test_instance from the stored data
        test_instance = test_instance_data["test_instance"]
        
        if test_instance.bt_atr_period is None or test_instance.bt_multiplier is None:
            return jsonify({"error": "Please define ATR period and Multiplier"}), 400
        
        tg_channel_id = test_instance.tg_channel_id
        tg_invite_link = test_instance.tg_invite_link
        
        try:
            # tg_invite_link = loop.run_until_complete(generate_invite_link(client, tg_channel_id))
            if tg_channel_id == None and test_instance.tg_enable:
                result = loop.run_until_complete(create_tg_channel(client, f'Invest Trend - {test_instance.test_name} (id#{test_instance.test_id})'))
                tg_channel_id = test_instance.tg_channel_id = result
            
                # loop.run_until_complete(add_user_to_channel(client, tg_channel_id, test_instance.tg_username))
        except Exception as e:
            print(f"An error occurred: {e}")
        try:    
            if tg_channel_id:
                    tg_invite_link = loop.run_until_complete(generate_invite_link(client, int(tg_channel_id)))
        except Exception as e:
            print(f"An error occurred: {e}")


        # Update the item in DynamoDB to set active to True and add the current start_time
        try:
            # Define the Hong Kong timezone
            hong_kong = pytz.timezone('Asia/Hong_Kong')
            current_time = datetime.now().replace(tzinfo=pytz.utc)
            hong_kong_time = current_time.astimezone(hong_kong)
            formatted_time = hong_kong_time.strftime('%Y-%m-%d')  # ISO 8601 format in UTC
            
    
            
            
            update_response = tests_table.update_item(
                Key={'id': test_id},
                UpdateExpression='SET #state = :val1, #ft_start_date = :val2, #tg_channel_id = :val3, #tg_invite_link = :val4',
                ExpressionAttributeNames={
                    '#state': 'state',
                    '#ft_start_date': "ft_start_date",
                    '#tg_channel_id': "tg_channel_id",
                    '#tg_invite_link': "tg_invite_link",# Use ExpressionAttributeNames to avoid conflicts with reserved words
                },
                ExpressionAttributeValues={
                    ':val1': "Running",
                    ':val2': formatted_time,
                    ':val3': str(tg_channel_id),
                    ':val4': str(tg_invite_link)
                }
            )
        except Exception as e:
            return jsonify({"error": "Error updating DynamoDB", "details": str(e)}), 500

        if update_response['ResponseMetadata']['HTTPStatusCode'] == 200:
            try:
                # Start the test using a function from the 'full' module
                full.start_forward_test_thread(test_instance,client)
                test_instance.edit_parameters(
                    {"state": "Running", "ft_start_date": datetime.strptime(formatted_time, '%Y-%m-%d'),"tg_invite_link":tg_invite_link}
                )  # Uncomment this line if you have the full module
            except Exception as e:
                # test_instance.delete_test_channel()
                return jsonify({"error": "Error starting forward test thread", "details": str(e)}), 500

        # Check if the update was successful
        if update_response['ResponseMetadata']['HTTPStatusCode'] != 200:
            test_instance.delete_test_channel()
            return jsonify({"error": "Failed to update DynamoDB"}), 500

        # Return a success message indicating the test has started
        return jsonify({"message": "Test started and DynamoDB updated",
                        'tg_invite_link':str(tg_invite_link)})
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500


@app.route("/stop_forward_test", methods=["POST"])
def stop_test():
    try:
        # Extract test_id from the request data
        test_id = request.json.get("test_id")
        if test_id is None:
            return jsonify({"error": "Missing test_id"}), 400

        # Query DynamoDB to find the item based on test_id
        try:
            response = tests_table.get_item(Key={'id': test_id})
        except Exception as e:
            return jsonify({"error": "Error querying DynamoDB", "details": str(e)}), 500

        if 'Item' not in response:
            return jsonify({"error": "Test instance not found"}), 404

        try:
            # Find the test instance in the global list by test_id
            test_instance_data = next(
                (inst for inst in test_instances if inst["test_id"] == test_id), None)
        except Exception as e:
            return jsonify({"error": "Error finding test instance", "details": str(e)}), 500

        # If the test instance is not found, return an error
        if test_instance_data is None:
            return jsonify({"error": "Test instance not found"}), 400

        # Retrieve the test_instance from the stored data
        test_instance = test_instance_data["test_instance"]

        try:
            # Stop the test using a function from the 'full' module
            full.stop_forward_test_thread(test_instance)
        except Exception as e:
            return jsonify({"error": "Error stopping forward test thread", "details": str(e)}), 500

        # Define the Hong Kong timezone
        hong_kong = pytz.timezone('Asia/Hong_Kong')

        try:
            # Update the item in DynamoDB to set active to False and add the current end_time
            current_time = datetime.now().replace(tzinfo=pytz.utc) + timedelta(days=1)
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
        except Exception as e:
            return jsonify({"error": "Error updating DynamoDB", "details": str(e)}), 500

        if update_response['ResponseMetadata']['HTTPStatusCode'] == 200:
            try:
                # Stop the test using a function from the 'full' module
                full.stop_forward_test_thread(test_instance)
                test_instance.edit_parameters(
                    {"state": "End", "stop_flag_live_trade": True, "ft_end_date": datetime.strptime(formatted_time, '%Y-%m-%d')}
                )  # Uncomment this line if you have the full module
            except Exception as e:
                return jsonify({"error": "Error stopping forward test thread", "details": str(e)}), 500
        else:
            return jsonify({"error": "Failed to update DynamoDB"}), 500

        # Return a success message indicating the test has stopped
        return jsonify({"message": "Test stopped and DynamoDB updated"})
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500


@app.route("/get_test_instances", methods=["POST"])
def get_test_instances():
    try:
        # Extract test_id from the request JSON data
        test_id = request.json.get("test_id")
        if test_id is None:
            return jsonify({"error": "Missing test_id"}), 400

        # Perform the get_item operation to retrieve the item from the table
        response = tests_table.get_item(Key={'id': test_id})
        item = response.get('Item')

        if not item:
            return jsonify({"error": "Test instance not found"}), 404

        # Convert all Decimal instances to float for JSON serialization
        for key, value in item.items():
            if isinstance(value, Decimal):
                item[key] = decimal_default(value)

        # Return the test instance as JSON
        return jsonify(item), 200

    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@app.route("/get_in_memory_test_instances", methods=["POST"])
def get_in_memory_test_instances():
    try:
        # Extract test_id from the request data
        test_id = request.json.get("test_id")
        if test_id is None:
            return jsonify({"error": "Missing test_id"}), 400

        try:
            # Find the test instance in the global list by test_id
            test_instance_data = next(
                (inst for inst in test_instances if inst["test_id"] == test_id), None)
        except Exception as e:
            return jsonify({"error": "Error finding test instance", "details": str(e)}), 500

        # If the test instance is not found, return an error
        if test_instance_data is None:
            return jsonify({"error": "Test instance not found"}), 404

        # Retrieve the test_instance from the stored data
        test_instance = test_instance_data["test_instance"]

        try:
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
        except Exception as e:
            return jsonify({"error": "Error processing test instance data", "details": str(e)}), 500

        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500


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
    test_instance.parse_and_convert_parameters()

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
    """
    This function handles requests to get the forward test result.
    It initiates a background task to process the test result if conditions are met.
    """
    try:
        # Retrieve the test_id from the request body
        test_id = request.json.get("test_id")
        
        if test_id is None:
            return jsonify({"error": "Missing test_id"}), 400

        # Find the test instance data in the test_instances list
        test_instance_data = next(
            (inst for inst in test_instances if inst["test_id"] == test_id), None)
        
        if test_instance_data is None:
            return jsonify({"error": "Test instance not found"}), 400

        # Retrieve the test_instance from the stored data
        test_instance = test_instance_data["test_instance"]

        # Check the state of the test instance
        if test_instance.state == "Created":
            return jsonify({
                "success": False,
                "message": "No forward test has been run or is currently running. Please start the forward test first."
            }), 403
            
        # Check the state of the test instance
        if test_instance.ft_result_processing :
            return jsonify({
                "success": False,
                "message": "The get forward test result has already started. Please wait for the current task to finish."
            }), 403

        # Get the current time in Hong Kong timezone
        hong_kong = pytz.timezone('Asia/Hong_Kong')
        current_time = datetime.now().replace(tzinfo=pytz.utc)
        print('current_time type: ', type(current_time))
        hong_kong_time = current_time.astimezone(hong_kong)
        formatted_time = hong_kong_time.strftime('%Y-%m-%d')

        print('formatted_time:', formatted_time)
        print('test_instance.ft_start_date:', test_instance.ft_start_date)
        print('test_instance.ft_start_date == formatted_time:', test_instance.ft_start_date == formatted_time)

        # Uncomment and modify the following lines if you need to compare the start date with the current date
        # datetime_obj = datetime.strptime(test_instance.ft_start_date, "%Y-%m-%d %H:%M:%S")
        # test_instance_date_only = test_instance.ft_start_date.strftime("%Y-%m-%d")
        # if test_instance_date_only == formatted_time:
        #     return jsonify({"error": "Cannot get the result on the forward test start date."}), 400

        # Start the background task for updating the test instance
        thread = Thread(target=update_test_instance, args=(test_id, test_instance))
        thread.start()
        setattr(test_instance, "ft_result_processing", True)

        # Return an immediate response indicating that processing has started
        return jsonify({
            "success": True,
            "message": "Test result processing has been started."
        }), 202

    except Exception as e:
        # Log the exception
        print(f"Error in get_test_result: {e}")

        # Return a generic error message
        return jsonify({"error": "An unexpected error occurred."}), 500

@app.route("/get_forward_test_progress_percentage", methods=["POST"])
def get_forward_test_progress_percentage():
    # Get the test ID from the request JSON
    test_id = request.json.get("test_id")
    if test_id is None:
        # Return an error if the test ID is missing
        return jsonify({"error": "Missing test_id"}), 400

    # Find the test instance data based on the test ID
    test_instance_data = next(
        (inst for inst in test_instances if inst["test_id"] == test_id), None)
    if test_instance_data is None:
        # Return an error if the test instance is not found
        return jsonify({"error": "Test instance not found"}), 400

    # Get the test instance object
    test_instance = test_instance_data["test_instance"]

    # Check if the test instance is in the "Created" state
    if test_instance.state == "Created":
        # Return an error if the forward test has not been started
        return jsonify({"processing":False, 
                        "state":0, 
                        "percentage": None,
                        "elapsed_time":None, 
                        "estimated_remaining_time":None,
                        "message": "No forward test have been run or are currently running. Please start the forward test first."}), 403

    # Check if the test instance is processing the forward test result
    processing = test_instance.ft_result_processing
    if processing:
        # Get the progress percentage, elapsed time, and estimated remaining time
        percentage = test_instance.ft_getting_result_progress_percentage
        elapsed_time = test_instance.elapsed_time
        estimated_remaining_time = test_instance.estimated_remaining_time

        # Check if the elapsed time and estimated remaining time are available
        if elapsed_time and estimated_remaining_time : 
            if elapsed_time > 0 and estimated_remaining_time > 0 : 
                # Return the progress percentage and other details if the test is calculating
                return jsonify({"processing":True, 
                                "state":2, 
                                "percentage": percentage, 
                                "elapsed_time":elapsed_time, 
                                "estimated_remaining_time":estimated_remaining_time, 
                                "message": "The forward test result is calculating"}), 200
        else :
            # Return the progress percentage and other details if the test is downloading
            return jsonify({"processing":True, 
                            "state":1, 
                            "percentage": percentage, 
                            "elapsed_time":elapsed_time, 
                            "estimated_remaining_time":estimated_remaining_time, 
                            "message": "The forward test result is downloading"}), 202

    # Return a default response if the test instance is not processing
    return jsonify({"processing":False, 
                    "state":0, 
                    "percentage": None,
                    "elapsed_time":None, 
                    "estimated_remaining_time":None,
                    "message": "The forward test result have not been started yet."}), 206

    

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
    limit = request.json.get("limit")
    start_date = request.json.get("start_date")
    end_date = request.json.get("end_date")
    symbol = request.json.get("symbol")
    impact_above = request.json.get("impact_above")
    impact_below = request.json.get("impact_below")
    
    table_name = 'InvestNews-ambqia6vxrcgzfv4zl44ahmlp4-dev'
    table = dynamodb.Table(table_name)
    
    if test_id is None:
        return jsonify({"error": "Missing test_id"}), 400
    
    if limit is not None and (not isinstance(limit, int) or limit <= 0):
        return jsonify({"error": "The limit value is invalid - the limit must be an integer and <= 0"}), 400
    
    if start_date is not None:
        if not isinstance(start_date, str) or not re.match(r"\d{4}-\d{2}-\d{2}", start_date):
            return jsonify({"error": "Invalid start_date format - format must be YYYY-MM-DD"}), 400

    if end_date is not None:
        if not isinstance(end_date, str) or not re.match(r"\d{4}-\d{2}-\d{2}", end_date):
            return jsonify({"error": "Invalid end_date format - format must be YYYY-MM-DD"}), 400
    
        
    if impact_above is not None:
        if not isinstance(impact_above, int):
            return jsonify({"error": "Invalid impact_above value - it must be an integer"}), 400

    if impact_below is not None:
        if not isinstance(impact_below, int):
            return jsonify({"error": "Invalid impact_below value - it must be an integer"}), 400
        
    if impact_above and impact_below:
        if impact_above < 0 or impact_below > 0:
            return jsonify({"error": "Invalid values for impact_above or impact_below - it must be an integer"}), 400
    
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
        impact_below = -50
    if limit == None:
        limit = 10
    
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
                if item['headline_impact'] >= impact_above or item['headline_impact'] <= impact_below
            ]
        
        # Prepend to ensure latest items are kept if we exceed 10
        last_items = filtered_items + last_items
        last_items = last_items[-(limit):]  # Keep only the last 10 items

        if 'LastEvaluatedKey' not in response or len(last_items) >= limit:
            break
        exclusive_start_key = response['LastEvaluatedKey']
        
    for item in last_items:
        for key, value in item.items():
            if isinstance(value, Decimal):
                item[key] = decimal_default(value)
        
    # Sorting the items by 'date_time' from latest to earliest
    sorted_items = sorted(last_items, key=lambda x: datetime.strptime(x['date_time'], '%Y-%m-%dT%H:%M:%SZ'), reverse=True)

    # Return an immediate response
    return jsonify(sorted_items), 200

@app.route("/get_multiple_ai_analyze_news", methods=["POST"])
def get_analyze_news_combine():
    test_id = request.json.get("test_id")
    limit = request.json.get("limit")
    start_date = request.json.get("start_date")
    end_date = request.json.get("end_date")
    symbol = request.json.get("symbol")
    impact_above = request.json.get("impact_above")
    impact_below = request.json.get("impact_below")
    
    table_name = 'InvestNewsMix-ambqia6vxrcgzfv4zl44ahmlp4-dev'
    table = dynamodb.Table(table_name)
    
    if test_id is None:
        return jsonify({"error": "Missing test_id"}), 400
    
        # Validate limit
    if not isinstance(limit, int) or limit <= 0:
        return jsonify({"error": "The limit must be a positive integer"}), 400
    
    # Define regex patterns
    date_pattern = r"\d{4}-\d{2}-\d{2}"

    # Validate date formats
    if start_date:
        if not isinstance(start_date, str) or not re.match(date_pattern, start_date):
            return jsonify({"error": "Invalid start_date format - format must be YYYY-MM-DD"}), 400

    if end_date:
        if not isinstance(end_date, str) or not re.match(date_pattern, end_date):
            return jsonify({"error": "Invalid end_date format - format must be YYYY-MM-DD"}), 400
        
    if impact_above is not None:
        if not isinstance(impact_above, int):
            return jsonify({"error": "Invalid impact_above value - it must be an integer"}), 400

    if impact_below is not None:
        if not isinstance(impact_below, int):
            return jsonify({"error": "Invalid impact_below value - it must be an integer"}), 400
        
    if impact_above and impact_below:
        if impact_above < 0 or impact_below > 0:
            return jsonify({"error": "Invalid values for impact_above or impact_below - it must be an integer"}), 400
    
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
        impact_above = 80 
    if impact_below == None:
        impact_below = -70
    if limit == None:
        limit = 1000
    
    # news_results = analyze_news_gemini_request(symbol, start_date, end_date, limit)
    
    # Paginate through the results manually to find the last 10 items
    last_items = []
    exclusive_start_key = None

    while True:
        scan_kwargs = {
    'FilterExpression': Attr('date_time').between(start_date, end_date) &
                        Attr('ticker_symbol').contains(symbol) &
                        (Attr('body_impact_overall').gte(impact_above) | 
                         Attr('body_impact_overall').lte(impact_below))
}
        
        # Only add ExclusiveStartKey to arguments if it's not None
        if exclusive_start_key:
            scan_kwargs['ExclusiveStartKey'] = exclusive_start_key

        response = table.scan(**scan_kwargs)
        
        items = response.get('Items', [])
        # print('items: ', len(items))
        
        filtered_items = [
                item for item in items 
                if item['body_impact_overall'] >= impact_above or item['body_impact_overall'] <= impact_below
            ]
        
        # Prepend to ensure latest items are kept if we exceed 10
        last_items = filtered_items + last_items
        last_items = last_items[-(limit):]  # Keep only the last 10 items

        if 'LastEvaluatedKey' not in response or len(last_items) >= limit:
            break
        exclusive_start_key = response['LastEvaluatedKey']
        
    for item in last_items:
        for key, value in item.items():
            if isinstance(value, Decimal):
                item[key] = decimal_default(value)
        
    # Sorting the items by 'date_time' from latest to earliest
    sorted_items = sorted(last_items, key=lambda x: datetime.strptime(x['date_time'], '%Y-%m-%dT%H:%M:%SZ'), reverse=True)
    # sorted_items = sorted_items[-(limit):] 
    print('sorted_items: ', len(sorted_items))

    # Return an immediate response
    return jsonify(sorted_items), 200 

# @app.route("/get_multiple_ai_analyze_news_test", methods=["POST"])
# def get_analyze_news_combine_test():
#     data = request.json
#     test_id = data.get("test_id")
#     limit = data.get("limit")
#     start_date = data.get("start_date")
#     end_date = data.get("end_date", datetime.now().strftime("%Y-%m-%d"))
#     symbol = data.get("symbol")
#     impact_above = data.get("impact_above", 50)
#     impact_below = data.get("impact_below", -50)
    
#     table_name = 'InvestNewsMix-ambqia6vxrcgzfv4zl44ahmlp4-dev'
#     table = dynamodb.Table(table_name)
    
#     # Validate input parameters
#     if not test_id:
#         return jsonify({"error": "Missing test_id"}), 400
    
#     if not limit:
#         limit = 30
    
#     if not isinstance(limit, int) or limit <= 0:
#         return jsonify({"error": "The limit value is invalid - the limit must be a positive integer"}), 400
    
#     date_pattern = r"\d{4}-\d{2}-\d{2}"
#     if start_date and not re.match(date_pattern, start_date):
#         return jsonify({"error": "Invalid start_date format - format must be YYYY-MM-DD"}), 400

#     if not re.match(date_pattern, end_date):
#         return jsonify({"error": "Invalid end_date format - format must be YYYY-MM-DD"}), 400

#     if not isinstance(impact_above, int) or not isinstance(impact_below, int):
#         return jsonify({"error": "Invalid impact_above or impact_below value - it must be an integer"}), 400
    
#     if impact_above < 0 or impact_below > 0:
#         return jsonify({"error": "Invalid values for impact_above or impact_below - it must be an integer"}), 400
    
#     # Retrieve test instance data
#     test_instance_data = next((inst for inst in test_instances if inst["test_id"] == test_id), None)
#     if not test_instance_data:
#         return jsonify({"error": "Test instance not found"}), 400
    
#     test_instance = test_instance_data["test_instance"]
    
#     # Use default values from test instance if not provided
#     symbol = symbol or getattr(test_instance, "ft_symbol")
#     start_date = start_date or getattr(test_instance, "bt_start_date").strftime("%Y-%m-%d")
    
#     # Fetch news results from DynamoDB
#     scan_kwargs = {
#         'FilterExpression': Attr('date_time').between(start_date, end_date) &
#                             Attr('ticker_symbol').contains(symbol) &
#                             Attr('body_impact_overall').gte(impact_above) 
#     }
#     scan_kwargs2 = {
#         'FilterExpression': Attr('date_time').between(start_date, end_date) &
#                             Attr('ticker_symbol').contains(symbol) &
#                             Attr('body_impact_overall').lte(impact_below)
#     }

#     response = table.scan(**scan_kwargs)
#     response2 = table.scan(**scan_kwargs2)
#     items = response.get('Items', [])
#     items2 = response2.get('Items', [])

#     # Combine items from both responses
#     combined_items = items + items2
    
#     # Convert Decimal to float
#     for item in combined_items:
#         for key, value in item.items():
#             if isinstance(value, Decimal):
#                 item[key] = float(value)

#     # Sort and limit the items
#     sorted_items = sorted(combined_items, key=lambda x: datetime.strptime(x['date_time'], '%Y-%m-%dT%H:%M:%SZ'), reverse=True)
#     limited_items = sorted_items[:limit]

#     return jsonify(limited_items), 200
    
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
            
        for item in items:
            for key, value in item.items():
                if isinstance(value, Decimal):
                    item[key] = decimal_default(value)
            
        sorted_items = sorted(items, key=lambda x: datetime.strptime(x['create_time'], '%Y-%m-%dT%H:%M:%SZ'), reverse=True)

        return jsonify(sorted_items), 200

    except ClientError as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/gemini', methods=['POST'])
def gemini():
    """
    This endpoint interacts with the Google Generative Language API (Gemini).
    It sends a POST request with the provided JSON data and returns the API response.
    """
    data = request.json
    
    # Retrieve the Google API key from environment variables
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    if not GOOGLE_API_KEY:
        return jsonify({"error": "The Google API key is missing or not set in the environment variables"}), 500

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GOOGLE_API_KEY}"

    headers = {
        'Content-Type': 'application/json'
    }

    try:
        # Send the request to the Google Generative Language API
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Raise an exception for HTTP errors
    except requests.exceptions.RequestException as e:
        # Log the error and return a JSON response with the error message
        app.logger.error(f"Request to Google API failed: {e}")
        return jsonify({"error": "Failed to contact the Google Generative Language API"}), 500

    # Return the JSON response from the Google API
    return response.json()



def get_tests_id_by_state(index_name, states):

    test_ids = []
    try:
        # Iterate over the states and perform a separate query for each
        for state in states:
            response = tests_table.query(
                IndexName=index_name,
                KeyConditionExpression=Key('state').eq(state)
            )

            # Extract test_ids from the items
            if 'Items' in response:
                for item in response['Items']:
                    if 'test_id' in item:  # Make sure 'test_id' exists in the item
                        test_ids.append(item['test_id'])

                # Handle the potential for paginated results
                while 'LastEvaluatedKey' in response:
                    response = tests_table.query(
                        IndexName=index_name,
                        KeyConditionExpression=Key('state').eq(state),
                        ExclusiveStartKey=response['LastEvaluatedKey']
                    )
                    for item in response['Items']:
                        if 'test_id' in item:  # Make sure 'test_id' exists in the item
                            test_ids.append(item['test_id'])

    except ClientError as e:
        print(e.response['Error']['Message'])
        return None  # Return None or appropriate error handling
    except Exception as e:
        print(str(e))
        return None  # Return None or appropriate error handling
    
    return test_ids  # Return the list of test IDs
    
    
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
            if 's3Key_backtest_data' in test_instance_data:
                bt_key = test_instance_data['s3Key_backtest_data']
                bt_data = get_json_data_from_s3(s3_bucket_name,bt_key)
                test.edit_parameters(bt_data)

                
            if 's3Key_stock_close_price' in test_instance_data:
                price_key = test_instance_data['s3Key_stock_close_price']
                price_data = get_json_data_from_s3(s3_bucket_name,price_key)
                test.edit_parameters({'stock_close_price':price_data})
                
            if 's3Key_stock_volume' in test_instance_data:
                volume_key = test_instance_data['s3Key_stock_volume']
                volume_data = get_json_data_from_s3(s3_bucket_name,volume_key)
                test.edit_parameters({'stock_volume':volume_data})
            
            if 's3Key_forward_test_data' in test_instance_data:
                ft_key = test_instance_data['s3Key_forward_test_data']
                ft_data = get_json_data_from_s3(s3_bucket_name,ft_key)
                test.edit_parameters(ft_data)
                
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
            full.start_forward_test_thread(inst["test_instance"],client)
            # print(inst)
            
            
# Define a set of colors and a dictionary to map emotions to colors
colors = list(mcolors.TABLEAU_COLORS.values())
emotion_color_map = {}

@app.route('/tsla-stock-chart', methods=['POST'])
def get_tsla_stock_chart():
    try:
        # Extract start_date, end_date, and dominant_emotion from the POST request
        data = request.json
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        dominant_emotion = data.get('dominant_emotion')
        
        # Validate and parse the dates
        if not start_date or not end_date:
            return jsonify({"error": "Please provide both start_date and end_date"}), 400

        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({"error": "Dates must be in YYYY-MM-DD format"}), 400
        
        # Fetch TSLA stock data using yfinance
        tsla = yf.Ticker("TSLA")
        tesla_data = tsla.history(start=start_date, end=end_date)
        
        # Handle case where no data is returned
        if tesla_data.empty:
            return jsonify({"error": "No data available for the provided date range"}), 404
        
        # Convert tesla_data index to naive datetime
        tesla_data.index = tesla_data.index.tz_localize(None)
        
        # Plotting
        plt.figure(figsize=(14, 7))
        plt.plot(tesla_data.index, tesla_data['Close'], label='Tesla Stock Price')

        # Annotate the graph with dominant emotions using scatter plot
        index_dates = tesla_data.index
        
        youtube_table = dynamodb.Table('invest_trend_youtube_dataV4')
        
        items = []
        if dominant_emotion:
            for emotion in dominant_emotion:
            # Query the DynamoDB table
                response = youtube_table.scan(
                    FilterExpression=Attr('dominant_emotion').eq(emotion) &
                                    Attr('published_at').between(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                )
                item = response['Items']
                items.extend(item)
        else:
             # Query the DynamoDB table
            response = youtube_table.scan(
                FilterExpression=Attr('published_at').between(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            )
            items = response['Items']
        
        # Get the items from the response
        
        
        # Convert published_at to datetime and extract dominant emotions
        for video in items:
            video['published_at'] = datetime.strptime(video['published_at'], '%Y-%m-%dT%H:%M:%SZ')
            if isinstance(video['emotion_analysis'], list) and video['emotion_analysis']:
                emotion_info = video['emotion_analysis'][0]
                if 'dominant_emotion' in emotion_info and 'emotion' in emotion_info:
                    video['dominant_emotion'] = emotion_info['dominant_emotion']
                    video['dominant_emotion_value'] = emotion_info['emotion'][video['dominant_emotion']]
                else:
                    video['dominant_emotion'] = None
                    video['dominant_emotion_value'] = None
            else:
                video['dominant_emotion'] = None
                video['dominant_emotion_value'] = None
                
            if video['dominant_emotion']:
                # Find the closest available date
                target_date = video['published_at']
                closest_index = index_dates.get_indexer([target_date], method='nearest')[0]
                closest_date = index_dates[closest_index]
                closest_price = tesla_data.loc[closest_date]['Close']
                
                # Assign a color to the dominant emotion if not already assigned
                if video['dominant_emotion'] not in emotion_color_map:
                    emotion_color_map[video['dominant_emotion']] = colors[len(emotion_color_map) % len(colors)]
                
                # Scatter plot for dominant emotions
                plt.scatter(
                    closest_date, 
                    video['dominant_emotion_value'], 
                    label=video['dominant_emotion'], 
                    color=emotion_color_map[video['dominant_emotion']]
                )
        
        plt.xlabel('Date')
        plt.ylabel('Stock Price / Emotion Analysis Value')
        plt.title('Tesla Stock Price and Dominant Emotions from Video Data')
        
        # Create a custom legend to avoid duplicate labels
        handles, labels = plt.gca().get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        plt.legend(by_label.values(), by_label.keys())

        plt.grid(True)
        
        # Save the plot to a BytesIO object
        img_io = BytesIO()
        plt.savefig(img_io, format='png')
        img_io.seek(0)
        plt.close()
        
        # Send the image as a response
        return send_file(img_io, mimetype='image/png')
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    # try:
    
        # Create the client and connect 
        client = TelegramClient('test01', api_id, api_hash)
        # telegram_event_loop = None
        client.start(phone)
        states_to_query = ['Created', 'Running', 'End']
        # delete_tests_by_state('state-index', states_to_query, test_instances)
        created_and_running_tests = get_tests_by_state('state-index', states_to_query, test_instances)
        get_running_instances_and_run()
        
        app.run(host="0.0.0.0", port=8000,debug=False, use_reloader=False)
    
    # finally:
    #     client.disconnect()
    # app.run(port=8000,debug=False, use_reloader=False)
 


