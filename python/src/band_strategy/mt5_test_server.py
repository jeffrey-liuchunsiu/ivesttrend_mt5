from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import MetaTrader5 as mt5
import json

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize MT5 connection
def init_mt5():
    if not mt5.initialize():
        print("MT5 initialization failed")
        return False
    return True

@app.route('/order', methods=['POST'])
def place_order():
    try:
        data = request.json
        # Emit the order data to MT5 client via WebSocket
        socketio.emit('new_order', data)
        return jsonify({"status": "success", "message": "Order sent to MT5"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('order_status')
def handle_order_status(data):
    print(f"Order status received: {data}")
    # You can broadcast this to other connected clients if needed
    emit('order_update', data, broadcast=True)

if __name__ == '__main__':
    if init_mt5():
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    else:
        print("Failed to start server due to MT5 initialization error")