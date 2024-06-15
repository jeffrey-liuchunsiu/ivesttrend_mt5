# -*- coding: utf-8 -*-
"""
Created on Fri Oct  7 16:58:34 2022

@author: Victor Lee
"""

from mt5linux import MetaTrader5
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import time
import schedule
import pytz
import yfinance as yf
import json
import asyncio
import os
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal
from collections import namedtuple
from dotenv import load_dotenv,find_dotenv
load_dotenv(find_dotenv())

mt5 = MetaTrader5(
    host='18.141.245.200',
    port=18812
)

mt5_username = os.getenv('mt5_username')
mt5_password = os.getenv('mt5_password')

# Path to MetaTrader 5 terminal
path = "/home/ubuntu/.wine/drive_c/Program Files/Pepperstone MetaTrader 5/terminal64.exe"
server = 'Pepperstone-Demo'
username = mt5_username
password = mt5_password

deviation = 10

aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
region_name = os.getenv('AWS_REGION')

dynamodb = boto3.resource('dynamodb', 
                          aws_access_key_id=aws_access_key_id, 
                          aws_secret_access_key=aws_secret_access_key, 
                          region_name=region_name)

# table = dynamodb.Table('test_by_users-dev')
# tests_table = dynamodb.Table('TestInstance-hj4kjln2cvcg5cjw6tik2b2grq-dev')
table = dynamodb.Table('investtrend_mt5_history_deals')

# Function to start Meta Trader 5 (MT5)
def start_mt5():
    uname = int(username)  # Username must be an int
    pword = str(password)  # Password must be a string
    trading_server = str(server)  # Server must be a string
    filepath = str(path)  # Filepath must be a string

    if mt5.initialize(login=uname, password=pword, server=trading_server, path=filepath):
        if mt5.login(login=uname, password=pword, server=trading_server):
            print("Login good")
            return True
        else:
            print("Login Fail")
            return PermissionError
    else:
        print("MT5 Initialization Failed")
        return ConnectionAbortedError

# Initialize connection to MT5
def connect():
    mt5.initialize()

# Start MT5 and print account info
# start_mt5()
# print(mt5.account_info())

timezone = pytz.timezone("Asia/Hong_Kong")

# Function to fetch deals in chunks of 10 days
def fetch_deals_in_chunks(start_date, end_date, chunk_size_days=0.1):
    start_mt5()
    print(mt5.account_info())
    all_deals = []
    current_start_date = start_date
    
    while current_start_date < end_date:
        
        current_end_date = current_start_date + timedelta(days=chunk_size_days)
        # print('current_start_date: ', current_start_date)
        # print('current_end_date: ', current_end_date)
        if current_end_date > end_date:
            current_end_date = end_date
            # print('current_end_date: ', current_end_date)
        
        utc_from_timestamp = current_start_date.timestamp()
        date_to_timestamp = current_end_date.timestamp()
        
        history_deals = mt5.history_deals_get(utc_from_timestamp, date_to_timestamp, group="BTCUSD")
        if history_deals is not None:
            all_deals.extend(history_deals)
            for history_deal in history_deals:
                # print(history_deal.ticket)
                # Put deal into DynamoDB
                put_deal_into_dynamodb(history_deal)
        
        current_start_date = current_end_date
        print("fetch_deals_in_chunks Done")
    
    return tuple(all_deals)

# Function to store a trade deal into DynamoDB
def put_deal_into_dynamodb(deal):
    # Convert float values to Decimal
    def decimalize(value):
        if isinstance(value, float):
            return Decimal(str(value))
        return value

    # Check if the ticket already exists
    response = table.get_item(
        Key={
            'ticket': deal.ticket
        }
    )
    
    if 'Item' in response:
        print(f"Deal with ticket {deal.ticket} already exists.")
    else:
        # Insert the deal into DynamoDB
        table.put_item(
            Item={
                'ticket': deal.ticket,
                'order': deal.order,
                'time': deal.time,
                'time_msc': deal.time_msc,
                'type': deal.type,
                'entry': deal.entry,
                'magic': deal.magic,
                'position_id': deal.position_id,
                'reason': deal.reason,
                'volume': decimalize(deal.volume),
                'price': decimalize(deal.price),
                'commission': decimalize(deal.commission),
                'swap': decimalize(deal.swap),
                'profit': decimalize(deal.profit),
                'fee': decimalize(deal.fee),
                'symbol': deal.symbol,
                'comment': deal.comment,
                'external_id': deal.external_id
            }
        )
        print(f"Deal with ticket {deal.ticket} has been added to DynamoDB.")


def get_trade_deal_from_db_by_magic(magic_value,table_name="investtrend_mt5_history_deals", index_name='magic-index'):
    # Initialize a session using Amazon DynamoDB
    dynamodb = boto3.resource('dynamodb', 
                          aws_access_key_id=aws_access_key_id, 
                          aws_secret_access_key=aws_secret_access_key, 
                          region_name=region_name)
    
    # Select your DynamoDB table
    table = dynamodb.Table(table_name)
    
    # Perform the query operation
    response = table.query(
        IndexName=index_name,
        KeyConditionExpression=Key('magic').eq(magic_value)
    )
    
    # Extract the items from the response
    items = response.get('Items', [])
    
    # Define the TradeDeal class using namedtuple for simplicity
    TradeDeal = namedtuple('TradeDeal', [
        'ticket', 'order', 'time', 'time_msc', 'type', 'entry', 'magic',
        'position_id', 'reason', 'volume', 'price', 'commission', 'swap',
        'profit', 'fee', 'symbol', 'comment', 'external_id'
    ])
    
    # Convert items to TradeDeal instances
    trade_deals = []
    for item in items:
        trade_deal = TradeDeal(
            ticket=int(item['ticket']),
            order=int(item['order']),
            time=int(item['time']),
            time_msc=int(item['time_msc']),
            type=int(item['type']),
            entry=int(item['entry']),
            magic=int(item['magic']),
            position_id=int(item['position_id']),
            reason=int(item['reason']),
            volume=float(item['volume']),
            price=float(item['price']),
            commission=float(item['commission']),
            swap=float(item['swap']),
            profit=float(item['profit']),
            fee=float(item['fee']),
            symbol=item['symbol'],
            comment=item['comment'],
            external_id=item['external_id']
        )
        trade_deals.append(trade_deal)
    
    # Convert the list to a tuple and return
    return tuple(trade_deals)

# Example usage
if __name__ == "__main__":
    table_name = 'investtrend_mt5_history_deals'
    index_name = 'magic-index'
    magic_value = 7  # Replace with your actual partition key value
    
    # Calculate the start date for fetching historical deals
    utc_from = datetime.now(tz=timezone) - timedelta(days=3)  # Adjust this as needed
    print('utc_from: ', utc_from)

    # Convert utc_from to a timezone-aware datetime object
    utc_from = datetime(utc_from.year, utc_from.month, utc_from.day,
                        hour=utc_from.hour, minute=utc_from.minute, tzinfo=timezone)

    # Get current date and time in Hong Kong timezone
    date_to = datetime.now().astimezone(pytz.timezone("Asia/Hong_Kong"))
    date_to = datetime(date_to.year, date_to.month, date_to.day,
                    hour=date_to.hour, minute=date_to.minute, tzinfo=timezone)

    # Fetch historical deals in chunks of 10 days
    deals=mt5.history_deals_total(utc_from.timestamp(), date_to.timestamp())
    print('deals: ', deals)
    # history_deals = mt5.history_deals_get(utc_from.timestamp(), date_to.timestamp(), group="BTCUSD")

    # history_deals = mt5.history_deals_get(utc_from.timestamp(), date_to.timestamp(), group="BTCUSD")
    # print('history_deals: ', history_deals)
    all_deals = fetch_deals_in_chunks(utc_from, date_to, chunk_size_days=0.5)
    print('all_deals: ', all_deals)
    # result = get_trade_deal_from_db_by_magic(magic_value)
    # print(result)
