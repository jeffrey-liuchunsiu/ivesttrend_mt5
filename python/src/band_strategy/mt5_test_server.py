from flask import Flask, request, jsonify
from flask_socketio import SocketIO
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store connected clients
connected_clients = set()

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    connected_clients.add(request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")
    connected_clients.remove(request.sid)

@app.route('/place_order', methods=['POST'])
def place_order():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['symbol', 'type', 'volume', 'sl', 'tp']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Format the order message for MT5
        order_message = f"{data['symbol']},{data['type']},{data['volume']},{data['sl']},{data['tp']}"

        # Send the order to all connected MT5 clients
        if not connected_clients:
            return jsonify({'error': 'No MT5 clients connected'}), 503

        socketio.emit('order', order_message, broadcast=True)
        
        return jsonify({
            'status': 'success',
            'message': 'Order sent to MT5',
            'order_details': data
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Optional: Endpoint to check server status
@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        'status': 'online',
        'connected_clients': len(connected_clients)
    })

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)