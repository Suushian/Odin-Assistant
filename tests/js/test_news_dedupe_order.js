/* Regression: news deduplication must follow configured feed order, not response timing. */
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert');

const root = path.resolve(__dirname, '..', '..');
const source = path.join(root, 'android', 'app', 'src', 'main', 'assets', 'www', 'js', 'data.js');
const O = { CONFIG: { news: { feeds: [] } }, faNum: n => String(n) };
const ctx = {
  console, Date, Map, Promise, URL, Uint8Array, TextDecoder, setTimeout,
  ODIN: O, fetch: () => Promise.reject(new Error('offline'))
};
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(source, 'utf8'), ctx, { filename: 'data.js' });

// Keep the test focused on fetch completion order and duplicate selection.
O.parseFeedXml = text => [{ raw: text }];
O.parseEntries = (entries, sourceName, weight, nowMs) => [{
  title: 'same story',
  source: sourceName,
  score: weight >= 2 ? 6 : 4,
  published: nowMs - 60000,
  age_minutes: 1,
  direction: { USD: 1 }
}];
O.dedupeKey = title => String(title).toLowerCase();
O.http = url => new Promise(resolve => {
  const delay = url.endsWith('/first') ? 40 : 0;
  setTimeout(() => resolve({ status: 200, text: url }), delay);
});

(async function main() {
  const snap = await O.fetchNews({
    news: {
      enabled: true,
      feeds: [
        { name: 'first', url: 'https://example.test/first', weight: 1 },
        { name: 'second', url: 'https://example.test/second', weight: 2 }
      ],
      max_age_hours: 30,
      min_score: 2,
      max_items_per_feed: 12,
      max_total: 18
    }
  }, () => {});

  assert.strictEqual(snap.items.length, 1, 'duplicate headline is retained only once');
  assert.strictEqual(snap.items[0].source, 'first',
    'configured first feed wins even if its HTTP response arrives later');
  assert.strictEqual(snap.items[0].score, 4,
    'deduplication choice must not change with network response timing');
  assert.strictEqual(snap.feedsOk, 2);
  assert.strictEqual(snap.feedsFailed, 0);
  console.log('news dedupe ordering tests passed (5 assertions).');
})().catch(err => {
  console.error(err);
  process.exitCode = 1;
});
