import asyncio
import websockets
import logging
from quart import Quart, request, jsonify
import json
import uuid
import base64
import hashlib

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Quart(__name__)
clients = {}

def calculate_accept_key(key):
    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    accept = key + GUID
    accept_sha1 = hashlib.sha1(accept.encode()).digest()
    return base64.b64encode(accept_sha1).decode()

async def handle_client(websocket, path):
    client_id = str(uuid.uuid4())
    clients[client_id] = websocket
    logger.info(f"New client connected: {client_id}")
    
    try:
        await websocket.send("CONNECTION_ESTABLISHED")
        
        while True:
            try:
                message = await websocket.recv()
                logger.debug(f"Received from {client_id}: {message}")
                
                if message == "HEARTBEAT":
                    await websocket.send("HEARTBEAT")
                    logger.debug(f"Sent heartbeat response to {client_id}")
                
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"Error handling message from {client_id}: {str(e)}")
                break
    finally:
        if client_id in clients:
            del clients[client_id]
        logger.info(f"Client disconnected: {client_id}")

@app.route('/place_order', methods=['POST'])
async def place_order():
    try:
        order = await request.get_json()
        logger.debug(f"Received order: {order}")
        
        order_message = f"{order['symbol']},{order['type']},{order['volume']},{order['sl']},{order['tp']}\n"
        logger.debug(f"Formatted order message: {order_message}")
        
        for client_id, websocket in list(clients.items()):
            try:
                await websocket.send(order_message)
                logger.debug(f"Sent order to {client_id}")
            except Exception as e:
                logger.error(f"Error sending to {client_id}: {str(e)}")
                if client_id in clients:
                    del clients[client_id]
        
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error in place_order: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/list_clients', methods=['GET'])
async def list_clients():
    return jsonify({"clients": list(clients.keys())})

async def start_websocket_server():
    async with websockets.serve(
        handle_client,
        "0.0.0.0",
        5000,
        ping_interval=20,
        ping_timeout=60,
        compression=None
    ):
        await asyncio.Future()

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