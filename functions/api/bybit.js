// Cloudflare Pages Function: /api/bybit
// Fetches live account data from Bybit using HMAC signing
// Env vars: BYBIT_API_KEY, BYBIT_API_SECRET

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

async function hmacSign(secret, data) {
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(data));
  return Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function bybitGet(path, params, apiKey, apiSecret) {
  const ts = Date.now().toString();
  const recvWindow = '5000';
  const qs = new URLSearchParams(params).toString();
  // HMAC signing: timestamp + apiKey + recvWindow + queryString (NO path)
  const signStr = ts + apiKey + recvWindow + qs;
  const signature = await hmacSign(apiSecret, signStr);

  const url = 'https://api.bybit.com' + path + '?' + qs;
  const resp = await fetch(url, {
    headers: {
      'X-BAPI-API-KEY': apiKey,
      'X-BAPI-TIMESTAMP': ts,
      'X-BAPI-RECV-WINDOW': recvWindow,
      'X-BAPI-SIGN': signature,
    },
  });
  return resp.json();
}

export async function onRequestGet(context) {
  const { BYBIT_API_KEY, BYBIT_API_SECRET } = context.env;
  if (!BYBIT_API_KEY || !BYBIT_API_SECRET) {
    return Response.json({ error: 'Missing BYBIT_API_KEY or BYBIT_API_SECRET env vars' }, { status: 500, headers: CORS });
  }

  try {
    const [bal, pos, orders] = await Promise.all([
      bybitGet('/v5/account/wallet-balance', { accountType: 'UNIFIED', coin: 'USDT' }, BYBIT_API_KEY, BYBIT_API_SECRET),
      bybitGet('/v5/position/list', { category: 'linear', settleCoin: 'USDT' }, BYBIT_API_KEY, BYBIT_API_SECRET),
      bybitGet('/v5/order/realtime', { category: 'linear', settleCoin: 'USDT' }, BYBIT_API_KEY, BYBIT_API_SECRET),
    ]);

    // Extract USDT balance
    let wallet = 0, equity = 0;
    if (bal.retCode === 0 && bal.result?.list?.[0]?.coin) {
      for (const c of bal.result.list[0].coin) {
        if (c.coin === 'USDT') {
          wallet = parseFloat(c.walletBalance || 0);
          equity = parseFloat(c.equity || 0);
        }
      }
    }

    // Extract positions
    const positions = [];
    if (pos.retCode === 0 && pos.result?.list) {
      for (const p of pos.result.list) {
        if (parseFloat(p.size || 0) > 0) {
          positions.push({
            symbol: p.symbol,
            side: p.side,
            size: p.size,
            avgPrice: p.avgPrice,
            unrealisedPnl: p.unrealisedPnl || '0',
            takeProfit: p.takeProfit || '0',
            stopLoss: p.stopLoss || '0',
            leverage: p.leverage || '1',
            liqPrice: p.liqPrice || '0',
          });
        }
      }
    }

    // Extract open orders
    const openOrders = [];
    if (orders.retCode === 0 && orders.result?.list) {
      for (const o of orders.result.list) {
        openOrders.push({
          symbol: o.symbol,
          side: o.side,
          orderType: o.orderType,
          qty: o.qty,
          price: o.price || '',
          stopLoss: o.stopLoss || '',
          takeProfit: o.takeProfit || '',
        });
      }
    }

    if (bal.retCode !== 0) {
      return Response.json({
        error: 'Bybit API error: ' + bal.retMsg,
        wallet: 0, equity: 0, positions: [], openOrders: [],
        updated_at: Date.now(),
      }, { headers: CORS });
    }

    return Response.json({
      wallet, equity, positions, openOrders,
      updated_at: Date.now(),
    }, { headers: CORS });

  } catch (e) {
    return Response.json({ error: e.message, stack: e.stack }, { status: 500, headers: CORS });
  }
}

export async function onRequestOptions() {
  return new Response(null, { headers: CORS });
}
