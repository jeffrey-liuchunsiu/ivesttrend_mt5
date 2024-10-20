from flask import Flask, jsonify
import random

app = Flask(__name__)

@app.route('/get_order', methods=['GET'])
def get_order():
    # This is a simple example. In a real scenario, you'd have more complex logic here.
    order = {
    "action": "BUY",
    "symbol": "EURUSD",
    "volume": 0.1,
    "price": 1.8600,
    "sl": 1.0990,
    "tp": 1.1010
}
    return jsonify(order)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)