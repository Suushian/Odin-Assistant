/* تست‌های آفلاین دروازهٔ کیفیت دادهٔ بازار. */
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert');

const root = path.resolve(__dirname, '..', '..');
const source = path.join(root, 'android', 'app', 'src', 'main', 'assets', 'www', 'js', 'data.js');
const O = { CONFIG: {}, faNum: n => String(n), BUS: { emit: function () {} }, core: { EVENTS: { FUNDAMENTAL_COLLECTED: 'fundamental.collected' } } };
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

const gap = sample(now);
gap.h1.splice(100, 3);
assert(Array.from(O.validateMarketData(gap, now)).some(
  x => x.startsWith('H1') && x.includes('شکاف زمانی')
), 'suspicious intraday H1 gaps must be rejected');

const h4Start = Date.UTC(2026, 9, 14, 8, 0);
const h4 = [
  { t: h4Start, o: 1.1, h: 1.2, l: 1.0, c: 1.15 },
  { t: h4Start + 4 * 60 * 60000, o: 1.15, h: 1.25, l: 1.05, c: 1.2 }
];
assert.strictEqual(O.keepCompleted4h(h4, Date.UTC(2026, 9, 14, 14, 30)).length, 1);
assert.strictEqual(O.keepCompleted4h(h4, Date.UTC(2026, 9, 14, 16, 0)).length, 2);

const weekend = Date.UTC(2026, 9, 17, 12, 0);
const weekendData = sample(weekend);
weekendData.m15 = weekendData.m15.map(x => ({ ...x, t: x.t - 2 * 60 * 60000 }));
weekendData.h1 = weekendData.h1.map(x => ({ ...x, t: x.t - 5 * 60 * 60000 }));
assert(!Array.from(O.validateMarketData(weekendData, weekend)).some(x => x.includes('کهنه است')));

const futureWeekend = sample(weekend);
futureWeekend.h1 = futureWeekend.h1.map(x => ({ ...x, t: x.t + 2 * 24 * 60 * 60000 }));
assert(Array.from(O.validateMarketData(futureWeekend, weekend)).some(
  x => x.startsWith('H1') && x.includes('آینده')
), 'future-dated H1 data must be rejected even when FX is closed');

const calendarLogs = [];
const staleCalendar = {
  events: [{ title: 'test event' }],
  ok: true,
  stale: true,
  fromCache: true,
  fetchedAt: Date.now() - 95 * 60000,
  error: 'HTTP -1'
};
O.collectFundamental(
  { tradingview: { enabled: false }, fundamental: { enabled: true }, news: { enabled: false }, symbols: [] },
  {},
  {},
  line => calendarLogs.push(line),
  {
    tv: null,
    calendar: { fetchCalendar: () => Promise.resolve(staleCalendar) },
    news: null
  }
).then(() => {
  assert(calendarLogs.some(line => line.includes('تقویم اقتصادی کهنه است')), calendarLogs);
  assert(calendarLogs.some(line => line.includes('95 دقیقه')), calendarLogs);
  console.log('market data quality tests passed (8 scenarios, including stale calendar warning).');
}).catch(err => {
  console.error(err);
  process.exitCode = 1;
});


// Exercise the real fetchCalendar cache/fallback path, not only a fabricated
// snapshot passed to collectFundamental.
async function testCalendarCacheLifecycle() {
  O.CAL_SOURCE_NAME = 'test-calendar';
  O.parseEvents = raw => raw.map(x => ({ when: x.when, title_fa: x.title || 'test' }));
  const savedNow = Date.now;
  const fixedNow = Date.now();
  Date.now = () => fixedNow;
  try {
    function store(ts) {
      const mem = { 'cache.calendar': JSON.stringify({
        fetched_at: new Date(ts).toISOString(),
        events: [{ when: new Date(fixedNow + 60 * 60000).toISOString(), title: 'event' }]
      }) };
      return {
        get: k => mem[k] || '',
        set: (k, v) => { mem[k] = String(v); },
        del: k => { delete mem[k]; }
      };
    }
    const cfg = { fundamental: { enabled: true, cache_ttl_minutes: 30, source_url: 'https://calendar.invalid' } };

    let requests = 0;
    O.http = () => { requests++; return Promise.resolve({ status: -1, text: 'offline' }); };
    const fresh = await O.fetchCalendar(cfg, store(fixedNow - 10 * 60000));
    assert.strictEqual(fresh.ok, true);
    assert.strictEqual(fresh.stale, false);
    assert.strictEqual(fresh.fromCache, true);
    assert.strictEqual(fresh.fetchedAt, fixedNow - 10 * 60000);
    assert.strictEqual(requests, 0, 'fresh cache must avoid network requests');

    const stale = await O.fetchCalendar(cfg, store(fixedNow - 95 * 60000));
    assert.strictEqual(stale.ok, true);
    assert.strictEqual(stale.stale, true);
    assert.strictEqual(stale.fromCache, true);
    assert.strictEqual(stale.fetchedAt, fixedNow - 95 * 60000);
    assert.strictEqual(stale.error, 'HTTP -1');
    assert.strictEqual(requests, 1, 'stale cache should attempt one refresh');

    const unavailable = await O.fetchCalendar(cfg, {
      get: () => '', set: () => {}, del: () => {}
    });
    assert.strictEqual(unavailable.ok, false);
    assert.strictEqual(unavailable.stale, false);
    assert.strictEqual(unavailable.fromCache, false);
    assert.strictEqual(unavailable.fetched, false);
    assert.strictEqual(unavailable.error, 'HTTP -1');
    assert.strictEqual(requests, 2);
    console.log('calendar cache lifecycle passed (3 real fetchCalendar paths).');
  } finally {
    Date.now = savedNow;
  }
}
testCalendarCacheLifecycle().catch(err => {
  console.error(err);
  process.exitCode = 1;
});
