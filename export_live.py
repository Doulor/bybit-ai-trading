"""Export live Bybit data and push to live-data branch (amend, no new commits)."""
import os, sys, time, json, base64, subprocess
from urllib.parse import urlencode
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import requests

# Read API credentials from env or local .env file
api_key = os.environ.get('BYBIT_API_KEY', '')
private_key_pem = os.environ.get('BYBIT_PRIVATE_KEY', '')

if not api_key:
    env_path = r'C:\Users\Doulor\.openclaw\.env'
    private_key_path = ''
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('BYBIT_API_KEY='):
                    api_key = line.split('=', 1)[1]
                elif line.startswith('BYBIT_API_PRIVATE_KEY_PATH='):
                    private_key_path = line.split('=', 1)[1]
        if private_key_path and os.path.exists(private_key_path):
            with open(private_key_path, 'rb') as f:
                private_key_pem = f.read()

if not api_key or not private_key_pem:
    print("ERROR: API credentials not found")
    sys.exit(1)

if isinstance(private_key_pem, str):
    private_key_pem = private_key_pem.encode()
pk = serialization.load_pem_private_key(private_key_pem, password=b'')

base = 'https://api.bybit.com'

def sign(ts, ps):
    payload = f"{ts}{api_key}5000{ps}"
    return base64.b64encode(pk.sign(payload.encode(), padding.PKCS1v15(), hashes.SHA256())).decode()

def req(method, path, params=None):
    ts = str(int(time.time() * 1000))
    params = params or {}
    ps = urlencode(params) if method == 'GET' else json.dumps(params)
    s = sign(ts, ps)
    h = {'X-BAPI-API-KEY': api_key, 'X-BAPI-TIMESTAMP': ts, 'X-BAPI-RECV-WINDOW': '5000', 'X-BAPI-SIGN': s, 'X-BAPI-SIGN-TYPE': '2'}
    url = f'{base}{path}'
    if method == 'GET' and params: url += f'?{ps}'
    r = requests.request(method, url, data=ps.encode() if method != 'GET' else None, headers=h, timeout=15)
    try:
        return r.json()
    except:
        print(f"ERROR: {path} returned status {r.status_code}")
        return {'retCode': -1}

# Fetch data
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

data = {
    'wallet': wallet, 'equity': equity,
    'positions': positions, 'openOrders': [],
    'updated_at': int(time.time() * 1000),
}

# Write to data/live.json
repo_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()
out = os.path.join(repo_root, 'data', 'live.json')
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, 'w') as f:
    json.dump(data, f, indent=2)

print(f"wallet={wallet:.4f} equity={equity:.4f} pos={len(positions)}")

# Switch to live-data branch, amend, force push, switch back
subprocess.run(['git', 'stash'], cwd=repo_root, capture_output=True)
current = subprocess.check_output(['git', 'branch', '--show-current'], cwd=repo_root, text=True).strip()
subprocess.run(['git', 'checkout', 'live-data'], cwd=repo_root, capture_output=True)
subprocess.run(['git', 'add', 'data/live.json'], cwd=repo_root, capture_output=True)
subprocess.run(['git', 'commit', '--amend', '-m', 'live data'], cwd=repo_root, capture_output=True)
subprocess.run(['git', 'push', '--force', 'origin', 'live-data'], cwd=repo_root, capture_output=True)
subprocess.run(['git', 'checkout', current], cwd=repo_root, capture_output=True)
subprocess.run(['git', 'stash', 'pop'], cwd=repo_root, capture_output=True)
print("Pushed to live-data branch (amend)")
