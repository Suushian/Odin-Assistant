/* Regression tests for Android journal tracker/statistics (offline). */
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert');

const root = path.join(__dirname, '..', '..');
const journalPath = path.join(root, 'android', 'app', 'src', 'main', 'assets', 'www', 'js', 'journal.js');
const ctx = { console };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(journalPath, 'utf8'), ctx, { filename: 'journal.js' });
const O = ctx.ODIN;

const now = Date.parse('2026-10-13T12:00:00Z');
const priorEntry = {
  id: 'old', ts: Date.parse('2026-09-01T12:00:00Z'),
  outcome_ts: Date.parse('2026-10-12T12:00:00Z'),
  symbol: 'EURUSD', direction: 'BUY', score: 10, outcome: O.TP, r: 2,
  evidences: []
};
const stats = O.computeStats([priorEntry], now);
assert.strictEqual(stats.this_week_key, O.isoWeekKey(now));
assert.strictEqual(stats.last_week_key, O.isoWeekKey(now - 7 * 86400000));
assert.strictEqual(stats.by_score['۱۰–۱۱'].closed, 1);
assert.strictEqual(stats.by_week[O.isoWeekKey(now)].closed, 1);
assert.strictEqual(stats.by_week[O.isoWeekKey(priorEntry.ts)], undefined);

const entry = {
  id: 'signal-1', ts: Date.parse('2026-10-13T10:00:00Z'),
  symbol: 'EURUSD', direction: 'BUY', entry: 1.35, sl: 1.348, tp: 1.354,
  rr: 2, risk_pips: 20, pip: 0.0001, outcome: null
};
const candles = [
  { t: entry.ts - 15 * 60000, h: 1.355, l: 1.347, c: 1.35 }, // pre-signal: both
  { t: entry.ts + 15 * 60000, h: 1.352, l: 1.3475, c: 1.348 }, // first exit: SL only
  { t: entry.ts + 30 * 60000, h: 1.355, l: 1.347, c: 1.350 } // later both, irrelevant
];
let stored = null;
const journal = {
  openEntries: () => [entry],
  addOutcome: (_id, outcome, closePrice, r, note, ts) => { stored = { outcome, closePrice, r, note, ts }; }
};
const resolved = O.resolveOpenSignals(journal, { EURUSD: { m15: candles } },
  entry.ts + 45 * 60000, { journal: { enabled: true, conservative_both_touch: true } });
assert.strictEqual(resolved.length, 1);
assert.strictEqual(stored.outcome, O.SL);
assert.strictEqual(stored.note, '');

// storage.append (پل نیتیو اتمیک) باید همان نتیجهٔ set را بدهد و سقف نرم کار کند.
{
  const mem = {};
  const storage = {
    get: (k) => mem[k] || '',
    set: (k, v) => { mem[k] = String(v); },
    append: (k, v) => { mem[k] = (mem[k] || '') + String(v); },
    del: (k) => { delete mem[k]; }
  };
  const j = new O.Journal(storage);
  j.appendRec({ id: 'a', kind: 'signal' });
  j.appendRec({ id: 'b', kind: 'signal' });
  assert.strictEqual(j.load().length, 2);
  assert.ok(/\n$/.test(j.raw()), 'هر رکورد باید با newline تمام شود');
  const oldMax = O.Journal.MAX_BYTES;
  O.Journal.MAX_BYTES = 160;
  for (let i = 0; i < 10; i++) j.appendRec({ id: 'x' + i, note: 'x'.repeat(20) });
  assert.ok(j.raw().length <= 400, 'ژورنال باید پس از عبور از سقف چرخش کند');
  O.Journal.MAX_BYTES = oldMax;
  console.log('    ✓ journal append + soft rotation');
}

console.log('SMOKE JOURNAL OK — calendar weeks, score bucket, first-exit double-touch, append/rotation');
