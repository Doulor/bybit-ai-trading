"""
Export live Bybit data to GitHub Pages (live-data branch).
Runs via Windows Task Scheduler.
wallet = balance - unrealized PnL (JS adds real-time PnL back).
"""
import sys, os, json, time, subprocess

PROJECT = r'C:\Users\Doulor\Documents\BybitAI'
DATA_DIR = os.path.join(PROJECT, 'data')
sys.path.insert(0, os.path.join(PROJECT, 'scripts', 'utils'))

from _bybit_helpers import get_balance, get_positions

def export():
    print(f'[{time.strftime("%H:%M:%S")}] Exporting...')
    
    bal = get_balance()
    positions = get_positions()
    total_upnl = sum(float(p.get('unrealisedPnl', 0)) for p in positions)
    wallet_only = bal - total_upnl
    
    live = {
        'wallet': round(wallet_only, 4),
        'equity': round(bal, 4),
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
    
    print(f'  bal={bal:.2f} wallet={wallet_only:.2f} pos={len(positions)}')
    
    os.chdir(PROJECT)
    
    # Write to temp file first (stays on current branch)
    os.makedirs(os.path.join(PROJECT, 'temp'), exist_ok=True)
    with open(os.path.join(PROJECT, 'temp', 'live_push.json'), 'w', encoding='utf-8') as f:
        json.dump(live, f, indent=2)
    
    # Switch to live-data
    subprocess.run(['git', 'checkout', 'live-data'], capture_output=True, timeout=10)
    
    # Copy temp to data/live.json
    import shutil
    shutil.copy2(os.path.join(PROJECT, 'temp', 'live_push.json'), os.path.join(DATA_DIR, 'live.json'))
    
    subprocess.run(['git', 'add', 'data/live.json'], capture_output=True, timeout=10)
    result = subprocess.run(['git', 'diff', '--cached', '--quiet'], capture_output=True, timeout=10)
    if result.returncode == 0:
        print('  No changes')
        subprocess.run(['git', 'checkout', 'main'], capture_output=True, timeout=10)
        return
    
    ts = time.strftime('%Y-%m-%d %H:%M')
    subprocess.run(['git', 'commit', '-m', f'live {ts}'], capture_output=True, timeout=10)
    push = subprocess.run(['git', 'push', 'origin', 'live-data'], capture_output=True, timeout=30, text=True)
    print(f'  {"Pushed" if push.returncode == 0 else "Failed: "+push.stderr[:100]}')
    subprocess.run(['git', 'checkout', 'main'], capture_output=True, timeout=10)

if __name__ == '__main__':
    export()
