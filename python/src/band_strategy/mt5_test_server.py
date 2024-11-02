import asyncio
import websockets
import logging
from flask import Flask, request, jsonify
import json
from quart import Quart
from functools import wraps

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Quart(__name__)  # Changed from Flask to Quart
clients = {}

async def handle_client(websocket, path):
    client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    logger.debug(f"New WebSocket connection from {client_id}")
    clients[client_id] = websocket
    
    try:
        while True:
            message = await websocket.recv()
            logger.debug(f"Received from {client_id}: {message}")
            
            if message == "HEARTBEAT":
                await websocket.send("HEARTBEAT")
                logger.debug(f"Sent heartbeat response to {client_id}")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: {client_id}")
    finally:
        if client_id in clients:
            del clients[client_id]

@app.route('/place_order', methods=['POST'])
async def place_order():
    order = await request.get_json()
    logger.debug(f"Received order: {order}")
    
    order_message = f"{order['symbol']},{order['type']},{order['volume']},{order['sl']},{order['tp']}\n"
    logger.debug(f"Formatted order message: {order_message}")
    
    for client_id, websocket in clients.items():
        try:
            logger.debug(f"Attempting to send order to client {client_id}")
            await websocket.send(order_message)
            logger.debug(f"Successfully sent order to client {client_id}")
        except Exception as e:
            logger.error(f"Error sending order to {client_id}: {str(e)}")
    
    return jsonify({"status": "success"})

@app.route('/test_websocket', methods=['GET'])
async def test_websocket():
    test_message = "TEST,BUY,0.1,0,0\n"
    logger.debug(f"Sending test message: {test_message}")
    
    for client_id, websocket in clients.items():
        try:
            await websocket.send(test_message)
            logger.debug(f"Test message sent to {client_id}")
        except Exception as e:
            logger.error(f"Error sending test message to {client_id}: {str(e)}")
    
    return jsonify({"status": "test message sent"})

@app.route('/list_clients', methods=['GET'])
async def list_clients():
    return jsonify({"clients": list(clients.keys())})

async def start_websocket_server():
    server = await websockets.serve(handle_client, "0.0.0.0", 5000)
    await server.wait_closed()

@app.before_serving
async def startup():
    app.websocket_task = asyncio.create_task(start_websocket_server())

@app.after_serving
async def shutdown():
    app.websocket_task.cancel()
    try:
        await app.websocket_task
    except asyncio.CancelledError:
        pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)