/* تست‌های آفلاین دروازهٔ کیفیت دادهٔ بازار. */
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert');

const root = path.resolve(__dirname, '..', '..');
const source = path.join(root, 'android', 'app', 'src', 'main', 'assets', 'www', 'js', 'data.js');
const O = { CONFIG: {}, BUS: { emit: function () {} } };
const ctx = { console, Date, Map, Promise, URL, Uint8Array, TextDecoder, ODIN: O, fetch: () => Promise.reject(new Error('offline')) };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(source, 'utf8'), ctx, { filename: 'data.js' });

function rows(n, interval, end, base) {
  const out = [];
  for (let i = n - 1; i >= 0; i--) {
    const c = base + (n - i) * 0.00001;
    out.push({ t: end - i * interval, o: c - 0.00002, h: c + 0.00005, l: c - 0.00005, c });
  }
  return out;
}
function sample(now) {
  const m15 = 15 * 60000, h1 = 60 * 60000, h4 = 4 * h1;
  return {
    symbol: 'EURUSD',
    m15: rows(100, m15, Math.floor(now / m15) * m15 - m15, 1.1),
    h1: rows(300, h1, Math.floor(now / h1) * h1 - h1, 1.1),
    h4: rows(240, h4, Math.floor(now / h4) * h4 - h4, 1.1)
  };
}

const now = Date.UTC(2026, 9, 14, 14, 30); // Wednesday, market open
assert.deepStrictEqual(Array.from(O.validateMarketData(sample(now), now)), []);

const stale = sample(now);
stale.m15 = stale.m15.map(x => ({ ...x, t: x.t - 2 * 60 * 60000 }));
stale.h1 = stale.h1.map(x => ({ ...x, t: x.t - 5 * 60 * 60000 }));
const staleErrors = Array.from(O.validateMarketData(stale, now));
assert(staleErrors.some(x => x.startsWith('M15') && x.includes('کهنه')), staleErrors);
assert(staleErrors.some(x => x.startsWith('H1') && x.includes('کهنه')), staleErrors);

const bad = sample(now);
bad.m15[bad.m15.length - 1].h = 0.1;
assert(Array.from(O.validateMarketData(bad, now)).some(x => x.includes('OHLC ناسازگار')));

const short = sample(now);
short.h1 = short.h1.slice(0, 200);
assert(Array.from(O.validateMarketData(short, now)).some(x => x.startsWith('H1: تاریخچه ناکافی')));

const weekend = Date.UTC(2026, 9, 17, 12, 0);
const weekendData = sample(weekend);
weekendData.m15 = weekendData.m15.map(x => ({ ...x, t: x.t - 2 * 60 * 60000 }));
weekendData.h1 = weekendData.h1.map(x => ({ ...x, t: x.t - 5 * 60 * 60000 }));
assert(!Array.from(O.validateMarketData(weekendData, weekend)).some(x => x.includes('کهنه است')));

console.log('market data quality tests passed (5 scenarios).');
