"""Export live Bybit data to JSON for the dashboard."""
import os, sys, time, json, base64
from urllib.parse import urlencode
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import requests

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

_pw = bytes()
pk = serialization.load_pem_private_key(pem_data, password=_pw if _pw else None)

base = 'https://api.bybit.com'

def sign(ts, ps):
    payload = f"{ts}{api_key}5000{ps}"
    sig = pk.sign(payload.encode(), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()

def req(method, path, params=None):
    ts = str(int(time.time() * 1000))
    params = params or {}
    ps = urlencode(params) if method == 'GET' else json.dumps(params)
    s = sign(ts, ps)
    h = {'X-BAPI-API-KEY': api_key, 'X-BAPI-TIMESTAMP': ts, 'X-BAPI-RECV-WINDOW': '5000', 'X-BAPI-SIGN': s, 'X-BAPI-SIGN-TYPE': '2'}
    url = f'{base}{path}'
    if method == 'GET' and params: url += f'?{ps}'
    body = None
    if method != 'GET':
        h['Content-Type'] = 'application/json'
        body = ps.encode()
    r = requests.request(method, url, data=body, headers=h, timeout=15)
    return r.json()

bal = req('GET', '/v5/account/wallet-balance', {'accountType': 'UNIFIED', 'coin': 'USDT'})
wallet = equity = 0
if bal.get('retCode') == 0:
    for c in bal['result']['list'][0]['coin']:
        if c['coin'] == 'USDT':
            wallet = float(c.get('walletBalance', 0))
            equity = float(c.get('equity', 0))

pos = req('GET', '/v5/position/list', {'category': 'linear', 'settleCoin': 'USDT'})
positions = []
if pos.get('retCode') == 0:
    for p in pos['result']['list']:
        if float(p.get('size', 0)) > 0:
            positions.append({
                'symbol': p['symbol'], 'side': p['side'], 'size': p['size'],
                'avgPrice': p['avgPrice'], 'unrealisedPnl': p.get('unrealisedPnl', '0'),
                'takeProfit': p.get('takeProfit', '0'), 'stopLoss': p.get('stopLoss', '0'),
                'leverage': p.get('leverage', '1'), 'liqPrice': p.get('liqPrice', '0'),
                'markPrice': p.get('markPrice', '0'),
            })

orders = req('GET', '/v5/order/realtime', {'category': 'linear', 'settleCoin': 'USDT'})
open_orders = []
if orders.get('retCode') == 0:
    for o in orders['result']['list']:
        open_orders.append({
            'symbol': o['symbol'], 'side': o['side'], 'orderType': o['orderType'],
            'qty': o['qty'], 'price': o.get('price', ''),
        })

data = {
    'wallet': wallet, 'equity': equity,
    'positions': positions, 'openOrders': open_orders,
    'updated_at': int(time.time() * 1000),
}

out = r'C:\Users\Doulor\Documents\BybitAI\data\live.json'
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, 'w') as f:
    json.dump(data, f, indent=2)

print(f"wallet={wallet:.4f} equity={equity:.4f} pos={len(positions)} orders={len(open_orders)}")
