#!/usr/bin/env node
/* میخ‌های رفتاری «چند استراتژی + رده‌بندی + پورتفوی» در موتور JS — نسخهٔ ۱.۱.
 *
 * اجرا:  node tests/js/test_strategies.js      (آفلاین، قطعی، بدون شبکه)
 *
 * آینهٔ tests/test_strategies.py. چون منطق استراتژی‌ها در دو زبان تکرار شده
 * (پایتون برای دسکتاپ، JS برای اندروید)، این دو فایل باید همان سناریوها و
 * همان اعداد را پین کنند تا واگرایی زودتر از انتشار دیده شود.
 *
 * پوشش: buildSetups (پولبک/رنج/شکست تازه/غیرتازه) · bestSetup · رده‌بندی
 * A/B/C و دیده‌بان · قیف سیگنال · سقف روزانه · کلید ضداسپم · اتصال config.js
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..', '..');
const WWW = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www', 'js');

let COUNT = 0;
function A(cond, msg) {
  if (!cond) throw new Error(msg);
  COUNT++;
}

function createVm() {
  const ctx = { console, Date, Math, JSON };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  const files = ['md5.js', 'fa.js', 'icons.js', 'license.js', 'config.js', 'indicators.js',
    'session.js', 'technical.js', 'calendar.js', 'news.js', 'judge.js', 'journal.js'];
  for (const f of files) {
    vm.runInContext(fs.readFileSync(path.join(WWW, f), 'utf8'), ctx, { filename: f });
  }
  return ctx.ODIN;
}

const O = createVm();
const ACFG = { adx_min_trend: 20, adx_strong: 25 };

function st(over) {
  return Object.assign({
    price: 1.1000, trend: 'bullish', h1_agrees: true, adx: 30, rsi: 40, rsi_rising: true,
    atr: 0.0010, support: 1.0995, resistance: 1.1050,
    range_high: 1.1040, range_low: 1.0960,
    prev_range_high: 1.1035, prev_range_low: 1.0965, prev_close: 1.1010
  }, over || {});
}

// ══════════════════════════════════════════════════════════════
function testSetupDetection() {
  let s = O.buildSetups(st(), 'EURUSD', ACFG, {});
  A(s.length === 1 && s[0].key === 'trend_pullback', 'پولبک در روند شناسایی شد');
  A(s[0].direction === 'BUY' && s[0].quality === 3, 'پولبک خرید کیفیت ۳');
  A(s[0].stop_ref === 1.0995, 'سطح مرجع پولبک = حمایت');
  A(s[0].setup_id === 'EURUSD|trend_pullback|BUY', 'setup_id پایدار');
  A(s[0].label_fa === O.STRATEGY_FA.trend_pullback, 'برچسب فارسی استراتژی');

  s = O.buildSetups(st({ rsi_rising: false }), 'EURUSD', ACFG, {});
  A(s.length === 1 && s[0].quality === 2, 'بدون برگشت RSI → کیفیت ۲');

  s = O.buildSetups(st({ trend: 'bearish', rsi: 62, rsi_rising: false }), 'EURUSD', ACFG, {});
  A(s.length === 1 && s[0].direction === 'SELL', 'پولبک فروش آینه‌ای');
  A(s[0].stop_ref === 1.1050, 'سطح مرجع فروش = مقاومت');

  s = O.buildSetups(st({ adx: 14, rsi: 28, price: 1.0996, h1_agrees: false }), 'EURUSD', ACFG, {});
  A(s.length === 1 && s[0].key === 'range_reversion' && s[0].direction === 'BUY',
    'رنج: بازگشت خرید از حمایت');
  A(s[0].quality === 3, 'چسبیده به سطح → کیفیت ۳');

  s = O.buildSetups(st({ adx: 17, rsi: 74, rsi_rising: false, price: 1.1047 }), 'EURUSD', ACFG, {});
  A(s.length === 1 && s[0].key === 'range_reversion' && s[0].direction === 'SELL',
    'رنج: بازگشت فروش از مقاومت');

  s = O.buildSetups(st({ adx: 28, rsi: 62, price: 1.1060, support: 1.1000, resistance: 1.1060,
    range_high: 1.1050, prev_range_high: 1.1048, prev_close: 1.1045 }), 'EURUSD', ACFG, {});
  A(s.length === 1 && s[0].key === 'breakout' && s[0].direction === 'BUY', 'شکست صعودی تازه');
  A(s[0].stop_ref === 1.1050 && s[0].quality === 3, 'لبهٔ شکست + کیفیت ۳');

  s = O.buildSetups(st({ adx: 28, rsi: 62, price: 1.1060, range_high: 1.1050,
    prev_range_high: 1.1055, prev_close: 1.1058 }), 'EURUSD', ACFG, {});
  A(s.length === 0, 'شکست غیرتازه شلیک نمی‌کند (ضد اسپم)');

  s = O.buildSetups(st({ adx: 19, rsi: 62, price: 1.1060, range_high: 1.1050,
    prev_range_high: 1.1048, prev_close: 1.1045 }), 'EURUSD', ACFG, {});
  A(s.length === 0, 'شکست با ADX کم رد می‌شود');

  A(O.strategyEnabled({ breakout: false }, 'breakout') === false, 'شکل کوتاه خاموشی');
  A(O.strategyEnabled({ breakout: { enabled: false } }, 'breakout') === false, 'شکل کامل خاموشی');
  A(O.strategyEnabled({}, 'breakout') === true, 'نبود کلید = روشن');
  A(O.buildSetups(st(), 'EURUSD', ACFG, { trend_pullback: { enabled: false } }).length === 0,
    'خاموش‌کردن پولبک → بی‌ستاپ');
}

// ══════════════════════════════════════════════════════════════
function testBestSetup() {
  const S = (key, quality, direction) => ({ key, quality, direction: direction || 'BUY' });
  A(O.bestSetup([S('range_reversion', 3), S('trend_pullback', 2)], {}).key === 'range_reversion',
    'کیفیت بالاتر برنده');
  A(O.bestSetup([S('range_reversion', 3), S('trend_pullback', 3)], {}).key === 'trend_pullback',
    'کیفیت برابر → اولویت پولبک');
  A(O.bestSetup([S('trend_pullback', 3)], { trend_pullback: false }) === null,
    'ستاپ استراتژی خاموش نادیده گرفته می‌شود');
  A(O.bestSetup([], {}) === null && O.bestSetup(null, {}) === null, 'خالی → null');
}

// ══════════════════════════════════════════════════════════════
function makeCtx(jover, nowMs) {
  // مثل هارنس طلایی: jcfg از CONFIG.deepFill شده و بعد override می‌شود
  const jcfg = O.deepFill(JSON.parse(JSON.stringify(O.CONFIG.judge)), jover || {});
  return {
    jcfg: jcfg, acfg: O.CONFIG.analysis, symbolsCfg: O.CONFIG.symbols,
    scfg: {}, ranking: [['EUR', 0.3], ['GBP', 0.1], ['USD', -0.2], ['JPY', -0.4]],
    tvMap: {}, calSnap: null, newsSnap: null, calendarEnabled: false,
    nowMs: nowMs, status: O.marketStatus(new Date(nowMs)), eventVetoMinutes: 30
  };
}

function makeAnalysis(over) {
  return Object.assign({
    symbol: 'EURUSD', fa_name: 'یورو به دلار آمریکا', base: 'EUR', quote: 'USD',
    price: 1.1490, pip: 0.0001, trend: 'bullish', h1_agrees: true, adx: 32, rsi: 38,
    rsi_rising: true, atr: 0.0010, support: 1.1486, resistance: 1.1560,
    last_candle: null, verdict: 'BUY_SETUP', setups: [], strategy: ''
  }, over || {});
}

const TIERS_ON = { tiers: { enabled: true, a_min_score: 7, c_min_score: 4, b_soft_vetoes: 1 } };
const WED = Date.UTC(2026, 8, 23, 14, 0, 0);

function testTiers() {
  let j = O.judgeSymbol(makeAnalysis(), {}, null, makeCtx(TIERS_ON, WED));
  A(!!j.signal, 'امتیاز کامل → سیگنال');
  A(j.tier === 'A' && j.signal.tier === 'A', 'ردهٔ A برای امتیاز بالا و بدون وتوی نرم');

  j = O.judgeSymbol(makeAnalysis({ h1_agrees: false }), {}, null, makeCtx(TIERS_ON, WED));
  A(!!j.signal, 'یک وتوی نرم سیگنال را نمی‌کشد');
  A(j.tier === 'B', 'یک وتوی نرم → ردهٔ B');
  A(j.signal.warnings.some((w) => w.indexOf('ردهٔ B') >= 0), 'هشدار نیمریسک اضافه شد');

  j = O.judgeSymbol(makeAnalysis(), {}, null,
    makeCtx({ tiers: { enabled: true, a_min_score: 12, c_min_score: 4, b_soft_vetoes: 1 } }, WED));
  A(!!j.signal && j.tier === 'B', 'امتیاز زیر a_min_score → B');

  j = O.judgeSymbol(makeAnalysis(), {}, null, makeCtx({
    min_score: 12, tiers: { enabled: true, a_min_score: 7, c_min_score: 6, b_soft_vetoes: 1 }
  }, WED));
  A(!j.signal && j.reject_reason === 'WATCHLIST', 'امتیاز ۱۱ با آستانهٔ ۱۲ → دیده‌بان');
  A(O.judgmentStatusFa(j).indexOf('دیده‌بان') >= 0, 'برچسب فارسی دیده‌بان');

  j = O.judgeSymbol(makeAnalysis(), {}, null, makeCtx({
    min_score: 12, tiers: { enabled: true, a_min_score: 7, c_min_score: 12, b_soft_vetoes: 1 }
  }, WED));
  A(j.reject_reason === 'LOW_SCORE', 'زیر c_min → LOW_SCORE (رفتار قبلی)');

  j = O.judgeSymbol(makeAnalysis(), {}, null,
    makeCtx({ tiers: { enabled: false } }, WED));
  A(!!j.signal && j.tier === '', 'رده‌بندی خاموش → بدون برچسب');
}

// ══════════════════════════════════════════════════════════════
function testStrategyInJudge() {
  // ستاپ رنج: وتوی رنج/تضاد نباید شلیک شود و مدرک روند ۱ از ۲ باشد
  const a = makeAnalysis({ adx: 14, h1_agrees: false, verdict: 'RANGE', rsi: 28, price: 1.0996,
    setups: [{ key: 'range_reversion', symbol: 'EURUSD', direction: 'BUY', quality: 3,
      entry: 1.0996, stop_ref: 1.0995, reasons_fa: [], label_fa: 'بازگشت از کف/سقف رنج',
      setup_id: 'EURUSD|range_reversion|BUY' }] });
  const j = O.judgeSymbol(a, {}, null, makeCtx(TIERS_ON, WED));
  A(!j.vetoes.some((v) => v.key === 'RANGE'), 'وتوی رنج برای ستاپ رنج حذف شد');
  A(!j.vetoes.some((v) => v.key === 'TF_CONFLICT'), 'وتوی تضاد تایم‌فریم استثنا شد');
  A(j.direction === 'BUY' && j.strategy === 'range_reversion', 'جهت از ستاپ گرفت');
  A(j.evidences.some((e) => e.key === 'trend' && e.points === 1), 'مدرک روند ۱ از ۲ (صادقانه)');

  // ستاپ شکست: حد ضرر روی لبهٔ شکست
  const b = makeAnalysis({ verdict: 'WAIT', adx: 28, rsi: 62, price: 1.1060,
    support: 1.1000, resistance: 1.1060,
    setups: [{ key: 'breakout', symbol: 'EURUSD', direction: 'BUY', quality: 3,
      entry: 1.1060, stop_ref: 1.1050, reasons_fa: [], label_fa: 'شکست تازهٔ دامنه',
      setup_id: 'EURUSD|breakout|BUY' }] });
  const jb = O.judgeSymbol(b, {}, null, makeCtx(TIERS_ON, WED));
  A(jb.direction === 'BUY' && jb.strategy === 'breakout', 'جهت از ستاپ شکست');
  A(jb.signal ? (jb.signal.sl >= 1.1040 && jb.signal.sl < 1.1050) : true,
    'حد ضرر شکست زیر لبهٔ 1.1050');

  // نسخهٔ ۱.۱.۱ — قیمت مرجع ورود: شکست با کلوز M15، بقیه با کلوز H1
  A(O.entryAtMarket('breakout') === true, 'شکست: قیمت مرجع لحظه‌ای');
  A(O.entryAtMarket('trend_pullback') === false && O.entryAtMarket('range_reversion') === false,
    'پولبک و رنج: همان کلوز H1');
  const bm = makeAnalysis({ verdict: 'WAIT', adx: 28, rsi: 62, price: 1.1060,
    support: 1.1000, resistance: 1.1060, entry_ref: 1.1075,
    setups: [{ key: 'breakout', symbol: 'EURUSD', direction: 'BUY', quality: 3,
      entry: 1.1075, stop_ref: 1.1050, reasons_fa: [], label_fa: 'شکست تازهٔ دامنه',
      setup_id: 'EURUSD|breakout|BUY' }] });
  const jm = O.judgeSymbol(bm, {}, null, makeCtx(TIERS_ON, WED));
  A(!!jm.signal && Math.abs(jm.signal.entry - 1.1075) < 1e-9, 'ورود شکست از کلوز M15');
  const pm = makeAnalysis({ price: 1.1000, entry_ref: 1.1010,
    setups: [{ key: 'trend_pullback', symbol: 'EURUSD', direction: 'BUY', quality: 3,
      entry: 1.1000, stop_ref: 0.9990, reasons_fa: [], label_fa: 'پولبک در روند',
      setup_id: 'EURUSD|trend_pullback|BUY' }] });
  const jpm = O.judgeSymbol(pm, {}, null, makeCtx(TIERS_ON, WED));
  A(!!jpm.signal && Math.abs(jpm.signal.entry - 1.1000) < 1e-9, 'ورود پولبک همان کلوز H1');

  // نسخهٔ ۱.۲ — نوع سفارش: شکست لیمیت، بقیه بازار
  A(O.limitEntry('breakout') === true, 'شکست: اردر لیمیت');
  A(O.limitEntry('trend_pullback') === false, 'پولبک: ورود بازار');
  const jl = O.judgeSymbol(bm, {}, null, makeCtx(TIERS_ON, WED));
  A(!!jl.signal && jl.signal.order_type === 'limit' &&
    jl.signal.valid_minutes === O.DEFAULT_LIMIT_VALID_MINUTES,
    'سیگنال شکست لیمیت با اعتبار پیش‌فرض');
  A(O.signalToJournal(jl.signal).order_type === 'limit', 'ژورنال نوع سفارش را نگه می‌دارد');
  const jp = O.judgeSymbol(pm, {}, null, makeCtx(TIERS_ON, WED));
  A(!!jp.signal && jp.signal.order_type === 'market' && jp.signal.valid_minutes === 0,
    'سیگنال پولبک: ورود بازار');

  // ستاپ خاموش در ctx → مسیر قدیمی verdict
  const c = makeAnalysis({ setups: [{ key: 'trend_pullback', symbol: 'EURUSD', direction: 'BUY',
    quality: 3, entry: 1.149, stop_ref: 1.1486, reasons_fa: [], label_fa: 'پولبک در روند',
    setup_id: 'EURUSD|trend_pullback|BUY' }] });
  const ctxOff = makeCtx(TIERS_ON, WED);
  ctxOff.scfg = { trend_pullback: { enabled: false } };
  const jc = O.judgeSymbol(c, {}, null, ctxOff);
  A(jc.strategy === '' && jc.direction === 'BUY', 'ستاپ خاموش → مسیر verdict');
}

// ══════════════════════════════════════════════════════════════
function testFunnel() {
  const snap = O.signalFunnel([
    { signal: { symbol: 'EURUSD' }, vetoes: [] },
    { signal: null, reject_reason: 'WATCHLIST', vetoes: [] },
    { signal: null, reject_reason: 'VETO', vetoes: [{ key: 'RANGE' }, { key: 'EVENT' }] },
    { signal: null, reject_reason: 'NO_SETUP', vetoes: [] }
  ]);
  A(snap.total === 4 && snap.signals === 1, 'قیف: شمارش کل و سیگنال');
  A(snap.counts.WATCHLIST === 1 && snap.counts.VETO === 1 && snap.counts.NO_SIGNAL !== 0,
    'قیف: توزیع دلایل');
  A(snap.vetoes.RANGE === 1 && snap.vetoes.EVENT === 1, 'قیف: شمارش وتوها');
  A(snap.line_fa.indexOf('قیف سیگنال') >= 0 && snap.line_fa.indexOf('دیده‌بان') >= 0,
    'قیف: خط فارسی شامل دیده‌بان');
  A(O.signalFunnel([]).line_fa.indexOf('هیچ نمادی داوری نشد') >= 0, 'قیف خالی');

  const day1 = O.funnelMergeDaily({}, snap, Date.UTC(2026, 10, 23, 10, 0, 0));
  const key = '2026-11-23';
  A(day1.days[key].cycles === 1 && day1.days[key].signals === 1, 'سبد روزانه: چرخهٔ اول');
  const day2 = O.funnelMergeDaily(day1, snap, Date.UTC(2026, 10, 23, 12, 0, 0));
  A(day2.days[key].cycles === 2 && day2.days[key].signals === 2, 'سبد روزانه: جمع می‌شود');
  A(day2.days[key].counts.WATCHLIST === 2, 'سبد روزانه: شمارش دلایل جمع می‌شود');
  A(O.funnelDayLine(day2.days[key]).indexOf('۲ سیگنال') >= 0, 'خط روزانه با ارقام فارسی');
}

// ══════════════════════════════════════════════════════════════
function testSpamAndCapacity() {
  const nowMs = Date.UTC(2026, 10, 23, 12, 0, 0);
  const sigA = { symbol: 'EURUSD', direction: 'BUY', score: 9, strategy: 'trend_pullback' };
  const sigB = { symbol: 'EURUSD', direction: 'BUY', score: 9, strategy: 'breakout' };
  A(O.signalStateKey(sigA) === 'EURUSD|trend_pullback|BUY', 'کلید ضداسپم شامل استراتژی');
  A(O.signalStateKey({ symbol: 'EURUSD', direction: 'SELL' }) === 'EURUSD|SELL',
    'سیگنال بدون استراتژی → قالب قدیمی');

  const state = {};
  const before = O.shouldSendSignal(state, sigA, O.CONFIG.judge, nowMs);
  A(before.go === true, 'بار اول ارسال می‌شود');
  state[O.signalStateKey(sigA)] = { ts: new Date(nowMs).toISOString(), score: 9 };
  A(O.shouldSendSignal(state, sigA, O.CONFIG.judge, nowMs + 15 * 60000).go === false,
    'همان ستاپ در cooldown → ارسال نمی‌شود');
  A(O.shouldSendSignal(state, sigB, O.CONFIG.judge, nowMs + 15 * 60000).go === true,
    'ستاپ دیگر روی همان نماد در cooldown نیست');

  const today = O.signalCountsToday(state, nowMs);
  A(today.total === 1 && today.by_symbol.EURUSD === 1, 'شمارش امروز بر اساس کلید');
  A(O.dailyCapBlock({ symbol: 'EURUSD' }, today, { max_per_symbol_per_day: 1 })
    .indexOf('سقف') >= 0, 'سقف روزانهٔ هر نماد اعمال می‌شود');
  A(O.dailyCapBlock({ symbol: 'GBPUSD' }, today, { max_per_symbol_per_day: 1 }) === '',
    'نماد دیگر بلوکه نیست');
  A(O.dailyCapBlock({ symbol: 'GBPUSD' }, { total: 8, by_symbol: {} },
    { max_signals_per_day: 8 }).indexOf('سقف') >= 0, 'سقف کل روز اعمال می‌شود');
  A(O.dailyCapBlock({ symbol: 'GBPUSD' }, today, {}) === '', 'سقف صفر/نبود = بدون محدودیت');

  // صندلی ظرفیت: فقط سیگنالِ ارسال‌شده صندلی می‌گیرد (باگِ کشف‌شده در بک‌تست)
  let cs = { actionable: true, capacity_note: '' };
  A(O.applyCapacity(cs, true, 2, true, 2) === 1 && cs.actionable === true,
    'سیگنالِ ارسال‌شده صندلی می‌گیرد');
  cs = { actionable: true, capacity_note: '' };
  A(O.applyCapacity(cs, false, 2, true, 2) === 2 && cs.actionable === false,
    'سیگنالِ سرکوب‌شده (cooldown) صندلی نمی‌گیرد');
  cs = { actionable: true, capacity_note: '' };
  A(O.applyCapacity(cs, true, 0, true, 2) === 0 && cs.actionable === false &&
    cs.capacity_note.indexOf('پوزیشن باز پر است') >= 0, 'صندلی تمام‌شده → «فقط پیگیری»');
  cs = { actionable: true, capacity_note: '' };
  A(O.applyCapacity(cs, true, 0, false, 0) === 0 && cs.actionable === true,
    'ظرفیت خاموش → دست‌نخورده');
}

// ══════════════════════════════════════════════════════════════
function testConfigWiring() {
  const cfg = O.CONFIG;
  A(cfg.symbols.length === 10, 'ده نماد در config اندروید');
  const names = cfg.symbols.map((s) => s.name);
  A(names.indexOf('EURJPY') >= 0 && names.indexOf('EURGBP') >= 0, 'کراس‌های یورو موجودند');
  A(cfg.judge.min_score === 5, 'min_score همان ۵ ماند');
  A(cfg.judge.tiers && cfg.judge.tiers.enabled === true, 'رده‌بندی روشن است');
  A(cfg.judge.portfolio.max_open_positions === 2, 'سقف دو پوزیشن باز');
  A(cfg.judge.funnel && cfg.judge.funnel.enabled === true, 'قیف سیگنال روشن است');
  A(cfg.strategies.trend_pullback.enabled === true &&
    cfg.strategies.range_reversion.enabled === true &&
    cfg.strategies.breakout.enabled === true, 'هر سه استراتژی روشن‌اند');
  A(cfg.judge.resend_cooldown_minutes === 90, 'cooldown ۹۰ دقیقه');
  A(cfg.journal.expiry_hours === 72, 'انقضای ژورنال ۳ روز (نتیجهٔ مطالعهٔ خروج)');
}

// ══════════════════════════════════════════════════════════════
//  v1.6.0 — دروازهٔ استراتژی (آینهٔ tests/test_signal_quality.py)
// ══════════════════════════════════════════════════════════════
function testStrategyGate() {
  const G = (inner) => makeCtx({ strategy_gate: Object.assign({ enabled: true }, inner || {}) }, WED);

  // ۱) پیش‌فرض خاموش = رفتار قبلی
  const offGate = O.strategyGate({ strategy_gate: { enabled: false } }, 'breakout');
  A(offGate.on === false && offGate.allowed === true && offGate.min_score === 0,
    'پیش‌فرض: دروازه خاموش، ستاپ مجاز، آستانهٔ اضافه صفر');
  A(O.strategyGate({}, 'breakout').on === false, 'نبودِ کلید config = خاموش');

  // ۲) سه حالت روشن
  const g = { strategy_gate: { enabled: true,
    breakout: { enabled: false }, range_reversion: { min_score: 8 },
    trend_pullback: { min_score: '6' } } };
  A(O.strategyGate(g, 'breakout').allowed === false, 'ستاپ خاموش → allowed=false');
  A(O.strategyGate(g, 'range_reversion').min_score === 8, 'min_score عددی');
  A(O.strategyGate(g, 'trend_pullback').min_score === 6, 'min_score رشته‌ای');
  A(O.strategyGate(g, 'nope').allowed === true, 'ستاپ ناشناخته = بی‌تغییر');
  A(O.strategyGate({ strategy_gate: { enabled: true, breakout: { min_score: 'x' } } },
    'breakout').min_score === 0, 'min_score نامعتبر → بی‌اثر');

  // ۳) مسیر داوری: ستاپ با کیفیت بالا که پیش‌فرض سیگنال می‌دهد
  const withSetup = (key) => makeAnalysis({ setups: [{ key: key, quality: 3, direction: 'BUY' }] });

  let j = O.judgeSymbol(withSetup('range_reversion'), {}, null, makeCtx({}, WED));
  A(!!j.signal && j.reject_reason === '', 'دروازهٔ خاموش: سیگنال مثل قبل صادر می‌شود');
  const baseScore = j.score;

  j = O.judgeSymbol(withSetup('range_reversion'), {}, null,
    G({ range_reversion: { enabled: false } }));
  A(!j.signal && j.reject_reason === 'STRATEGY_OFF', 'ستاپ خاموش → STRATEGY_OFF');
  A(j.reject_detail.indexOf('بازگشت از کف/سقف رنج') >= 0, 'متن رد، نام فارسی ستاپ را دارد');
  A(j.reject_detail.indexOf(O.faNum(baseScore)) >= 0, 'متن رد، امتیاز همان ستاپ را دارد');
  A(O.judgmentStatusFa(j).indexOf('⛔') === 0, 'برچسب وضعیت برای ستاپ خاموش');

  // رده‌بندی عمداً خاموش است تا دلیل دقیقاً LOW_SCORE باشد (وگرنه دیده‌بان می‌شود)
  j = O.judgeSymbol(withSetup('range_reversion'), {}, null,
    makeCtx({ tiers: { enabled: false },
              strategy_gate: { enabled: true, range_reversion: { min_score: 12 } } }, WED));
  A(!j.signal && j.reject_reason === 'LOW_SCORE', 'آستانهٔ ۱۲ برای ستاپ → LOW_SCORE');
  A(j.reject_detail.indexOf(O.faNum(12)) >= 0, 'متن LOW_SCORE آستانهٔ مؤثر را نشان می‌دهد');

  j = O.judgeSymbol(withSetup('range_reversion'), {}, null,
    G({ range_reversion: { min_score: 5 } }));
  A(!!j.signal, 'آستانهٔ ۵ = عمومی → سیگنال صادر می‌شود');

  j = O.judgeSymbol(withSetup('trend_pullback'), {}, null,
    G({ range_reversion: { enabled: false } }));
  A(!!j.signal, 'خاموش‌کردن یک ستاپ، ستاپ دیگر را نمی‌بندد');

  // ۴) قیف باید دلیل تازه را بشمارد
  A(O.SIGNAL_REASON_ORDER.indexOf('STRATEGY_OFF') >= 0, 'STRATEGY_OFF در ترتیب قیف هست');
  A(!!O.SIGNAL_REASON_FA.STRATEGY_OFF, 'برچسب فارسی STRATEGY_OFF تعریف شده');
}


// ══════════════════════════════════════════════════════════════
//  v1.6.4 — دروازهٔ نماد (D2) — آینهٔ tests/test_signal_quality.py
// ══════════════════════════════════════════════════════════════
function testSymbolGate() {
  const SG = (inner) => makeCtx({ symbol_gate: Object.assign({ enabled: true }, inner || {}) }, WED);

  // ۱) پیش‌فرض خاموش
  const off = O.symbolGate({ symbol_gate: { enabled: false } }, 'GBPUSD');
  A(off.on === false && off.allowed === true && off.min_score === 0,
    'دروازهٔ نماد خاموش → بی‌اثر');
  A(O.symbolGate({}, 'GBPUSD').on === false, 'نبودِ کلید config = خاموش');

  // ۲) سه حالت
  const g = { symbol_gate: { enabled: true, GBPUSD: { enabled: false },
    XAUUSD: { min_score: 9 }, EURJPY: { min_score: '7' } } };
  A(O.symbolGate(g, 'GBPUSD').allowed === false, 'نماد خاموش → allowed=false');
  A(O.symbolGate(g, 'XAUUSD').min_score === 9, 'min_score عددی');
  A(O.symbolGate(g, 'EURJPY').min_score === 7, 'min_score رشته‌ای');
  A(O.symbolGate(g, 'EURUSD').allowed === true, 'نماد دیگر دست‌نخورده');
  A(O.symbolGate({ symbol_gate: { enabled: true, EURUSD: { min_score: 'x' } } },
    'EURUSD').min_score === 0, 'min_score نامعتبر → بی‌اثر');

  // ۳) مسیر داوری — همان سیگنال پایه
  const a = () => makeAnalysis({ setups: [{ key: 'range_reversion', quality: 3, direction: 'BUY' }] });
  let j = O.judgeSymbol(a(), {}, null, makeCtx({}, WED));
  A(!!j.signal, 'دروازهٔ خاموش: سیگنال صادر می‌شود');
  const score = j.score;
  const sym = j.symbol;

  j = O.judgeSymbol(a(), {}, null, SG({ [sym]: { enabled: false } }));
  A(!j.signal && j.reject_reason === 'SYMBOL_OFF', 'نماد خاموش → SYMBOL_OFF');
  A(j.reject_detail.indexOf(O.faNum(score)) >= 0, 'متن رد، امتیاز را دارد');
  A(j.reject_detail.length > 20, 'متن رد کامل است (بریده نیست)');
  A(O.judgmentStatusFa(j).indexOf('⛔') === 0, 'برچسب وضعیت برای نماد خاموش');

  j = O.judgeSymbol(a(), {}, null,
    makeCtx({ tiers: { enabled: false }, symbol_gate: { enabled: true, [sym]: { min_score: 12 } } }, WED));
  A(!j.signal && j.reject_reason === 'LOW_SCORE', 'آستانهٔ ۱۲ نماد → LOW_SCORE');
  A(j.reject_detail.indexOf(O.faNum(12)) >= 0, 'متن LOW_SCORE آستانهٔ مؤثر نماد را دارد');

  j = O.judgeSymbol(a(), {}, null, SG({ [sym]: { min_score: 5 } }));
  A(!!j.signal, 'آستانهٔ ۵ = عمومی → سیگنال صادر می‌شود');

  // ۴) هر دو دروازه با هم: ستاپ خاموش زودتر گزارش می‌شود
  j = O.judgeSymbol(a(), {}, null,
    makeCtx({ strategy_gate: { enabled: true, range_reversion: { enabled: false } },
              symbol_gate: { enabled: true, [sym]: { enabled: false } } }, WED));
  A(j.reject_reason === 'STRATEGY_OFF', 'وقتی هر دو خاموش‌اند، دلیل ستاپ اولویت دارد');

  // ۵) قیف
  A(O.SIGNAL_REASON_ORDER.indexOf('SYMBOL_OFF') >= 0, 'SYMBOL_OFF در ترتیب قیف هست');
  A(!!O.SIGNAL_REASON_FA.SYMBOL_OFF, 'برچسب فارسی SYMBOL_OFF تعریف شده');
  A(O.SIGNAL_REASON_ORDER.indexOf('SYMBOL_OFF') > O.SIGNAL_REASON_ORDER.indexOf('STRATEGY_OFF'),
    'ترتیب: ستاپ قبل از نماد');
}


// ══════════════════════════════════════════════════════════════
testSetupDetection();
testBestSetup();
testTiers();
testStrategyInJudge();
testStrategyGate();
  testSymbolGate();
testFunnel();
testSpamAndCapacity();
testConfigWiring();

console.log('✅ STRATEGY TESTS (JS) OK — ' + COUNT +
  ' بررسی پاس؛ سه استراتژی + رده‌بندی + دروازهٔ استراتژی + قیف + سقف پوزیشن/روز در موتور اندروید سبز است');
