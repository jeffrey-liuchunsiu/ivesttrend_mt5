from flask import Flask, request, jsonify
import socket
import threading
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global variables
connected_clients = {}
server_socket = None

def start_socket_server():
    global server_socket
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', 5000))
        server_socket.listen(5)
        logger.info("Socket server started on port 5000")

        while True:
            client_socket, address = server_socket.accept()
            client_id = f"{address[0]}:{address[1]}"
            connected_clients[client_id] = {
                'socket': client_socket,
                'address': address,
                'connected_at': datetime.now()
            }
            logger.info(f"New client connected: {client_id}")
            
            # Start a thread to handle client messages
            threading.Thread(target=handle_client, args=(client_socket, client_id)).start()

    except Exception as e:
        logger.error(f"Socket server error: {str(e)}")
        if server_socket:
            server_socket.close()

def handle_client(client_socket, client_id):
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            logger.info(f"Received from {client_id}: {data.decode()}")
    except:
        pass
    finally:
        client_socket.close()
        if client_id in connected_clients:
            del connected_clients[client_id]
        logger.info(f"Client disconnected: {client_id}")

@app.route('/place_order', methods=['POST'])
def place_order():
    try:
        data = request.get_json()
        logger.info(f"Received order request: {data}")

        # Validate required fields
        required_fields = ['symbol', 'type', 'volume', 'sl', 'tp']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Format the order message
        order_message = f"{data['symbol']},{data['type']},{data['volume']},{data['sl']},{data['tp']}\n"

        # Check for connected clients
        if not connected_clients:
            logger.warning("No MT5 clients connected")
            return jsonify({'error': 'No MT5 clients connected'}), 503

        # Send the order to all connected clients
        for client_id, client_data in list(connected_clients.items()):
            try:
                client_data['socket'].send(order_message.encode())
                logger.info(f"Order sent to client {client_id}")
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {str(e)}")
                client_data['socket'].close()
                del connected_clients[client_id]

        return jsonify({
            'status': 'success',
            'message': 'Order sent to MT5',
            'order_details': data,
            'clients_count': len(connected_clients)
        })

    except Exception as e:
        logger.error(f"Error processing order: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        'status': 'online',
        'connected_clients': len(connected_clients),
        'client_details': {
            client_id: {
                'address': f"{client_data['address'][0]}:{client_data['address'][1]}",
                'connected_at': client_data['connected_at'].isoformat()
            }
            for client_id, client_data in connected_clients.items()
        }
    })

if __name__ == '__main__':
    # Start socket server in a separate thread
    threading.Thread(target=start_socket_server, daemon=True).start()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=5001, debug=True)