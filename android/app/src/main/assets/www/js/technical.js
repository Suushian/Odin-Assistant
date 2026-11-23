/* موتور تحلیل تکنیکال + قدرت ارزها — پورت src/analysis/technical.py و strength.py
 *
 * md = { h4: [candles], h1: [candles], m15: [candles] }  با candle = {t,o,h,l,c}
 */
(function (O) {
  'use strict';

  O.TREND_FA = { bullish: 'صعودی 📈', bearish: 'نزولی 📉', none: 'نامشخص ❔' };
  O.VERDICT_FA = {
    RANGE: '❌ بازار بی‌روند (رنج) — طبق قوانین، فعلاً سیگنالی صادر نمی‌شود',
    BUY_SETUP: '🟢 شرایط «سیگنال خرید» در حال شکل‌گیری است (تصمیم نهایی با داور)',
    SELL_SETUP: '🔴 شرایط «سیگنال فروش» در حال شکل‌گیری است (تصمیم نهایی با داور)',
    WAIT: '⏳ در انتظار — مدارک کافی برای صدور سیگنال جمع نشده',
    DATA: '⚠️ داده کافی برای تحلیل این نماد در دسترس نیست'
  };
  O.RECOMMENDATION_FA = {
    STRONG_BUY: 'خرید قوی 🟢🟢', BUY: 'خرید 🟢', NEUTRAL: 'خنثی ⚪',
    SELL: 'فروش 🔴', STRONG_SELL: 'فروش قوی 🔴🔴'
  };


  // ══════════════════════════════════════════════════════════
  //  استراتژی‌های چندگانه (نسخهٔ ۱.۱) — پورت src/analysis/strategies.py
  //  هر ستاپ: {key, symbol, direction, quality, entry, stop_ref, reasons_fa}
  //  ⚠️ هر تغییر اینجا باید در پایتون هم اعمال شود (tests/test_strategies.py
  //     و tests/js/test_strategies.js دو باتری آینه‌اند).
  // ══════════════════════════════════════════════════════════
  O.STRATEGY_FA = {
    trend_pullback: 'پولبک در روند',
    range_reversion: 'بازگشت از کف/سقف رنج',
    breakout: 'شکست تازهٔ دامنه'
  };
  O.STRATEGY_PRIORITY = { trend_pullback: 3, breakout: 2, range_reversion: 1 };

  // نسخهٔ ۱.۱.۱ — «قیمت همین حالا» (کلوز آخرین کندل بستهٔ M15). `price` عمداً
  // همان کلوز H1 مانده (برابری بایت‌به‌بایت با ۱.۰)؛ فقط ستاپ‌های مومنتومی از
  // این مرجع استفاده می‌کنند (بک‌تست ۲۰۲۳–۲۰۲۴: شکست با قیمت کهنه −۰٫۱۴R).
  O.ENTRY_AT_MARKET = { breakout: true };
  O.entryAtMarket = function (key) { return !!O.ENTRY_AT_MARKET[key]; };

  function sNum(cfg, key, dflt) {
    var v = cfg ? cfg[key] : undefined;
    if (v === undefined || v === null) return dflt;
    v = +v;
    return Number.isNaN(v) ? dflt : v;
  }

  O.strategyEnabled = function (scfg, key) {
    var block = scfg ? scfg[key] : undefined;
    if (block && typeof block === 'object') return block.enabled !== false;
    if (typeof block === 'boolean') return block;
    return true;
  };

  function g5(v) {
    var t = Number(v).toPrecision(5);
    if (t.indexOf('.') >= 0 && t.indexOf('e') < 0) t = t.replace(/0+$/, '').replace(/\.$/, '');
    return t;
  }
  function f0(v) { return O.faNum(O.pyFixed(v, 0)); }
  function f1(v) { return O.faNum(O.pyFixed(v, 1)); }

  function mkSetup(key, sym, direction, quality, entry, stopRef, reasons) {
    return { key: key, symbol: sym, direction: direction, quality: quality,
      entry: entry, stop_ref: stopRef, reasons_fa: reasons,
      label_fa: O.STRATEGY_FA[key] || key,
      setup_id: sym + '|' + key + '|' + direction };
  }

  O.detectTrendPullback = function (st, sym, acfg, scfg) {
    if (!O.strategyEnabled(scfg, 'trend_pullback')) return null;
    var adxMin = sNum(acfg, 'adx_min_trend', 20);
    var adxStrong = sNum(acfg, 'adx_strong', 25);
    if (st.adx < adxMin || !st.h1_agrees) return null;
    var direction, level, turn, whyRsi;
    if (st.trend === 'bullish' && st.rsi < 45) {
      direction = 'BUY'; level = st.support;
      turn = st.rsi_rising && st.rsi >= 30;
      whyRsi = 'RSI=' + f0(st.rsi) + ' زیر ۴۵ است (ناحیهٔ پولبک)';
    } else if (st.trend === 'bearish' && st.rsi > 55) {
      direction = 'SELL'; level = st.resistance;
      turn = !st.rsi_rising && st.rsi <= 70;
      whyRsi = 'RSI=' + f0(st.rsi) + ' بالای ۵۵ است (ناحیهٔ اصلاح)';
    } else {
      return null;
    }
    var strong = st.adx >= adxStrong;
    var quality = (strong && turn) ? 3 : ((strong || turn) ? 2 : 1);
    var reasons = [
      'روند ۴ ساعته ' + (st.trend === 'bullish' ? 'صعودی' : 'نزولی') +
        ' و تایم‌فریم ۱ ساعته هم‌جهت است',
      'ADX=' + f0(st.adx) + ' → ' + (strong ? 'روند قوی' : 'روند متوسط'),
      whyRsi + (turn ? ' و رو به برگشت است' : ' ولی هنوز تایید برگشت نیامده')
    ];
    return mkSetup('trend_pullback', sym, direction, quality, st.price, level, reasons);
  };

  O.detectRangeReversion = function (st, sym, acfg, scfg) {
    if (!O.strategyEnabled(scfg, 'range_reversion')) return null;
    var block = (scfg && scfg.range_reversion && typeof scfg.range_reversion === 'object')
      ? scfg.range_reversion : {};
    var adxMin = sNum(acfg, 'adx_min_trend', 20);
    if (st.adx >= adxMin || !(st.atr > 0)) return null;
    var band = sNum(block, 'band_atr', 1.0);
    var rsiBuy = sNum(block, 'rsi_buy', 32);
    var rsiSell = sNum(block, 'rsi_sell', 68);

    var best = null;
    if (st.support && st.rsi <= rsiBuy && st.rsi_rising) {
      var d1 = Math.abs(st.price - st.support) / st.atr;
      if (d1 <= band) best = { dist: d1, direction: 'BUY', level: st.support, kind: 'حمایت' };
    }
    if (st.resistance && st.rsi >= rsiSell && !st.rsi_rising) {
      var d2 = Math.abs(st.price - st.resistance) / st.atr;
      if (d2 <= band && (best === null || d2 < best.dist)) {
        best = { dist: d2, direction: 'SELL', level: st.resistance, kind: 'مقاومت' };
      }
    }
    if (best === null) return null;

    var quality = best.dist <= band / 2 ? 3 : 2;
    var sideFa = best.direction === 'BUY' ? 'کف' : 'سقف';
    var reasons = [
      'بازار در فاز رنج است (ADX=' + f0(st.adx) + ' زیر ' + f0(adxMin) +
        ') — معاملهٔ روند در آن معنا ندارد',
      'قیمت ' + f1(best.dist) + ' برابر ATR از ' + best.kind + ' رنج (' + O.faNum(g5(best.level)) +
        ') فاصله دارد',
      best.direction === 'BUY'
        ? 'RSI=' + f0(st.rsi) + ' در اشباع فروش و رو به بالا است — برگشت از ' + sideFa + ' رنج تایید می‌شود'
        : 'RSI=' + f0(st.rsi) + ' در اشباع خرید و رو به پایین است — برگشت از ' + sideFa + ' رنج تایید می‌شود'
    ];
    return mkSetup('range_reversion', sym, best.direction, quality, st.price, best.level, reasons);
  };

  O.detectBreakout = function (st, sym, acfg, scfg) {
    if (!O.strategyEnabled(scfg, 'breakout')) return null;
    var block = (scfg && scfg.breakout && typeof scfg.breakout === 'object') ? scfg.breakout : {};
    if (!(st.atr > 0) || !(st.range_high > 0) || !(st.range_low > 0)) return null;
    if (st.adx < sNum(block, 'adx_min', 20)) return null;
    var bufMult = sNum(block, 'buffer_atr', 0.25);
    var buf = bufMult * st.atr;
    var strong = st.adx >= sNum(acfg, 'adx_strong', 25);

    var direction = '', level = null;
    if (st.price > st.range_high + buf && st.prev_close <= st.prev_range_high + buf) {
      direction = 'BUY'; level = st.range_high;
    } else if (st.price < st.range_low - buf && st.prev_close >= st.prev_range_low - buf) {
      direction = 'SELL'; level = st.range_low;
    }
    if (!direction) return null;

    var quality = (strong && st.h1_agrees) ? 3 : ((strong || st.h1_agrees) ? 2 : 1);
    var sideFa = direction === 'BUY' ? 'سقف' : 'کف';
    var edge = direction === 'BUY' ? st.range_high : st.range_low;
    var reasons = [
      'قیمت همین کندل از ' + sideFa + ' دامنهٔ ' + O.faNum(g5(edge)) + ' با بافر ' +
        O.faNum(O.pyFixed(bufMult, 2)) + '×ATR بیرون زد',
      'ADX=' + f0(st.adx) + ' → ' + (strong ? 'روند قوی' : 'روند متوسط') +
        ' (شکست بدون روند معمولاً برمی‌گردد)',
      st.h1_agrees ? 'تایم‌فریم ۱ ساعته هم‌جهت است'
        : '⚠️ تایم‌فریم ۱ ساعته هم‌جهت نیست — شکست نیاز به تایید دارد'
    ];
    return mkSetup('breakout', sym, direction, quality, st.price, level, reasons);
  };

  O.buildSetups = function (st, sym, acfg, scfg) {
    var out = [
      O.detectTrendPullback(st, sym, acfg, scfg),
      O.detectRangeReversion(st, sym, acfg, scfg),
      O.detectBreakout(st, sym, acfg, scfg)
    ].filter(function (x) { return x !== null; });
    out.sort(function (a, b) {
      if (b.quality !== a.quality) return b.quality - a.quality;
      return (O.STRATEGY_PRIORITY[b.key] || 0) - (O.STRATEGY_PRIORITY[a.key] || 0);
    });
    return out;
  };

  O.bestSetup = function (setups, scfg) {
    var live = (setups || []).filter(function (s) {
      return !!O.STRATEGY_FA[s.key] && O.strategyEnabled(scfg, s.key);
    });
    if (!live.length) return null;
    var best = live[0];
    for (var i = 1; i < live.length; i++) {
      var cand = live[i];
      var cq = cand.quality, bq = best.quality;
      if (cq > bq || (cq === bq &&
        (O.STRATEGY_PRIORITY[cand.key] || 0) > (O.STRATEGY_PRIORITY[best.key] || 0))) {
        best = cand;
      }
    }
    return best;
  };

  function rangeBounds(h1, scfg) {
    var empty = { range_high: 0, range_low: 0, prev_range_high: 0, prev_range_low: 0, prev_close: 0 };
    var block = (scfg && scfg.breakout && typeof scfg.breakout === 'object') ? scfg.breakout : {};
    var n = parseInt(block.lookback_h1, 10);
    if (Number.isNaN(n)) n = 24;
    n = Math.max(5, Math.min(240, n));
    if (!h1 || h1.length < n + 3) return empty;
    var hi = -Infinity, lo = Infinity, phi = -Infinity, plo = Infinity;
    var win = h1.slice(-(n + 1), -1);
    var prev = h1.slice(-(n + 2), -2);
    win.forEach(function (c) { if (c.h > hi) hi = c.h; if (c.l < lo) lo = c.l; });
    prev.forEach(function (c) { if (c.h > phi) phi = c.h; if (c.l < plo) plo = c.l; });
    return { range_high: hi, range_low: lo, prev_range_high: phi, prev_range_low: plo,
      prev_close: h1[h1.length - 2].c };
  }

  O.analyzeSymbol = function (symCfg, md, acfg, scfg) {
    var emaFastN = acfg.ema_fast | 0;
    var emaSlowN = acfg.ema_slow | 0;
    var adxN = acfg.adx_period | 0;
    var adxMin = +acfg.adx_min_trend;
    var rsiN = acfg.rsi_period | 0;
    var atrN = acfg.atr_period | 0;
    var swingWin = acfg.swing_window | 0;

    var h4 = md.h4, h1 = md.h1, m15 = md.m15;
    var common = {
      symbol: symCfg.name,
      fa_name: symCfg.fa || symCfg.name,
      base: symCfg.base, quote: symCfg.quote,
      pip: +symCfg.pip
    };

    function lastTs(df) { return df && df.length ? new Date(df[df.length - 1].t) : null; }

    // بررسی کفایت داده (دقیقاً مثل دسکتاپ)
    if (h4.length < emaSlowN + 10 || h1.length < emaSlowN + 10 || m15.length < rsiN + 10) {
      return Object.assign(common, {
        price: h1.length ? h1[h1.length - 1].c : 0,
        entry_ref: m15.length ? m15[m15.length - 1].c : 0,
        trend: 'none', h1_agrees: false, adx: 0, rsi: 50, rsi_rising: false,
        atr: 0, support: null, resistance: null,
        last_candle: lastTs(m15), verdict: 'DATA',
        setups: [], strategy: ''
      });
    }

    var price = h1[h1.length - 1].c;

    var closes = function (df) { return df.map(function (x) { return x.c; }); };
    var eFastH4 = O.last(O.ema(closes(h4), emaFastN));
    var eSlowH4 = O.last(O.ema(closes(h4), emaSlowN));
    var trend = eFastH4 > eSlowH4 ? 'bullish' : 'bearish';

    var eFastH1 = O.last(O.ema(closes(h1), emaFastN));
    var eSlowH1 = O.last(O.ema(closes(h1), emaSlowN));
    var h1Bullish = eFastH1 > eSlowH1;
    var h1Agrees = trend === 'bullish' ? h1Bullish : !h1Bullish;

    var adxV = O.last(O.adx(h4, adxN));
    var rsiS = O.rsi(closes(m15), rsiN);
    var rsiV = rsiS[rsiS.length - 1];
    var rsiRising = rsiS[rsiS.length - 1] > rsiS[rsiS.length - 2];
    var atrV = O.last(O.atr(h1, atrN));
    var lv = O.nearestLevels(price, h4, swingWin);

    var verdict;
    if (adxV < adxMin) verdict = 'RANGE';
    else if (trend === 'bullish' && h1Agrees && rsiV < 45) verdict = 'BUY_SETUP';
    else if (trend === 'bearish' && h1Agrees && rsiV > 55) verdict = 'SELL_SETUP';
    else verdict = 'WAIT';

    // ── ستاپ‌های چند-استراتژی (نسخهٔ ۱.۱) ────────────────────
    var bounds = rangeBounds(h1, scfg);
    var st = {
      price: price, trend: trend, h1_agrees: h1Agrees, adx: adxV, rsi: rsiV,
      rsi_rising: rsiRising, atr: atrV, support: lv.support, resistance: lv.resistance,
      range_high: bounds.range_high, range_low: bounds.range_low,
      prev_range_high: bounds.prev_range_high, prev_range_low: bounds.prev_range_low,
      prev_close: bounds.prev_close
    };
    var setups = O.buildSetups(st, symCfg.name, acfg, scfg);

    return Object.assign(common, {
      price: price, trend: trend, h1_agrees: h1Agrees,
      adx: adxV, rsi: rsiV, rsi_rising: rsiRising, atr: atrV,
      support: lv.support, resistance: lv.resistance,
      entry_ref: m15.length ? m15[m15.length - 1].c : 0,
      last_candle: lastTs(m15), verdict: verdict,
      setups: setups, strategy: setups.length ? setups[0].key : ''
    });
  };

  // ── سنجهٔ قدرت ارزها (پورت strength.py) ──────────────────────
  function splitSymbol(name) {
    var clean = name.replace('=X', '').toUpperCase();
    if (clean.length === 6) return [clean.slice(0, 3), clean.slice(3)];
    return [null, null];
  }

  O.currencyStrength = function (datasets, lookbackH1) {
    var changes = {};
    Object.keys(datasets).forEach(function (name) {
      var h1 = datasets[name].h1;
      var close = h1.map(function (x) { return x.c; });
      if (close.length <= lookbackH1) return;
      var pct = (close[close.length - 1] / close[close.length - 1 - lookbackH1] - 1) * 100;
      var sq = splitSymbol(name);
      if (sq[0] === null) return;
      (changes[sq[0]] = changes[sq[0]] || []).push(pct);
      (changes[sq[1]] = changes[sq[1]] || []).push(-pct);
    });
    var avg = Object.keys(changes).map(function (c) {
      var v = changes[c];
      return [c, v.reduce(function (a, b) { return a + b; }, 0) / v.length];
    });
    avg.sort(function (x, y) { return y[1] - x[1]; });
    return avg;
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
