from flask import Flask, request, jsonify
import queue

app = Flask(__name__)

commands = queue.Queue()

@app.route('/place_order', methods=['POST'])
def place_order():
    order = request.json
    print(f"Received order: {order}")
    commands.put(order)
    return jsonify({"message": "Order received and queued"})

@app.route('/get_command', methods=['GET'])
def get_command():
    print("Received GET request for /get_command")
    if not commands.empty():
        command = commands.get()
        print(f"Sending command: {command}")
        return jsonify(command)
    else:
        print("No command available")
        return jsonify({"message": "No command available"})

@app.route('/trade_result', methods=['POST'])
def trade_result():
    print("Received POST request for /trade_result")
    result = request.json
    print(f"Trade result received: {result}")
    return jsonify({"message": "Trade result received"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)