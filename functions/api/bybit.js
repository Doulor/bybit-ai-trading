// Cloudflare Pages Function: /api/bybit
// Fetches live account data from Bybit using RSA signing
// Env vars: BYBIT_API_KEY, BYBIT_PRIVATE_KEY (full PEM content)

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function pemToDer(pem) {
  const cleaned = pem
    .replace(/\\n/g, '\n')
    .replace(/-----BEGIN PRIVATE KEY-----/, '')
    .replace(/-----END PRIVATE KEY-----/, '')
    .replace(/\s+/g, '');
  const raw = atob(cleaned);
  const buf = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);
  return buf;
}

async function signRS256Base64(data, privateKeyPem) {
  const der = pemToDer(privateKeyPem);
  const key = await crypto.subtle.importKey(
    'pkcs8', der,
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false, ['sign']
  );
  const sig = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', key, new TextEncoder().encode(data));
  // Convert ArrayBuffer to base64
  const bytes = new Uint8Array(sig);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

async function bybitGet(path, params, apiKey, privateKey) {
  const ts = Date.now().toString();
  const recvWindow = '5000';
  const qs = new URLSearchParams(params).toString();
  // Bybit V5 RSA: timestamp + apiKey + recvWindow + queryString
  const signStr = ts + apiKey + recvWindow + qs;
  const signature = await signRS256Base64(signStr, privateKey);

  const url = 'https://api.bybit.com' + path + '?' + qs;
  const resp = await fetch(url, {
    headers: {
      'X-BAPI-API-KEY': apiKey,
      'X-BAPI-TIMESTAMP': ts,
      'X-BAPI-RECV-WINDOW': recvWindow,
      'X-BAPI-SIGN': signature,
      'X-BAPI-SIGN-TYPE': '2',
    },
  });
  return resp.json();
}

export async function onRequestGet(context) {
  const { BYBIT_API_KEY, BYBIT_PRIVATE_KEY } = context.env;
  if (!BYBIT_API_KEY || !BYBIT_PRIVATE_KEY) {
    return Response.json({
      error: 'Missing env vars. Set BYBIT_API_KEY and BYBIT_PRIVATE_KEY in Cloudflare Pages settings.',
      wallet: 0, equity: 0, positions: [], openOrders: [],
      updated_at: Date.now(),
    }, { headers: CORS });
  }

  try {
    const [bal, pos, orders] = await Promise.all([
      bybitGet('/v5/account/wallet-balance', { accountType: 'UNIFIED', coin: 'USDT' }, BYBIT_API_KEY, BYBIT_PRIVATE_KEY),
      bybitGet('/v5/position/list', { category: 'linear', settleCoin: 'USDT' }, BYBIT_API_KEY, BYBIT_PRIVATE_KEY),
      bybitGet('/v5/order/realtime', { category: 'linear', settleCoin: 'USDT' }, BYBIT_API_KEY, BYBIT_PRIVATE_KEY),
    ]);

    let wallet = 0, equity = 0;
    if (bal.retCode === 0 && bal.result?.list?.[0]?.coin) {
      for (const c of bal.result.list[0].coin) {
        if (c.coin === 'USDT') {
          wallet = parseFloat(c.walletBalance || 0);
          equity = parseFloat(c.equity || 0);
        }
      }
    }

    const positions = [];
    if (pos.retCode === 0 && pos.result?.list) {
      for (const p of pos.result.list) {
        if (parseFloat(p.size || 0) > 0) {
          positions.push({
            symbol: p.symbol, side: p.side, size: p.size, avgPrice: p.avgPrice,
            unrealisedPnl: p.unrealisedPnl || '0', takeProfit: p.takeProfit || '0',
            stopLoss: p.stopLoss || '0', leverage: p.leverage || '1', liqPrice: p.liqPrice || '0',
          });
        }
      }
    }

    const openOrders = [];
    if (orders.retCode === 0 && orders.result?.list) {
      for (const o of orders.result.list) {
        openOrders.push({
          symbol: o.symbol, side: o.side, orderType: o.orderType, qty: o.qty,
          price: o.price || '', stopLoss: o.stopLoss || '', takeProfit: o.takeProfit || '',
        });
      }
    }

    if (bal.retCode !== 0) {
      return Response.json({
        error: 'Bybit: ' + bal.retMsg,
        wallet: 0, equity: 0, positions: [], openOrders: [],
        updated_at: Date.now(),
      }, { headers: CORS });
    }

    return Response.json({ wallet, equity, positions, openOrders, updated_at: Date.now() }, { headers: CORS });

  } catch (e) {
    return Response.json({ error: e.message, wallet: 0, equity: 0, positions: [], openOrders: [], updated_at: Date.now() }, { headers: CORS });
  }
}

export async function onRequestOptions() {
  return new Response(null, { headers: CORS });
}
