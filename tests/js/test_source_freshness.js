/* تست برچسب تازگی منابع — فقط از وضعیت واقعی snapshot استفاده می‌شود. */
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert');

const root = path.resolve(__dirname, '..', '..');
const uiPath = path.join(root, 'android', 'app', 'src', 'main', 'assets', 'www', 'js', 'ui.js');
const O = { faNum: (n) => String(n), ico: () => '', icoStr: (s) => s, CONFIG: {} };
const ctx = { console, URL, Date, ODIN: O };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(uiPath, 'utf8'), ctx, { filename: 'ui.js' });

const now = Date.now();
const recent = now - 10 * 60 * 1000;
const label = O.sourceFreshnessLabel;
assert.strictEqual(label('calendar', null, now), 'هنوز دریافت نشده');
assert.strictEqual(label('calendar', { ok: true, fetchedAt: recent }, now), 'دریافت زنده · 10 دقیقه پیش');
assert.strictEqual(label('calendar', { ok: true, stale: true, fetchedAt: recent }, now), 'دادهٔ کهنه · 10 دقیقه پیش');
assert.strictEqual(label('calendar', { ok: true, fromCache: true, fetchedAt: recent }, now), 'کش · 10 دقیقه پیش');
assert.strictEqual(label('calendar', { ok: false, error: 'network' }, now), 'ناموجود');
assert.strictEqual(label('news', { feedsOk: 0, feedsFailed: 5, fetchedAt: recent }, now), 'دریافت ناموفق');
assert.strictEqual(label('news', { feedsOk: 3, feedsFailed: 2, ok: true, fetchedAt: recent }, now), 'ناقص (2 فید ناموفق) · 10 دقیقه پیش');
assert.strictEqual(label('news', { feedsOk: 5, feedsFailed: 0, ok: true, fetchedAt: recent }, now), 'دریافت موفق · 10 دقیقه پیش');
assert.strictEqual(label('news', { feedsOk: 5, feedsFailed: 0, ok: false, fetchedAt: recent }, now), 'خبر مرتبطی پیدا نشد · 10 دقیقه پیش');
console.log('source freshness tests passed (9 assertions).');
