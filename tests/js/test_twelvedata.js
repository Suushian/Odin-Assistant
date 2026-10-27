#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const A = (condition, message) => {
  if (!condition) throw new Error(message);
};

async function main() {
  const gen = require('./golden/gen_cycle_golden.js');
  const app = gen.createApp({ fixedNow: gen.FIXED_WED });
  // The golden harness stubs the provider; reload the production data module so this test
  // exercises the real parser/resampler with only the HTTP boundary mocked.
  vm.runInContext(fs.readFileSync(path.join(gen.WWW, 'data.js'), 'utf8'), app.ctx, { filename: 'data.js' });
  const O = app.O;
  const fixedNow = gen.FIXED_WED;
  const interval = 15 * 60000;
  const rows = [];
  for (let i = 0; i < 5000; i++) {
    const t = fixedNow - (5000 - i) * interval;
    const dt = new Date(t).toISOString().slice(0, 19).replace('T', ' ');
    const close = 1.1 + i * 0.000001;
    rows.push({
      datetime: dt,
      open: String(close - 0.0001),
      high: String(close + 0.0002),
      low: String(close - 0.0002),
      close: String(close)
    });
  }

  const urls = [];
  O.http = function (url) {
    urls.push(url);
    return Promise.resolve({ status: 200, text: JSON.stringify({ values: rows.slice().reverse() }) });
  };
  const md = await O.fetchTwelveDataSymbol(
    { name: 'EURUSD', td: 'EUR/USD' },
    { api_key: 'test-key-not-real', outputsize: 5000, min_request_gap_sec: 15 },
    O.CONFIG.history
  );

  A(urls.length === 1, 'برای هر نماد باید فقط یک درخواست API انجام شود؛ تعداد واقعی=' + urls.length);
  A(urls[0].indexOf('symbol=EUR%2FUSD') >= 0 && urls[0].indexOf('interval=15min') >= 0,
    'درخواست باید از نماد EUR/USD و کندل M15 استفاده کند');
  A(urls[0].indexOf('outputsize=5000') >= 0 && urls[0].indexOf('timezone=UTC') >= 0,
    'درخواست باید تاریخچهٔ حداکثری و منطقهٔ زمانی UTC بخواهد');
  A(!!md, '۵۰۰۰ کندل معتبر باید به مجموعهٔ داده تبدیل شود');
  A(md.m15.length >= 4000 && md.h1.length >= 250 && md.h4.length >= 210,
    'M15/H1/H4 باید تاریخچهٔ کافی داشته باشند');
  A(md.h1.every((x) => x.t % 3600000 === 0) && md.h4.every((x) => x.t % 14400000 === 0),
    'کندل‌های مشتق‌شده باید روی مرزهای UTC هم‌تراز باشند');
  A(md.m15[md.m15.length - 1].t + interval <= fixedNow,
    'کندل M15 در حال تشکیل نباید وارد تحلیل شود');

  const before = urls.length;
  const missing = await O.fetchTwelveDataSymbol(
    { name: 'XAUUSD', td: 'XAU/USD' }, { api_key: '' }, O.CONFIG.history
  );
  A(missing === null && urls.length === before, 'بدون کلید نباید درخواست شبکه ارسال شود');
  A(O.twelveDataErrorFor('XAUUSD').indexOf('کلید API') >= 0,
    'نبود کلید باید دلیل قابل‌فهم داشته باشد');

  const reg = O.buildDefaultRegistry(O.deepFill(O.CONFIG, {}), 'android').registry;
  A(reg.get('odin.data.market@1').id === 'data-twelvedata',
    'رجیستری اندروید باید Twelve Data را منبع بازار قرار دهد');
  const configSource = fs.readFileSync(path.join(gen.WWW, 'config.js'), 'utf8');
  A(configSource.indexOf("td: 'NZD/USD'") >= 0 && configSource.indexOf("td: 'XAU/USD'") >= 0,
    'نمادهای NZD/USD و اسپات XAU/USD باید در پیکربندی منبع وجود داشته باشند');

  // Regression: a rejected HTTP request must still consume the pacing interval.
  // Use a controlled clock/timer so this test does not sleep for 15 real seconds.
  const pacingApp = gen.createApp({ fixedNow: gen.FIXED_WED });
  vm.runInContext(fs.readFileSync(path.join(gen.WWW, 'data.js'), 'utf8'), pacingApp.ctx, { filename: 'data.js-pacing' });
  let fakeNow = gen.FIXED_WED;
  pacingApp.ctx.Date.now = () => fakeNow;
  pacingApp.ctx.setTimeout = (callback, ms) => {
    fakeNow += ms;
    callback();
    return 1;
  };
  let attempts = 0;
  pacingApp.O.http = function () {
    attempts++;
    if (attempts === 1) return Promise.reject(new Error('simulated network failure'));
    return Promise.resolve({ status: 200, text: JSON.stringify({ values: rows.slice().reverse() }) });
  };
  const pacingCfg = { api_key: 'test-key-not-real', outputsize: 5000, min_request_gap_sec: 15 };
  const pacingSym = { name: 'EURUSD', td: 'EUR/USD' };
  const failed = await pacingApp.O.fetchTwelveDataSymbol(pacingSym, pacingCfg, pacingApp.O.CONFIG.history);
  A(failed === null && attempts === 1, 'خطای شبکه باید بدون پرتاب خطا مدیریت شود');
  const afterFailure = fakeNow;
  await pacingApp.O.fetchTwelveDataSymbol(pacingSym, pacingCfg, pacingApp.O.CONFIG.history);
  A(attempts === 2 && fakeNow - afterFailure >= 15000,
    'درخواست ناموفق نیز باید فاصلهٔ ۱۵ ثانیه‌ای درخواست بعدی را اعمال کند');

  console.log('TWELVE DATA TESTS OK — ۱۳ بررسی');
}

main().catch((error) => {
  console.error('TWELVE DATA TESTS FAILED — ' + (error && error.stack || error));
  process.exit(1);
});
