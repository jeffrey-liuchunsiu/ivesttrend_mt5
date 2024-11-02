import asyncio
import websockets
import logging
from quart import Quart, request, jsonify
import json
import uuid
import base64
import hashlib
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Quart(__name__)

@dataclass
class Client:
    websocket: websockets.WebSocketServerProtocol
    last_heartbeat: datetime

class ClientManager:
    def __init__(self):
        self.clients: Dict[str, Client] = {}
        
    def add_client(self, websocket: websockets.WebSocketServerProtocol) -> str:
        client_id = str(uuid.uuid4())
        self.clients[client_id] = Client(
            websocket=websocket,
            last_heartbeat=datetime.now()
        )
        return client_id
    
    def remove_client(self, client_id: str) -> None:
        self.clients.pop(client_id, None)
    
    def update_heartbeat(self, client_id: str) -> None:
        if client := self.clients.get(client_id):
            client.last_heartbeat = datetime.now()
    
    def get_stale_clients(self, timeout: int = 70) -> list:
        now = datetime.now()
        return [
            client_id for client_id, client in self.clients.items()
            if (now - client.last_heartbeat).seconds > timeout
        ]

client_manager = ClientManager()

def validate_order(order: dict) -> bool:
    required_fields = {'symbol', 'type', 'volume', 'sl', 'tp'}
    if not all(field in order for field in required_fields):
        return False
    
    try:
        float(order['volume'])
        float(order['sl'])
        float(order['tp'])
        return True
    except (ValueError, TypeError):
        return False

async def handle_client(websocket: websockets.WebSocketServerProtocol, path: str):
    client_id = client_manager.add_client(websocket)
    logger.info(f"New client connected: {client_id}")
    
    try:
        await websocket.send(json.dumps({
            "type": "connection",
            "status": "established",
            "client_id": client_id
        }))
        
        while True:
            try:
                message = await websocket.recv()
                logger.debug(f"Received from {client_id}: {message}")
                
                if message == "HEARTBEAT":
                    client_manager.update_heartbeat(client_id)
                    await websocket.send(json.dumps({
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat()
                    }))
                    logger.debug(f"Sent heartbeat response to {client_id}")
                
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"Error handling message from {client_id}: {str(e)}")
                break
    finally:
        client_manager.remove_client(client_id)
        logger.info(f"Client disconnected: {client_id}")

@app.route('/place_order', methods=['POST'])
async def place_order():
    try:
        order = await request.get_json()
        logger.debug(f"Received order: {order}")
        
        if not validate_order(order):
            return jsonify({
                "status": "error",
                "message": "Invalid order format"
            }), 400
        
        order_message = json.dumps({
            "type": "order",
            "data": {
                "symbol": order['symbol'],
                "order_type": order['type'],
                "volume": float(order['volume']),
                "sl": float(order['sl']),
                "tp": float(order['tp']),
                "timestamp": datetime.now().isoformat()
            }
        })
        
        for client_id, client in list(client_manager.clients.items()):
            try:
                await client.websocket.send(order_message)
                logger.debug(f"Sent order to {client_id}")
            except Exception as e:
                logger.error(f"Error sending to {client_id}: {str(e)}")
                client_manager.remove_client(client_id)
        
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error in place_order: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/list_clients', methods=['GET'])
async def list_clients():
    return jsonify({
        "clients": list(client_manager.clients.keys()),
        "count": len(client_manager.clients)
    })

async def cleanup_stale_clients():
    while True:
        try:
            stale_clients = client_manager.get_stale_clients()
            for client_id in stale_clients:
                logger.info(f"Removing stale client: {client_id}")
                client_manager.remove_client(client_id)
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Error in cleanup task: {str(e)}")
            await asyncio.sleep(5)

async def start_websocket_server():
    cleanup_task = asyncio.create_task(cleanup_stale_clients())
    async with websockets.serve(
        handle_client,
        "0.0.0.0",
        5000,
        ping_interval=20,
        ping_timeout=60,
        compression=None
    ):
        try:
            await asyncio.Future()
        finally:
            cleanup_task.cancel()

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