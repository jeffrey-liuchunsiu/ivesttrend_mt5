from flask import Flask, request, jsonify
import MetaTrader5 as mt5
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

# Initialize MT5 connection
if not mt5.initialize():
    print("MT5 initialization failed")
    mt5.shutdown()

@app.route('/mt5/signal', methods=['POST'])
def receive_mt5_data():
    try:
        data = request.json
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Log received data
        logging.info(f"Received data: {json.dumps(data, indent=2)}")
        print(f"Received data: {json.dumps(data, indent=2)}")  # Console print
        
        if data.get('type') == 'trade_signal':
            symbol = data.get('symbol')
            action = data.get('action')
            price = data.get('price')
            sl = data.get('sl')
            tp = data.get('tp')
            volume = data.get('volume')
            
            # Place order based on received signal
            result = place_order(symbol, action, volume, price, sl, tp)
            
            return jsonify({
                'status': 'success',
                'message': f'Trade order processed: {result}',
                'timestamp': timestamp
            })
            
        elif data.get('type') == 'market_data':
            symbol = data.get('symbol')
            print(f"Market data received for {symbol}: Bid={data.get('bid')}, Ask={data.get('ask')}")
            return jsonify({
                'status': 'success',
                'message': f'Market data received for {symbol}',
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
        print(f"Error: {str(e)}")  # Console print
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }), 500

def place_order(symbol, action, volume, price, sl, tp):
    try:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 10,
            "magic": 234000,
            "comment": f"Python order - {action}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send order
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Order failed: {result.comment}")
            return f"Order failed: {result.comment}"
        
        print(f"Order successful: {result.comment}")
        return f"Order placed successfully. Ticket: {result.order}"
        
    except Exception as e:
        print(f"Error placing order: {str(e)}")
        return f"Error placing order: {str(e)}"

if __name__ == '__main__':
    print("Server starting...")
    print("MT5 connection status:", "Connected" if mt5.initialize() else "Not connected")
    app.run(host='0.0.0.0', port=5000, debug=True)