from flask import Flask, request, jsonify
import socket
import threading
import json
import logging
from datetime import datetime
import time
import signal
import sys
from collections import defaultdict

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
client_positions = defaultdict(dict)  # Store current positions for each client
client_magic_numbers = {"124.244.251.186":123456}  # Store custom magic numbers for clients

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
        logger.info(f"Initialized empty trading history for client {client_id}")
        
    while is_socket_server_running and not should_exit:
        try:
            data = client_socket.recv(1024)
            if not data:
                break
                
            message = data.decode()
            logger.info(f"Received from {client_id}: {message}")
            
            if message.startswith("CONNECTION_ESTABLISHED"):
                logger.info(f"Client {client_id} established connection")
                # History update should follow shortly
                
            # Handle history update messages
            elif message.startswith("HISTORY_UPDATE:"):
                history = parse_history_message(message.replace("HISTORY_UPDATE:", ""))
                if history:
                    trading_history[client_id] = history
                    logger.info("\n=== Received Trade History Update ===")
                    logger.info(f"Client: {client_id}")
                    logger.info(f"Total Trades: {len(history)}")
                    for trade in history:
                        logger.info(f"Trade: {trade}")
                    logger.info("=== End History Update ===\n")
                    
                    # After receiving history, print all trades
                    load_and_print_all_trades()
                else:
                    logger.warning(f"Received empty history update from {client_id}")
                
            # Handle trade execution messages
            elif message.startswith("TRADE_EXECUTED:"):
                trade_details = parse_trade_message(message.replace("TRADE_EXECUTED:", ""))
                trade_details['timestamp'] = datetime.now().isoformat()
                trading_history[client_id].append(trade_details)
                logger.info(f"\nNew Trade Executed:")
                logger.info(f"  Symbol: {trade_details.get('symbol')}")
                logger.info(f"  Type: {trade_details.get('type')}")
                logger.info(f"  Volume: {trade_details.get('volume')}")
                logger.info(f"  Price: {trade_details.get('price')}")
                logger.info(f"  Magic: {trade_details.get('magic')}")
                logger.info(f"  Time: {trade_details.get('timestamp')}\n")
                
        except Exception as e:
            logger.error(f"Error handling client message: {str(e)}")
            break

def parse_trade_message(message):
    """Parse trade execution message into dictionary"""
    parts = message.split(',')
    trade_dict = {}
    for part in parts:
        key, value = part.split('=')
        trade_dict[key.strip()] = value.strip()
    return trade_dict

def parse_positions_message(message):
    """Parse positions update message into dictionary"""
    positions = []
    if message:
        position_strings = message.split(';')
        for pos_str in position_strings:
            if pos_str:
                position = {}
                parts = pos_str.split(',')
                for part in parts:
                    key, value = part.split('=')
                    position[key.strip()] = value.strip()
                positions.append(position)
    return positions

def parse_history_message(message):
    """Parse history update message into list of trades"""
    trades = []
    logger.info("Parsing history message...")
    
    if message:
        trade_strings = message.split(';')
        logger.info(f"Found {len(trade_strings)} trade strings")
        
        for trade_str in trade_strings:
            if trade_str:
                try:
                    trade = {}
                    parts = trade_str.split(',')
                    for part in parts:
                        if '=' in part:
                            key, value = part.split('=')
                            trade[key.strip()] = value.strip()
                    if trade:  # Only append if we got valid trade data
                        trades.append(trade)
                        logger.info(f"Parsed trade: {trade}")
                except Exception as e:
                    logger.error(f"Error parsing trade string: {trade_str}")
                    logger.error(f"Error details: {str(e)}")
    
    logger.info(f"Successfully parsed {len(trades)} trades")
    return trades

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
        client_history = trading_history.get(client_id, [])
        magic_number = client_magic_numbers.get(client_id)
        
        return jsonify({
            'client_details': {
                'ip': client_id,
                'full_address': f"{client_data['address'][0]}:{client_data['address'][1]}",
                'connected_at': client_data['connected_at'].isoformat(),
                'connection_status': 'connected',
                'magic_number': magic_number,
                'is_auto_generated': magic_number is None
            },
            'trading_history': client_history,
            'total_trades': len(client_history)
        })
        
    except Exception as e:
        logger.error(f"Error getting client details: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/client/<client_id>/trades', methods=['GET'])
def get_client_trades(client_id):
    try:
        # Get client's trading history
        client_history = trading_history.get(client_id, [])
        
        # Get client's current positions
        current_positions = client_positions.get(client_id, [])
        
        return jsonify({
            'client_id': client_id,
            'trading_history': client_history,
            'current_positions': current_positions,
            'total_trades': len(client_history),
            'total_open_positions': len(current_positions)
        })
        
    except Exception as e:
        logger.error(f"Error getting client trades: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/client/<client_id>/magic', methods=['POST'])
def set_client_magic(client_id):
    try:
        data = request.get_json()
        if 'magic_number' not in data:
            return jsonify({'error': 'magic_number is required'}), 400
            
        magic_number = int(data['magic_number'])
        if magic_number <= 0:
            return jsonify({'error': 'magic_number must be positive'}), 400
            
        client_magic_numbers[client_id] = magic_number
        
        return jsonify({
            'status': 'success',
            'client_id': client_id,
            'magic_number': magic_number
        })
        
    except ValueError:
        return jsonify({'error': 'Invalid magic number format'}), 400
    except Exception as e:
        logger.error(f"Error setting magic number: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/client/<client_id>/magic', methods=['GET'])
def get_client_magic(client_id):
    try:
        magic_number = client_magic_numbers.get(client_id)
        return jsonify({
            'client_id': client_id,
            'magic_number': magic_number,
            'is_auto_generated': magic_number is None
        })
    except Exception as e:
        logger.error(f"Error getting magic number: {str(e)}")
        return jsonify({'error': str(e)}), 500

def cleanup():
    stop_socket_server()
    logger.info("Server shutdown complete")

# Add this function to help with debugging
@app.route('/debug/messages/<client_id>', methods=['GET'])
def get_debug_messages(client_id):
    """Endpoint to help debug message processing"""
    return jsonify({
        'client_id': client_id,
        'positions': client_positions.get(client_id, []),
        'history': trading_history.get(client_id, []),
        'magic_number': client_magic_numbers.get(client_id),
        'is_connected': client_id in connected_clients
    })

# Add this new route for handling MT5 signals
@app.route('/mt5/signal', methods=['POST'])
def handle_mt5_signal():
    try:
        # Log the raw request data and headers
        raw_data = request.get_data(as_text=True)
        logger.info(f"Received raw data: {raw_data}")
        logger.info(f"Content-Type: {request.headers.get('Content-Type')}")
        logger.info(f"All Headers: {dict(request.headers)}")

        # First try to get the data as-is
        try:
            data = request.get_json(force=True)  # force=True will try to parse even if content-type is not application/json
        except Exception as json_error:
            logger.error(f"Initial JSON parsing error: {str(json_error)}")
            
            # Clean up the data
            try:
                # Remove any whitespace
                cleaned_data = raw_data.strip()
                
                # Log the cleaning process
                logger.info(f"Cleaning data. Original length: {len(raw_data)}")
                logger.info(f"First 100 chars: {raw_data[:100]}")
                logger.info(f"Last 100 chars: {raw_data[-100:] if len(raw_data) > 100 else raw_data}")
                
                # Check for and remove BOM if present
                if cleaned_data.startswith('\ufeff'):
                    cleaned_data = cleaned_data[1:]
                
                # Remove any trailing commas before the last }
                if cleaned_data.rstrip().endswith(',}'):
                    cleaned_data = cleaned_data.rstrip()[:-2] + '}'
                
                # Ensure proper JSON structure
                if not cleaned_data.startswith('{'):
                    cleaned_data = '{' + cleaned_data
                if not cleaned_data.endswith('}'):
                    cleaned_data = cleaned_data + '}'
                
                logger.info(f"Cleaned data: {cleaned_data}")
                
                # Try to parse the cleaned data
                data = json.loads(cleaned_data)
                
            except Exception as clean_error:
                logger.error(f"Failed to clean and parse JSON: {str(clean_error)}")
                # Try to parse as key-value pairs
                try:
                    pairs = raw_data.split(',')
                    data = {}
                    for pair in pairs:
                        if '=' in pair:
                            key, value = pair.split('=', 1)
                            data[key.strip()] = value.strip()
                    logger.info(f"Parsed as key-value pairs: {data}")
                except Exception as kv_error:
                    logger.error(f"Failed to parse as key-value pairs: {str(kv_error)}")
                    return jsonify({
                        'error': 'Invalid data format',
                        'raw_data': raw_data,
                        'message': 'Could not parse data in any format'
                    }), 400

        # Log the successfully parsed data
        logger.info(f"Successfully parsed data: {data}")

        # Process the signal data
        # Add your signal processing logic here
        
        return jsonify({
            'status': 'success',
            'message': 'Signal received and processed',
            'data': data
        })

    except Exception as e:
        logger.error(f"Error processing MT5 signal: {str(e)}")
        return jsonify({
            'error': str(e),
            'raw_data': request.get_data(as_text=True)
        }), 500

# Add this helper endpoint to test the signal processing
@app.route('/test/signal', methods=['POST'])
def test_signal():
    """Endpoint to test signal processing with various formats"""
    try:
        raw_data = request.get_data(as_text=True)
        return jsonify({
            'received_data': raw_data,
            'content_type': request.headers.get('Content-Type'),
            'headers': dict(request.headers),
            'size': len(raw_data)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Update the error handler to provide more information
@app.errorhandler(400)
def bad_request_handler(error):
    logger.error(f"Bad Request: {str(error)}")
    logger.error(f"Request data: {request.get_data(as_text=True)}")
    logger.error(f"Headers: {dict(request.headers)}")
    return jsonify({
        'error': 'Bad Request',
        'message': str(error),
        'raw_data': request.get_data(as_text=True)
    }), 400

# Add these functions after the global variables

def load_and_print_all_trades():
    """Load and print all trades in the system"""
    logger.info("\n=== All Trading History ===")
    all_trades = []
    
    # Collect all trades from all clients
    for client_id, client_trades in trading_history.items():
        logger.info(f"\nClient: {client_id}")
        logger.info(f"Trades: {len(client_trades)}")
        all_trades.extend(client_trades)
    
    # Sort trades by timestamp if available
    try:
        all_trades.sort(key=lambda x: x.get('time', ''), reverse=True)
    except Exception as e:
        logger.error(f"Error sorting trades: {str(e)}")
    
    if all_trades:
        logger.info(f"\nTotal Trades Found: {len(all_trades)}")
        for trade in all_trades:
            logger.info(f"Trade: {trade}")
    else:
        logger.info("\nNo trades found in the system")
    
    logger.info("=== End Trading History ===\n")
    return all_trades

# Add this new endpoint to get all trades
@app.route('/trades', methods=['GET'])
def get_all_trades():
    """Get all trades in the system"""
    try:
        all_trades = load_and_print_all_trades()
        return jsonify({
            'total_trades': len(all_trades),
            'trades': all_trades
        })
    except Exception as e:
        logger.error(f"Error getting all trades: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting trading server...")
    
    # Print all existing trades at startup
    load_and_print_all_trades()
    
    # Start socket server in a separate thread
    socket_thread = threading.Thread(target=start_socket_server, daemon=True)
    socket_thread.start()
    
    try:
        # Start Flask server
        app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        # Print final trade status before shutdown
        load_and_print_all_trades()
    except Exception as e:
        logger.error(f"Flask server error: {str(e)}")
    finally:
        cleanup()