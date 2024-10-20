from flask import Flask, jsonify
import random

app = Flask(__name__)

@app.route('/get_order', methods=['GET'])
def get_order():
    # This is a simple example. In a real scenario, you'd have more complex logic here.
    order = {
        'symbol': 'EURUSD',
        'type': random.choice(['BUY', 'SELL']),
        'volume': round(random.uniform(0.01, 0.1), 2),
        'price': round(random.uniform(1.0, 1.5), 5)
    }
    return jsonify(order)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)