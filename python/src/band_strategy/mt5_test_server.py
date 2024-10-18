from flask import Flask, jsonify, request
import threading
import time
import random

app = Flask(__name__)

# Global variable to store the next command
next_command = None
command_lock = threading.Lock()

def generate_random_command():
    """Generate a random trading command."""
    action = random.choice(["BUY", "SELL"])
    symbol = random.choice(["EURUSD", "GBPUSD", "USDJPY"])
    volume = round(random.uniform(0.01, 0.5), 2)
    price = round(random.uniform(1.0, 1.5), 5)
    sl = round(price - random.uniform(0.001, 0.005), 5) if action == "BUY" else round(price + random.uniform(0.001, 0.005), 5)
    tp = round(price + random.uniform(0.001, 0.005), 5) if action == "BUY" else round(price - random.uniform(0.001, 0.005), 5)
    
    return {
        "action": action,
        "symbol": symbol,
        "volume": volume,
        "price": price,
        "sl": sl,
        "tp": tp
    }

def command_generator():
    """Generate a new command every 60 seconds."""
    global next_command
    while True:
        with command_lock:
            if next_command is None:
                next_command = generate_random_command()
        time.sleep(60)  # Wait for 60 seconds before generating the next command

# Start the command generator in a separate thread
threading.Thread(target=command_generator, daemon=True).start()

@app.route('/get_command', methods=['GET'])
def get_command():
    """Endpoint to get the next trading command."""
    global next_command
    with command_lock:
        if next_command:
            command = next_command
            next_command = None
            return jsonify(command)
        else:
            return jsonify({"message": "No command available"}), 204

@app.route('/send_command', methods=['POST'])
def send_command():
    """Endpoint to send a trading command via API."""
    global next_command
    command = request.json
    
    # Validate the incoming command
    required_fields = ['action', 'symbol', 'volume', 'price', 'sl', 'tp']
    if not all(field in command for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    if command['action'] not in ['BUY', 'SELL']:
        return jsonify({"error": "Invalid action. Must be 'BUY' or 'SELL'"}), 400
    
    try:
        command['volume'] = float(command['volume'])
        command['price'] = float(command['price'])
        command['sl'] = float(command['sl'])
        command['tp'] = float(command['tp'])
    except ValueError:
        return jsonify({"error": "Invalid numeric values"}), 400
    
    with command_lock:
        next_command = command
    
    return jsonify({"message": "Command received and queued"}), 200

@app.route('/trade_result', methods=['POST'])
def trade_result():
    """Endpoint to receive trade execution results."""
    result = request.json
    print(f"Received trade result: {result}")
    # Here you can add code to process or store the trade result
    return jsonify({"message": "Trade result received"}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)