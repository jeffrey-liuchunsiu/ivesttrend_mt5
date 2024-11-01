from flask import Flask, request, jsonify
from datetime import datetime
import json
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    filename='trading_server.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Store data
trade_signals = []
market_data = {}
positions = {}

@app.route('/mt5/signal', methods=['POST'])
def receive_mt5_data():
    try:
        data = request.json
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Log received data
        logging.info(f"Received data: {json.dumps(data, indent=2)}")
        
        if data.get('type') == 'market_data':
            symbol = data.get('symbol')
            market_data[symbol] = {
                'bid': data.get('bid'),
                'ask': data.get('ask'),
                'spread': data.get('spread'),
                'timestamp': timestamp
            }
            return jsonify({
                'status': 'success',
                'message': f'Market data received for {symbol}',
                'timestamp': timestamp
            })
            
        elif data.get('type') == 'trade_signal':
            trade_signals.append({
                'symbol': data.get('symbol'),
                'action': data.get('action'),
                'price': data.get('price'),
                'sl': data.get('sl'),
                'tp': data.get('tp'),
                'volume': data.get('volume'),
                'ticket': data.get('ticket'),
                'spread': data.get('spread'),
                'timestamp': timestamp
            })
            return jsonify({
                'status': 'success',
                'message': f'Trade signal received for {data.get("symbol")}',
                'timestamp': timestamp
            })
            
        elif data.get('type') == 'position_update':
            symbol = data.get('symbol')
            ticket = data.get('ticket')
            positions[f"{symbol}_{ticket}"] = {
                'action': data.get('action'),
                'position_type': data.get('position_type'),
                'volume': data.get('volume'),
                'price': data.get('price'),
                'sl': data.get('sl'),
                'tp': data.get('tp'),
                'profit': data.get('profit'),
                'timestamp': timestamp
            }
            return jsonify({
                'status': 'success',
                'message': f'Position update received for ticket {ticket}',
                'timestamp': timestamp
            })
            
        else:
            return jsonify({
                'status': 'error',
                'message': 'Unknown data type',
                'timestamp': timestamp
            }), 400
            
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }), 500

@app.route('/mt5/market_data', methods=['GET'])
def get_market_data():
    return jsonify(market_data)

@app.route('/mt5/signals', methods=['GET'])
def get_signals():
    return jsonify(trade_signals)

@app.route('/mt5/positions', methods=['GET'])
def get_positions():
    return jsonify(positions)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)