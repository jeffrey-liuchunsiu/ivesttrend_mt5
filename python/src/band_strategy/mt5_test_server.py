import asyncio
import websockets
import logging
from quart import Quart, request, jsonify
import json

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Quart(__name__)
clients = {}

class MT5WebSocket:
    def __init__(self):
        self.clients = {}
        self.lock = asyncio.Lock()

    async def register(self, websocket):
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        async with self.lock:
            self.clients[client_id] = websocket
        return client_id

    async def unregister(self, client_id):
        async with self.lock:
            if client_id in self.clients:
                del self.clients[client_id]

    async def send_to_all(self, message):
        disconnected_clients = []
        for client_id, websocket in self.clients.items():
            try:
                await websocket.send(message)
                logger.debug(f"Sent message to {client_id}: {message}")
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.append(client_id)
            except Exception as e:
                logger.error(f"Error sending to {client_id}: {str(e)}")
                disconnected_clients.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.unregister(client_id)

mt5_websocket = MT5WebSocket()

async def handle_client(websocket, path):
    client_id = await mt5_websocket.register(websocket)
    logger.info(f"New client connected: {client_id}")
    
    try:
        # Send initial connection acknowledgment
        await websocket.send("CONNECTION_ESTABLISHED")
        
        while True:
            try:
                message = await websocket.recv()
                logger.debug(f"Received from {client_id}: {message}")
                
                if message == "HEARTBEAT":
                    await websocket.send("HEARTBEAT")
                    logger.debug(f"Sent heartbeat response to {client_id}")
                elif message.startswith("ORDER_EXECUTED"):
                    logger.info(f"Order execution confirmation from {client_id}: {message}")
                
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"Error handling message from {client_id}: {str(e)}")
                break
                
    finally:
        await mt5_websocket.unregister(client_id)
        logger.info(f"Client disconnected: {client_id}")

@app.route('/place_order', methods=['POST'])
async def place_order():
    try:
        order = await request.get_json()
        logger.debug(f"Received order: {order}")
        
        required_fields = ['symbol', 'type', 'volume', 'sl', 'tp']
        if not all(field in order for field in required_fields):
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
        
        order_message = f"{order['symbol']},{order['type']},{order['volume']},{order['sl']},{order['tp']}\n"
        logger.debug(f"Formatted order message: {order_message}")
        
        await mt5_websocket.send_to_all(order_message)
        return jsonify({"status": "success", "message": "Order sent to all clients"})
        
    except Exception as e:
        logger.error(f"Error processing order: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/test_websocket', methods=['GET'])
async def test_websocket():
    try:
        test_message = "TEST,BUY,0.1,0,0\n"
        logger.debug(f"Sending test message: {test_message}")
        
        await mt5_websocket.send_to_all(test_message)
        return jsonify({"status": "success", "message": "Test message sent"})
        
    except Exception as e:
        logger.error(f"Error sending test message: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/list_clients', methods=['GET'])
async def list_clients():
    return jsonify({
        "status": "success",
        "clients": list(mt5_websocket.clients.keys()),
        "count": len(mt5_websocket.clients)
    })

async def start_websocket_server():
    async with websockets.serve(
        handle_client,
        "0.0.0.0",
        5000,
        ping_interval=20,
        ping_timeout=60
    ):
        await asyncio.Future()  # run forever

@app.before_serving
async def startup():
    app.websocket_task = asyncio.create_task(start_websocket_server())
    logger.info("WebSocket server started")

@app.after_serving
async def shutdown():
    app.websocket_task.cancel()
    try:
        await app.websocket_task
    except asyncio.CancelledError:
        pass
    logger.info("WebSocket server stopped")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)