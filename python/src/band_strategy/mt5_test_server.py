from flask import Flask, request, jsonify
import socket
import threading
import json
import logging
from datetime import datetime
import time
import signal
import sys

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
socket_thread = None
is_socket_server_running = False
trading_history = {}  # Store trading history for each client
should_exit = False  # Flag to control graceful shutdown

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global should_exit, is_socket_server_running
    logger.info("Shutting down gracefully...")
    should_exit = True
    is_socket_server_running = False
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def start_socket_server():
    global server_socket, is_socket_server_running
    
    while not should_exit:  # Keep trying to start the server
        try:
            # Check if socket server is already running
            if is_socket_server_running:
                time.sleep(5)  # Wait before retry
                continue
                
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('0.0.0.0', 5000))
            server_socket.listen(5)
            is_socket_server_running = True
            logger.info("Socket server started on port 5000")

            while is_socket_server_running and not should_exit:
                try:
                    client_socket, address = server_socket.accept()
                    client_id = address[0]
                    
                    if client_id in connected_clients:
                        try:
                            old_socket = connected_clients[client_id]['socket']
                            old_socket.close()
                        except:
                            pass
                    
                    connected_clients[client_id] = {
                        'socket': client_socket,
                        'address': address,
                        'connected_at': datetime.now()
                    }
                    logger.info(f"New client connected: {client_id}")
                    
                    # Start a thread to handle client messages
                    client_thread = threading.Thread(target=handle_client, args=(client_socket, client_id))
                    client_thread.daemon = True
                    client_thread.start()
                except Exception as e:
                    logger.error(f"Error accepting client connection: {str(e)}")
                    time.sleep(1)  # Wait before retrying
                    continue

        except Exception as e:
            logger.error(f"Socket server error: {str(e)}")
            is_socket_server_running = False
            if server_socket:
                try:
                    server_socket.close()
                except:
                    pass
            time.sleep(5)  # Wait before attempting to restart
        finally:
            if server_socket:
                try:
                    server_socket.close()
                except:
                    pass
            is_socket_server_running = False

def stop_socket_server():
    global server_socket, is_socket_server_running
    is_socket_server_running = False
    
    # Close all client connections
    for client_id, client_data in list(connected_clients.items()):
        try:
            client_data['socket'].close()
        except:
            pass
    connected_clients.clear()
    
    # Close server socket
    if server_socket:
        try:
            server_socket.close()
        except:
            pass
        server_socket = None
    
    logger.info("Socket server stopped")

def handle_client(client_socket, client_id):
    if client_id not in trading_history:
        trading_history[client_id] = []
        
    while is_socket_server_running and not should_exit:
        try:
            data = client_socket.recv(1024)
            if not data:
                break
                
            message = data.decode()
            logger.info(f"Received from {client_id}: {message}")
            
            # Store trade execution responses
            if message.startswith("TRADE_EXECUTED:"):
                trade_details = message.replace("TRADE_EXECUTED:", "").strip()
                trading_history[client_id].append({
                    'timestamp': datetime.now().isoformat(),
                    'details': trade_details
                })
                
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {str(e)}")
            break
    
    try:
        client_socket.close()
    except:
        pass
        
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
                try:
                    client_data['socket'].close()
                except:
                    pass
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
        'socket_server_running': is_socket_server_running,
        'connected_clients': len(connected_clients),
        'client_details': {
            client_id: {
                'ip': client_id,
                'full_address': f"{client_data['address'][0]}:{client_data['address'][1]}",
                'connected_at': client_data['connected_at'].isoformat()
            }
            for client_id, client_data in connected_clients.items()
        }
    })

@app.route('/client/<client_id>', methods=['GET'])
def get_client_details(client_id):
    try:
        # Check if client exists
        if client_id not in connected_clients:
            return jsonify({
                'error': 'Client not found',
                'message': f'No active client with ID: {client_id}'
            }), 404
            
        client_data = connected_clients[client_id]
        
        # Get client's trading history
        client_history = trading_history.get(client_id, [])
        
        return jsonify({
            'client_details': {
                'ip': client_id,
                'full_address': f"{client_data['address'][0]}:{client_data['address'][1]}",
                'connected_at': client_data['connected_at'].isoformat(),
                'connection_status': 'connected'
            },
            'trading_history': client_history,
            'total_trades': len(client_history)
        })
        
    except Exception as e:
        logger.error(f"Error getting client details: {str(e)}")
        return jsonify({'error': str(e)}), 500

def cleanup():
    stop_socket_server()
    logger.info("Server shutdown complete")

if __name__ == '__main__':
    # Start socket server in a separate thread
    socket_thread = threading.Thread(target=start_socket_server, daemon=True)
    socket_thread.start()
    
    try:
        # Start Flask server
        app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Flask server error: {str(e)}")
    finally:
        cleanup()