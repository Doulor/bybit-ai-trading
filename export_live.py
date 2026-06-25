"""
Export live Bybit account data to data/live.json and push to GitHub.
Runs via Windows Task Scheduler.
wallet = balance minus unrealized PnL (JS adds real-time PnL back)
"""
import sys, os, json, time, subprocess

PROJECT_DIR = r'C:\Users\Doulor\Documents\BybitAI'
DATA_DIR = os.path.join(PROJECT_DIR, 'data')
sys.path.insert(0, os.path.join(PROJECT_DIR, 'scripts', 'utils'))

from _bybit_helpers import get_balance, get_positions

def export():
    print(f'[{time.strftime("%H:%M:%S")}] Exporting live data...')
    
    bal = get_balance()
    positions = get_positions()
    
    # Calculate total unrealized PnL
    total_upnl = sum(float(p.get('unrealisedPnl', 0)) for p in positions)
    
    # wallet = balance minus unrealized PnL (JS will add real-time PnL)
    wallet_only = bal - total_upnl
    
    live = {
        'wallet': round(wallet_only, 4),
        'equity': round(bal, 4),
        'positions': [{
            'symbol': p['symbol'],
            'side': p['side'],
            'size': p['size'],
            'avgPrice': p['avgPrice'],
            'unrealisedPnl': p['unrealisedPnl'],
            'leverage': p['leverage'],
            'liqPrice': p.get('liqPrice', ''),
            'stopLoss': p.get('stopLoss', ''),
            'takeProfit': p.get('takeProfit', ''),
            'markPrice': p.get('markPrice', ''),
            'createdTime': p.get('createdTime', ''),
            'positionIdx': p.get('positionIdx', 0)
        } for p in positions],
        'openOrders': [],
        'updated_at': int(time.time() * 1000),
        'updated_local': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    }
    
    os.makedirs(DATA_DIR, exist_ok=True)
    live_path = os.path.join(DATA_DIR, 'live.json')
    with open(live_path, 'w', encoding='utf-8') as f:
        json.dump(live, f, indent=2)
    
    print(f'  bal={bal:.2f} wallet={wallet_only:.2f} upnl={total_upnl:.4f} pos={len(positions)}')
    
    # Only push live.json to live-data branch
    os.chdir(PROJECT_DIR)
    subprocess.run(['git', 'checkout', 'live-data'], capture_output=True, timeout=10)
    
    try:
        subprocess.run(['git', 'add', 'data/live.json'], capture_output=True, timeout=10)
        result = subprocess.run(['git', 'diff', '--cached', '--quiet'], capture_output=True, timeout=10)
        if result.returncode == 0:
            print('  No changes')
            return
        
        ts = time.strftime('%Y-%m-%d %H:%M')
        subprocess.run(['git', 'commit', '-m', f'live {ts}'], capture_output=True, timeout=10)
        push = subprocess.run(['git', 'push', 'origin', 'live-data'], capture_output=True, timeout=30, text=True)
        if push.returncode == 0:
            print(f'  Pushed live.json to live-data')
        else:
            print(f'  Push failed: {push.stderr[:200]}')
    except Exception as e:
        print(f'  Git error: {e}')

if __name__ == '__main__':
    export()
