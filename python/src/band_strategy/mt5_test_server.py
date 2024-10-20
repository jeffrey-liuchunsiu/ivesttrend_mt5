from flask import Flask, jsonify
import random

app = Flask(__name__)

@app.route('/get_order', methods=['GET'])
def get_order():
    # This is a simple example. In a real scenario, you'd have more complex logic here.
    order = {
    "action": "BUY",
    "symbol": "BTCUSD",
    "volume": float(0.1),
    "price": float(68320.0),
    "sl": float(68300.0),
    "tp": float(68321.0)
}
    return jsonify(order)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)