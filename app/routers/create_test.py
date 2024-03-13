from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional
from fastapi.encoders import jsonable_encoder
from utils.test_id_exists import test_id_exists, test_id_exists_in_memory

import utils.full_bot_process_mac as full
import os
from dotenv import find_dotenv, load_dotenv
import boto3

from boto3 import resource
from boto3.dynamodb.conditions import Key
import pytz 
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

import json
from mt5linux import MetaTrader5
from schedule import Scheduler
import shortuuid
from threading import Thread
from datetime import date


from test_instance_dependencies import get_test_instances  # Import from dependencies.py

mt5 = MetaTrader5(
    # host = 'localhost',
    host = '18.141.245.200',
    port = 18812      
)  

# Load environment variables from .env file

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

load_dotenv(find_dotenv())

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

router = APIRouter()

class TradingStrategy(BaseModel):
    test_strategy_name: str
    strategy_type: str
    test_name: str
    user: str
    bt_symbol: str
    bt_atr_period: str
    bt_multiplier: str
    bt_start_date: str
    bt_end_date: str
    bt_2nd_start_date: str
    bt_2nd_end_date: str
    bt_time_frame_backward: str
    bt_initial_investment: str
    bt_lot_size: str
    bt_sl_size: str
    bt_tp_size: str
    bt_commission: str
    ft_symbol: str
    ft_start_date: Optional[str] = None
    ft_end_date: Optional[str] = None
    ft_time_frame_forward: str
    ft_initial_investment: str
    ft_lot_size: str
    ft_sl_size: str
    ft_tp_size: str

def create_test_instance(data,uuid_id):
    """Create and return a new test instance from request data."""
    try:
        return full.Test(
            test_strategy_name=data["test_strategy_name"],
            strategy_type=data["strategy_type"],
            test_id=uuid_id,
            test_name=data["test_name"],
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

def save_test_instance(table, instance, user, uuid_id):
    """Save a test instance to the provided DynamoDB table."""
    try:
        current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
       
        update_response = table.put_item(Item={
            'id': uuid_id,
            'test_id': uuid_id,
            "test_name": instance.test_name,
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
            'stock_close_price': instance.stock_close_price,
            'stock_volume': instance.stock_volume,
            'create_time': current_time,
            'state': "Created"
        })
        return update_response
    except Exception as e:
        print(f"An error occurred while saving the test instance: {str(e)}")
        
@router.post('/create_test')
async def create_test(tradingStrategy:TradingStrategy, test_instances=Depends(get_test_instances)):
    try:
        # Parse request data using Pydantic model for validation
        # json_str = tradingStrategy.model_dump_json()
        data = jsonable_encoder(tradingStrategy)

        # data = json.loads(json_str)
        user = data["user"]
        uuid_id = shortuuid.uuid()[:16]

        # Validate required fields
        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing 'user' field")

        # Check if test_id already exists and generate new uuid
        while test_id_exists(tests_table, uuid_id) or test_id_exists_in_memory(test_instances, uuid_id):
            uuid_id = shortuuid.uuid()[:16]

        # Create test instance
        test_instance = create_test_instance(data, uuid_id)
        if test_instance is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid test instance data")

        test_instance.fetch_stock_price_and_volume()
        update_response = save_test_instance(tests_table, test_instance, user, uuid_id)
        if update_response['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save in DynamoDB")

        test_instance.parse_and_convert_parameters()
        test_instances.append({"test_id": uuid_id, "test_instance": test_instance})

        return {
            "test_id": uuid_id,
            "message": "Test instance created successfully and saved in DynamoDB"
        }

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# @app.get("/items/{item_id}")
# def read_item(item_id: int, q: Union[str, None] = None):
#     return {"item_id": item_id, "q": q}