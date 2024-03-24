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



# Include your Pydantic models here
class BestParametersRequest(BaseModel):
    test_id: str
    atr: Optional[float] = None
    multiplier: Optional[float] = None

class BestParametersResponse(BaseModel):
    ATR_Period: str
    Multiplier: str
    # ROI: str # Uncomment if you want to include ROI in the response
    
@router.post('/find_best_parameters', response_model=BestParametersResponse, responses={400: {'description': 'Bad Request'}, 404: {'description': 'Not Found'}, 403: {'description': 'Forbidden'}, 500: {'description': 'Internal Server Error'}})
async def find_best_parameters(request: BestParametersRequest,  test_instances=Depends(get_test_instances)):
    try:
        test_id = request.test_id
        atr = request.atr
        multiplier = request.multiplier

        if test_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing test_id or user")

        # Query DynamoDB to find the item based on test_id
        response = tests_table.get_item(Key={'id': test_id})
        if 'Item' not in response:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test instance not found in DynamoDB")

        item = response['Item']

        if 'test_end_date' in item or (item.get('state') != "Created"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Test cannot be started as it has already end or is already running")

        test_instance_data = next(
            (inst for inst in test_instances if inst["test_id"] == test_id), None)

        if test_instance_data is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Test instance not found")
        
        test_instance = test_instance_data["test_instance"]
        
        test_instance.parse_and_convert_parameters()
        test_instance.find_best_parameters(atr=atr, atr_multiplier=multiplier)
        
        update_response = tests_table.update_item(
            Key={'id': test_id},
            UpdateExpression='SET #bt_atr_period = :val1, #bt_multiplier = :val2',
            ExpressionAttributeNames={
                '#bt_atr_period': 'bt_atr_period',
                "#bt_multiplier": "bt_multiplier"  # Use ExpressionAttributeNames to avoid conflicts with reserved words
            },
            ExpressionAttributeValues={
                ':val1': str(test_instance.bt_atr_period),
                ':val2': str(test_instance.bt_multiplier)
            }
        )

        if update_response['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update DynamoDB")
            
        response_data = BestParametersResponse(
            ATR_Period=str(test_instance.bt_atr_period),
            Multiplier=str(test_instance.bt_multiplier),
            # ROI=str(test_instance.bt_first_roi)  # Uncomment if you want to include ROI in the response
        )

        return response_data

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))