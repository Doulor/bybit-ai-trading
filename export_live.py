"""
Export live Bybit data to main branch.
Uses --amend to avoid creating new commits each time.
"""
import sys, os, json, time, subprocess

PROJECT = r'C:\Users\Doulor\Documents\BybitAI'
DATA_DIR = os.path.join(PROJECT, 'data')
sys.path.insert(0, os.path.join(PROJECT, 'scripts', 'utils'))
from _bybit_helpers import get_balance, get_positions, bybit_req

def get_spot_assets():
    """Get non-USDT coin assets from unified wallet with purchase info."""
    uni = bybit_req('GET', '/v5/account/wallet-balance', {'accountType': 'UNIFIED'})
    assets = []
    for c in uni['result']['list'][0].get('coin', []):
        coin = c.get('coin', '')
        if coin == 'USDT':
            continue
        bal = float(c.get('walletBalance', 0))
        if bal <= 0:
            continue
        usd_value = float(c.get('usdValue', 0))
        try:
            cur_price = usd_value / bal
        except:
            cur_price = 0

        # Get avg buy price and buy time from filled orders
        avg_price = 0
        buy_time = ''
        try:
            orders = bybit_req('GET', '/v5/order/history', {'category': 'spot', 'symbol': f'{coin}USDT', 'limit': '20'})
            for o in orders.get('result', {}).get('list', []):
                if o.get('side') == 'Buy' and o.get('orderStatus') == 'Filled':
                    avg_price = float(o.get('avgPrice', 0)) or float(o.get('price', 0))
                    buy_time = o.get('createdTime', '')
                    if buy_time:
                        buy_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(int(buy_time) / 1000))
                    break
        except:
            pass

        pnl = (cur_price - avg_price) * bal if avg_price > 0 else 0
        pnl_pct = ((cur_price - avg_price) / avg_price * 100) if avg_price > 0 else 0

        assets.append({
            'coin': coin,
            'qty': bal,
            'price': round(cur_price, 4),
            'value': round(usd_value, 4),
            'avgPrice': round(avg_price, 4),
            'buyTime': buy_time,
            'pnl': round(pnl, 4),
            'pnlPct': round(pnl_pct, 2)
        })
    return assets

def export():
    print(f'[{time.strftime("%H:%M:%S")}] Exporting...')
    
    bal = get_balance()
    positions = get_positions()
    spot_assets = get_spot_assets()
    
    # Calculate equity = wallet + unrealised PnL + spot assets
    total_unrealised = sum(float(p.get('unrealisedPnl', 0)) for p in positions)
    total_spot = sum(a['value'] for a in spot_assets)
    equity = bal + total_unrealised + total_spot
    
    live = {
        'wallet': round(bal, 4),
        'equity': round(equity, 4),
        'spotAssets': spot_assets,
        'positions': [{'symbol':p['symbol'],'side':p['side'],'size':p['size'],
        'avgPrice':p['avgPrice'],'unrealisedPnl':p['unrealisedPnl'],
        'leverage':p['leverage'],'liqPrice':p.get('liqPrice',''),
        'stopLoss':p.get('stopLoss',''),'takeProfit':p.get('takeProfit',''),
        'markPrice':p.get('markPrice',''),'createdTime':p.get('createdTime',''),
        'positionIdx':p.get('positionIdx',0)} for p in positions],
        'openOrders': [],
        'updated_at': int(time.time() * 1000),
        'updated_local': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    }
    
    print(f'  bal={bal:.2f} pos={len(positions)} spot={len(spot_assets)} total_spot=${total_spot:.2f}')
    
    os.chdir(PROJECT)
    
    # Ensure on main
    subprocess.run(['git', 'checkout', 'main'], capture_output=True, timeout=10)
    
    # Write live.json
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, 'live.json'), 'w', encoding='utf-8') as f:
        json.dump(live, f, indent=2)
    
    # Stage only live.json
    subprocess.run(['git', 'add', 'data/live.json'], capture_output=True, timeout=10)
    result = subprocess.run(['git', 'diff', '--cached', '--quiet'], capture_output=True, timeout=10)
    if result.returncode == 0:
        print('  No changes')
        return
    
    # Amend last commit (no new commit created)
    ts = time.strftime('%Y-%m-%d %H:%M')
    subprocess.run(['git', 'commit', '--amend', '-m', f'live {ts}'], capture_output=True, timeout=10)
    push = subprocess.run(['git', 'push', '--force', 'origin', 'main'], capture_output=True, timeout=30, text=True)
    print(f'  {"Pushed (amended)" if push.returncode == 0 else "Failed: "+push.stderr[:100]}')

if __name__ == '__main__':
    export()
