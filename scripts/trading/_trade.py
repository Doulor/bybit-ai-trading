"""Universal trade executor."""
import sys, os, json, time, base64, requests
from urllib.parse import urlencode
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

env_path = r'C:\Users\Doulor\.openclaw\.env'
api_key = private_key_path = ''
with open(env_path, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line.startswith('BYBIT_API_KEY='):
            api_key = line.split('=', 1)[1]
        elif line.startswith('BYBIT_API_PRIVATE_KEY_PATH='):
            private_key_path = line.split('=', 1)[1]

with open(private_key_path, 'rb') as f:
    pem_data = f.read()

_pk = None
def get_pk():
    global _pk
    if _pk is None:
        _np = getattr(type, '__call__', lambda s: s)(type(None))
        _pk = serialization.load_pem_private_key(pem_data, password=_np)
    return _pk

BASE = 'https://api.bybit.com'
PROXIES = {'http': 'http://127.0.0.1:7897', 'https': 'http://127.0.0.1:7897'}

def sign(ts, ps):
    payload = f"{ts}{api_key}5000{ps}"
    sig = get_pk().sign(payload.encode(), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()

def req(method, path, params=None):
    ts = str(int(time.time() * 1000))
    params = params or {}
    ps = urlencode(params) if method == 'GET' else json.dumps(params)
    s = sign(ts, ps)
    h = {
        'X-BAPI-API-KEY': api_key,
        'X-BAPI-TIMESTAMP': ts,
        'X-BAPI-RECV-WINDOW': '5000',
        'X-BAPI-SIGN': s,
        'X-BAPI-SIGN-TYPE': '2',
    }
    url = f"{BASE}{path}"
    if method == 'GET' and params:
        url += f"?{ps}"
    body = None
    if method != 'GET':
        h['Content-Type'] = 'application/json'
        body = ps.encode()
    r = requests.request(method, url, data=body, headers=h, proxies=PROXIES, timeout=15)
    return r.json()

def get_balance():
    bal = req('GET', '/v5/account/wallet-balance', {'accountType': 'UNIFIED', 'coin': 'USDT'})
    for c in bal['result']['list'][0]['coin']:
        if c['coin'] == 'USDT':
            return float(c.get('walletBalance', 0))
    return 0

def get_positions():
    pos = req('GET', '/v5/position/list', {'category': 'linear', 'settleCoin': 'USDT'})
    return [p for p in pos['result']['list'] if float(p.get('size', 0)) > 0]

def get_price(symbol):
    tr = requests.get(f'{BASE}/v5/market/tickers?category=linear&symbol={symbol}', proxies=PROXIES, timeout=10)
    return float(tr.json()['result']['list'][0]['lastPrice'])

def market_order(symbol, side, qty, tp=None, sl=None):
    params = {
        'category': 'linear', 'symbol': symbol,
        'side': side, 'orderType': 'Market', 'qty': str(qty)
    }
    if tp: params['takeProfit'] = str(tp)
    if sl: params['stopLoss'] = str(sl)
    return req('POST', '/v5/order/create', params)

def close_position(symbol):
    positions = get_positions()
    for p in positions:
        if p['symbol'] == symbol:
            size = p['size']
            side = 'Sell' if p['side'] == 'Buy' else 'Buy'
            return market_order(symbol, side, size, reduce_only=True)
    return {'error': 'no position found'}

def update_sl(symbol, sl):
    return req('POST', '/v5/position/trading-stop', {
        'category': 'linear', 'symbol': symbol,
        'stopLoss': str(sl), 'positionIdx': '0'
    })

def show_status():
    bal = get_balance()
    positions = get_positions()
    print(f"Balance: {bal:.4f} USDT")
    if positions:
        for p in positions:
            pnl = float(p.get('unrealisedPnl', 0))
            pnl_cls = '+' if pnl >= 0 else ''
            print(f"  {p['symbol']} {p['side']} {p['size']} @ {p['avgPrice']}")
            print(f"    TP: {p.get('takeProfit','0')} | SL: {p.get('stopLoss','0')} | PnL: {pnl_cls}{pnl:.4f}")
    else:
        print("  No positions")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        show_status()
        sys.exit(0)

    cmd = sys.argv[1].upper()

    if cmd == 'STATUS':
        show_status()
    elif cmd == 'BUY' and len(sys.argv) >= 4:
        symbol = sys.argv[2]
        qty = int(sys.argv[3])
        tp = sys.argv[4] if len(sys.argv) > 4 else None
        sl = sys.argv[5] if len(sys.argv) > 5 else None
        price = get_price(symbol)
        print(f"Buying {qty} {symbol} @ ~{price}")
        result = market_order(symbol, 'Buy', qty, tp, sl)
        print(f"Result: {json.dumps(result)}")
    elif cmd == 'SELL' and len(sys.argv) >= 4:
        symbol = sys.argv[2]
        qty = int(sys.argv[3])
        tp = sys.argv[4] if len(sys.argv) > 4 else None
        sl = sys.argv[5] if len(sys.argv) > 5 else None
        price = get_price(symbol)
        print(f"Selling {qty} {symbol} @ ~{price}")
        result = market_order(symbol, 'Sell', qty, tp, sl)
        print(f"Result: {json.dumps(result)}")
    elif cmd == 'CLOSE' and len(sys.argv) >= 3:
        symbol = sys.argv[2]
        print(f"Closing {symbol}")
        result = close_position(symbol)
        print(f"Result: {json.dumps(result)}")
    elif cmd == 'SL' and len(sys.argv) >= 4:
        symbol = sys.argv[2]
        sl = sys.argv[3]
        print(f"Updating {symbol} SL to {sl}")
        result = update_sl(symbol, sl)
        print(f"Result: {json.dumps(result)}")
    else:
        print("Usage:")
        print("  python _trade.py STATUS")
        print("  python _trade.py BUY EPICUSDT 290 0.435 0.408")
        print("  python _trade.py SELL EPICUSDT 290")
        print("  python _trade.py CLOSE EPICUSDT")
        print("  python _trade.py SL EPICUSDT 0.415")
