/* لایهٔ داده — HTTP (پل نیتیو یا fetch)، Twelve Data، تریدینگ‌ویو،
 * تقویم اقتصادی و اخبار + ارکستراسیون کل چرخهٔ تحلیل.
 *
 * ⚠️ همهٔ توابع «هرگز استثنا پرتاب نمی‌کنند» — در بدترین حالت دادهٔ
 *    unavailable برمی‌گردد تا داور صادقانه ۰ امتیاز بدهد (حلقهٔ صداقت).
 */
(function (O) {
  'use strict';

  // ── HTTP ────────────────────────────────────────────────────
  var cbSeq = 1;
  var pending = {};

  O.httpDone = function (cbId, status, b64) {
    var p = pending[cbId];
    if (!p) return;
    delete pending[cbId];
    var text = '';
    try {
      if (b64) {
        var bin = atob(b64);
        var bytes = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        text = new TextDecoder('utf-8').decode(bytes);
      }
    } catch (e) { text = ''; }
    p({ status: status, text: text });
  };

  O.http = function (url, opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      try {
        if (typeof ODINNative !== 'undefined' && ODINNative.http) {
          var id = cbSeq++;
          pending[id] = resolve;
          ODINNative.http(id, url, opts.method || 'GET', opts.body || '', opts.contentType || 'application/json');
          return;
        }
      } catch (e) { /* fallback */ }
      // محیط مرورگر/Node (توسعه و تست) — بدون پل نیتیو
      try {
        var init = { method: opts.method || 'GET', headers: { 'Accept': '*/*' } };
        if (opts.body) {
          init.body = opts.body;
          init.headers['Content-Type'] = opts.contentType || 'application/json';
        }
        fetch(url, init).then(function (r) {
          return r.text().then(function (t) { resolve({ status: r.status, text: t }); });
        }).catch(function (e) { resolve({ status: -1, text: String(e && e.message || e) }); });
      } catch (e2) {
        resolve({ status: -1, text: String(e2 && e2.message || e2) });
      }
    });
  };

  // ── حافظهٔ محلی ─────────────────────────────────────────────
  O.makeStorage = function () {
    if (typeof ODINNative !== 'undefined' && ODINNative.getPref) {
      return {
        get: function (k) { try { return ODINNative.getPref(k) || ''; } catch (e) { return ''; } },
        set: function (k, v) { try { ODINNative.setPref(k, v == null ? '' : String(v)); } catch (e) { } },
        del: function (k) { try { ODINNative.removePref(k); } catch (e) { } }
      };
    }
    var mem = {};
    return {
      get: function (k) { return mem[k] || ''; },
      set: function (k, v) { mem[k] = String(v); },
      del: function (k) { delete mem[k]; }
    };
  };

  // ── Twelve Data: یک درخواست M15 برای هر نماد، سپس resample به H1/H4 ──
  // سهمیهٔ Basic رایگان: حداکثر ۸ اعتبار/دقیقه؛ درخواست‌ها را صف می‌کنیم تا
  // چرخهٔ ۸ نمادی از rate limit عبور نکند. فاصلهٔ ۱۵ ثانیه‌ای همچنین در حالتی
  // که UI و WebView سرویس هم‌زمان فعال‌اند، ریسک burst را کاهش می‌دهد.
  var tdQueue = Promise.resolve();
  var tdLastRequestAt = 0;
  var tdErrors = {};

  function requestTwelveData(url, gapMs) {
    var task = tdQueue.then(function () {
      var wait = Math.max(0, gapMs - (Date.now() - tdLastRequestAt));
      return new Promise(function (resolve) {
        if (wait > 0) setTimeout(resolve, wait);
        else resolve();
      });
    }).then(function () {
      // Count the attempt before network I/O: rejected requests must still consume
      // the pacing interval, otherwise a transient outage can trigger a burst.
      tdLastRequestAt = Date.now();
      return O.http(url);
    });
    tdQueue = task.then(function () { }, function () { });
    return task;
  }

  function parseTwelveDataTime(value) {
    var s = String(value || '').trim().replace(' ', 'T');
    if (!s) return NaN;
    if (!/(Z|[+-]\d{2}:?\d{2})$/i.test(s)) s += 'Z';
    return Date.parse(s);
  }

  function resampleM15(rows, minutes) {
    var frameMs = minutes * 60000;
    var countNeeded = minutes / 15;
    var buckets = {};
    rows.forEach(function (x) {
      var key = Math.floor(x.t / frameMs);
      var b = buckets[key];
      if (!b) {
        buckets[key] = { t: key * frameMs, o: x.o, h: x.h, l: x.l, c: x.c, n: 1, first: x.t, last: x.t };
      } else {
        if (x.h > b.h) b.h = x.h;
        if (x.l < b.l) b.l = x.l;
        b.c = x.c;
        b.n++;
        b.last = x.t;
      }
    });
    return Object.keys(buckets).map(function (k) { return buckets[k]; })
      .filter(function (b) {
        // کندل ناقص را به‌عنوان H1/H4 کامل جا نزن؛ تمام بازه‌های ۱۵ دقیقه‌ای
        // باید موجود و پیوسته باشند و از مرز UTC دقیق شروع شوند.
        return b.n === countNeeded && b.first === b.t &&
          b.last === b.t + frameMs - 15 * 60000;
      })
      .map(function (b) { return { t: b.t, o: b.o, h: b.h, l: b.l, c: b.c }; })
      .sort(function (a, b) { return a.t - b.t; });
  }

  O.fetchTwelveDataSymbol = function (symCfg, tdCfg, hcfg) {
    tdCfg = tdCfg || {};
    hcfg = hcfg || {};
    var key = String(tdCfg.api_key || '').trim();
    var symbol = String(symCfg.td || '').trim();
    // 4500 leaves headroom above the validated 210 H4 / 250 H1 minimums while
    // trimming 10% of the provider payload and JS parsing/allocation work.
    var outputsize = Math.max(4000, Math.min(5000, (tdCfg.outputsize | 0) || 4500));
    var gapMs = Math.max(15000, (+tdCfg.min_request_gap_sec || 15) * 1000);
    var dropForming = hcfg.drop_forming_candle !== false;
    tdErrors[symCfg.name] = '';

    if (!key) {
      tdErrors[symCfg.name] = 'کلید API رایگان Twelve Data را در تنظیمات وارد کنید';
      return Promise.resolve(null);
    }
    if (!symbol) {
      tdErrors[symCfg.name] = 'نماد Twelve Data در پیکربندی تعریف نشده است';
      return Promise.resolve(null);
    }

    var url = 'https://api.twelvedata.com/time_series?symbol=' + encodeURIComponent(symbol) +
      '&interval=15min&outputsize=' + outputsize + '&timezone=UTC&apikey=' + encodeURIComponent(key);

    return requestTwelveData(url, gapMs).then(function (r) {
      var payload;
      try { payload = JSON.parse((r && r.text) || '{}'); }
      catch (e) {
        tdErrors[symCfg.name] = 'پاسخ Twelve Data قابل‌خواندن نیست';
        return null;
      }
      if (!r || r.status !== 200 || !payload || !Array.isArray(payload.values)) {
        // متن خطا را نمایش می‌دهیم، اما هرگز URL یا کلید API را وارد لاگ نمی‌کنیم.
        tdErrors[symCfg.name] = String((payload && (payload.message || payload.status)) ||
          ('HTTP ' + (r ? r.status : 'نامشخص'))).slice(0, 160);
        return null;
      }

      var rows = [];
      // Provider values arrive newest-first. Walk backwards instead of
      // slice().reverse() so we do not allocate a second 4,500-item array.
      for (var vi = payload.values.length - 1; vi >= 0; vi--) {
        var v = payload.values[vi];
        var t = parseTwelveDataTime(v && v.datetime);
        var o = Number(v && v.open), h = Number(v && v.high);
        var l = Number(v && v.low), close = Number(v && v.close);
        if (!Number.isFinite(t) || !Number.isFinite(o) || !Number.isFinite(h) ||
            !Number.isFinite(l) || !Number.isFinite(close)) continue;
        rows.push({ t: t, o: o, h: h, l: l, c: close });
      }
      var now = Date.now();
      if (dropForming) {
        rows = rows.filter(function (x) { return x.t + 15 * 60000 <= now; });
      }
      var m15 = rows;
      var h1 = resampleM15(m15, 60);
      var h4 = resampleM15(m15, 240);
      if (m15.length < 50 || h1.length < 250 || h4.length < 210) {
        tdErrors[symCfg.name] = 'تاریخچهٔ کافی نیست (M15=' + m15.length +
          '، H1=' + h1.length + '، H4=' + h4.length + ')؛ نماد/دسترسی پلن را بررسی کنید';
        return null;
      }
      var md = { symbol: symCfg.name, m15: m15, h1: h1, h4: h4 };
      var problems = O.validateMarketData(md, now);
      if (problems.length) {
        tdErrors[symCfg.name] = problems.slice(0, 3).join('؛ ');
        return null;
      }
      return md;
    }).catch(function (e) {
      tdErrors[symCfg.name] = String(e && e.message || 'خطای شبکه').slice(0, 160);
      return null;
    });
  };

  O.twelveDataErrorFor = function (symbol) {
    return tdErrors[symbol] || '';
  };

  // اعتبارسنجی کندل‌ها پیش از ورود به تحلیل؛ مستقل از ظاهر شدن خطا در UI.
  O.validateMarketData = function (md, nowMs) {
    var errors = [];
    if (!md) return ['داده‌ای دریافت نشد'];
    var now = (typeof nowMs === 'number') ? nowMs : Date.now();
    var d = new Date(now);
    var weekday = d.getUTCDay(); // Sunday=0
    var minute = d.getUTCHours() * 60 + d.getUTCMinutes();
    var marketOpen = !(weekday === 6 || (weekday === 5 && minute >= 1260) ||
      (weekday === 0 && minute < 1260));
    var frames = [
      { name: 'M15', key: 'm15', min: 50, interval: 15 * 60000, maxAge: 45 * 60000, maxGap: 60 * 60000 },
      { name: 'H1', key: 'h1', min: 250, interval: 60 * 60000, maxAge: 90 * 60000, maxGap: 3 * 60 * 60000 },
      { name: 'H4', key: 'h4', min: 210, interval: 4 * 60 * 60000, maxAge: null }
    ];
    frames.forEach(function (spec) {
      var rows = md[spec.key];
      if (!Array.isArray(rows) || rows.length < spec.min) {
        errors.push(spec.name + ': تاریخچه ناکافی یا ناموجود');
        return;
      }
      var previous = -Infinity;
      rows.forEach(function (x) {
        var t = Number(x && x.t), o = Number(x && x.o), h = Number(x && x.h);
        var l = Number(x && x.l), c = Number(x && x.c);
        if (!Number.isFinite(t) || !Number.isFinite(o) || !Number.isFinite(h) ||
            !Number.isFinite(l) || !Number.isFinite(c) || o <= 0 || h <= 0 || l <= 0 || c <= 0) {
          errors.push(spec.name + ': مقدار زمان یا OHLC نامعتبر است');
          return;
        }
        if (t <= previous) errors.push(spec.name + ': ترتیب زمانی تکراری یا نامعتبر است');
        else if (spec.maxGap && previous > -Infinity &&
            Math.floor(t / 86400000) === Math.floor(previous / 86400000) &&
            t - previous > spec.maxGap) {
          // Ignore UTC date/session boundaries (weekends, holidays and FX rollover).
          errors.push(spec.name + ': شکاف زمانی غیرعادی در دادهٔ کندل‌ها');
        }
        previous = t;
        if (h < Math.max(o, c, l) || l > Math.min(o, c, h))
          errors.push(spec.name + ': رابطه OHLC ناسازگار است');
      });
      if (rows.length) {
        var lastT = Number(rows[rows.length - 1].t);
        // Future timestamps are invalid for every timeframe, including H4.
        // maxAge is intentionally intraday-only because H4 freshness is handled
        // differently, but that must not disable the future-data guard.
        if (lastT > now + 5 * 60000) {
          errors.push(spec.name + ': زمان آخرین کندل در آینده است');
        } else if (spec.maxAge && marketOpen) {
          var age = now - (lastT + spec.interval);
          if (age > spec.maxAge) errors.push(spec.name + ': آخرین کندل کهنه است');
        }
      }
    });
    return errors.filter(function (e, i, all) { return all.indexOf(e) === i; });
  };

  // H1 → H4 (دقیقاً مثل pandas resample("4h") روی ایندکس UTC:
  // سطل‌ها از نیمه‌شب UTC هر ۴ ساعت؛ Open=first, High=max, Low=min, Close=last)
  O.resample4h = function (h1) {
    var buckets = new Map();
    h1.forEach(function (x) {
      var key = Math.floor(x.t / 14400000);
      var b = buckets.get(key);
      if (!b) buckets.set(key, { t: key * 14400000, o: x.o, h: x.h, l: x.l, c: x.c });
      else {
        if (x.h > b.h) b.h = x.h;
        if (x.l < b.l) b.l = x.l;
        b.c = x.c;
      }
    });
    return Array.from(buckets.values()).sort(function (a, b) { return a.t - b.t; });
  };

  O.keepCompleted4h = function (h4, nowMs) {
    if (!Array.isArray(h4) || !h4.length) return [];
    var now = (typeof nowMs === 'number') ? nowMs : Date.now();
    var last = h4[h4.length - 1];
    return Number(last.t) + 4 * 60 * 60000 > now ? h4.slice(0, -1) : h4.slice();
  };

  // ── تاییدیه تریدینگ‌ویو (اسکنر غیررسمی، بدون لاگین) ─────────
  // ⚠️ نکتهٔ صادقانه: ستون‌های شمارش (Buy.All و...) دیگر از API گرفته
  // نمی‌شوند (null)؛ مقدار توصیه (Recommend.All) با پسوند دقیقه‌ای کار
  // می‌کند (4h → |240) و ملاک امتیاز داور همان است.
  var TF_SUFFIX = { '15m': '15', '1h': '60', '4h': '240' };

  function recLabel(v) {
    if (v == null) return null;
    if (v > 0.5) return 'STRONG_BUY';
    if (v > 0.1) return 'BUY';
    if (v >= -0.1) return 'NEUTRAL';
    if (v >= -0.5) return 'SELL';
    return 'STRONG_SELL';
  }

  O.fetchTvSnapshot = function (symbolsCfg, timeframe) {
    var tf = String(timeframe || '4h').toLowerCase();
    var suf = TF_SUFFIX[tf] || '240';
    var byScreener = {};
    symbolsCfg.forEach(function (s) {
      var tv = s.tv || {};
      if (!tv.symbol) return;
      var scr = tv.screener || 'forex';
      (byScreener[scr] = byScreener[scr] || []).push({
        name: s.name, ticker: (tv.exchange || 'FX') + ':' + tv.symbol
      });
    });
    var cols = ['close', 'Recommend.All|' + suf, 'Recommend.MA|' + suf, 'Recommend.Other|' + suf,
      'Buy.All|' + suf, 'Sell.All|' + suf, 'Neutral.All|' + suf, 'RSI|' + suf, 'ADX|' + suf];

    return Promise.all(Object.keys(byScreener).map(function (scr) {
      var tickers = byScreener[scr].map(function (x) { return x.ticker; });
      return O.http('https://scanner.tradingview.com/' + scr + '/scan', {
        method: 'POST',
        body: JSON.stringify({ symbols: { tickers: tickers }, columns: cols })
      }).then(function (r) {
        var out = {};
        if (r.status !== 200) return out;
        try {
          var j = JSON.parse(r.text);
          (j.data || []).forEach(function (row) {
            var hit = byScreener[scr].filter(function (x) { return x.ticker === row.s; })[0];
            if (!hit) return;
            var d = row.d || [];
            var rec = recLabel(d[1]);
            if (!rec) return;              // داده‌ای نیست → مدرک unavailable می‌ماند
            out[hit.name] = {
              symbol: hit.name, close: d[0], recommendation: rec,
              recommend_ma: d[2], recommend_other: d[3],
              buy: d[4], sell: d[5], neutral: d[6],
              rsi: d[7], adx: d[8], timeframe: tf
            };
          });
        } catch (e) { /* ignore */ }
        return out;
      }).catch(function () { return {}; });
    })).then(function (maps) {
      var all = {};
      maps.forEach(function (m) { Object.keys(m).forEach(function (k) { all[k] = m[k]; }); });
      return all;
    });
  };

  // ── تقویم اقتصادی (با کش محلی TTL‌دار، مثل دسکتاپ) ──────────
  O.fetchCalendar = function (cfg, storage) {
    var fcfg = cfg.fundamental || {};
    if (fcfg.enabled === false) {
      return Promise.resolve({ events: [], ok: false, error: 'غیرفعال در تنظیمات', fetched: false, stale: false, fromCache: false, weekRange: ['', ''] });
    }
    var ttl = (+(fcfg.cache_ttl_minutes) || 30) * 60000;
    var url = fcfg.source_url || 'https://nfs.faireconomy.media/ff_calendar_thisweek.json';

    function readCache() {
      try {
        var raw = storage.get('cache.calendar');
        if (!raw) return null;
        var blob = JSON.parse(raw);
        if (!blob || !Array.isArray(blob.events)) return null;
        return { raw: blob.events, ts: Date.parse(blob.fetched_at) };
      } catch (e) { return null; }
    }
    function build(raw, fetchedAt, fromCache, stale, fetched) {
      var events = O.parseEvents(raw);
      var dates = events.map(function (e) { return new Date(e.when).toISOString().slice(0, 10); }).sort();
      return {
        events: events, fetchedAt: fetchedAt, fromCache: fromCache, stale: stale,
        fetched: fetched,
        error: events.length ? '' : 'تقویم خالی یا فاقد رویداد معتبر است',
        ok: events.length > 0, source: O.CAL_SOURCE_NAME,
        weekRange: dates.length ? [dates[0], dates[dates.length - 1]] : ['', '']
      };
    }

    var cached = readCache();
    if (cached && (Date.now() - cached.ts) <= ttl) {
      return Promise.resolve(build(cached.raw, cached.ts, true, false, false));
    }
    return O.http(url).then(function (r) {
      if (r.status === 200) {
        try {
          var raw = JSON.parse(r.text);
          if (Array.isArray(raw)) {
            try { storage.set('cache.calendar', JSON.stringify({ fetched_at: new Date().toISOString(), events: raw })); } catch (e) { }
            return build(raw, Date.now(), false, false, true);
          }
        } catch (e) { /* fallthrough */ }
      }
      // زنده ناموفق — کش کهنه بهتر از هیچی است (و صادقانه علامت می‌خورد)
      if (cached && cached.raw) {
        var s = build(cached.raw, cached.ts, true, true, false);
        s.error = 'HTTP ' + r.status;
        return s;
      }
      return { events: [], ok: false, error: 'HTTP ' + r.status, fetched: false, stale: false, fromCache: false, weekRange: ['', ''] };
    }).catch(function (e) {
      if (cached && cached.raw) {
        var s = build(cached.raw, cached.ts, true, true, false);
        s.error = String(e && e.message || e);
        return s;
      }
      return { events: [], ok: false, error: String(e && e.message || e), fetched: false, stale: false, fromCache: false, weekRange: ['', ''] };
    });
  };

  // ── اخبار (RSS زنده در هر اجرا — بدون کش) ───────────────────
  O.fetchNews = function (cfg, onLog) {
    var ncfg = cfg.news || {};
    if (ncfg.enabled === false) {
      return Promise.resolve({ items: [], ok: false, error: 'غیرفعال در تنظیمات', feedsOk: 0, feedsFailed: 0, staleFeeds: [], failedNames: [], rawCount: 0 });
    }
    var feeds = ncfg.feeds && ncfg.feeds.length ? ncfg.feeds : O.CONFIG.news.feeds;
    var nowMs = Date.now();
    var age = +(ncfg.max_age_hours) || 30;
    var minScore = (ncfg.min_score | 0) || 2;
    var perFeed = (ncfg.max_items_per_feed | 0) || 12;
    var totalMax = (ncfg.max_total | 0) || 18;

    var snap = {
      items: [], fetchedAt: nowMs, feedsOk: 0, feedsFailed: 0,
      staleFeeds: [], failedNames: [], rawCount: 0, error: ''
    };

    // Fetch concurrently, but do not deduplicate or mutate shared snapshot state
    // inside individual callbacks: response timing must not decide which source wins.
    return Promise.all(feeds.map(function (f) {
      var name = f.name || f.url || 'feed';
      return O.http(f.url).then(function (r) {
        if (r.status !== 200 || !r.text) throw new Error('HTTP ' + r.status);
        var entries = O.parseFeedXml(r.text);
        if (!entries.length) throw new Error('فید خالی یا بدون ورودی بود');
        var items = O.parseEntries(entries, name, f.weight | 0 || 1, nowMs, age, minScore);
        items.sort(function (a, b) { return (b.published || nowMs) - (a.published || nowMs); });
        return { name: name, rawCount: entries.length, items: items.slice(0, perFeed) };
      }).catch(function (e) {
        return { name: name, error: String(e && e.message || e).slice(0, 70) };
      });
    })).then(function (results) {
      var seen = {};
      var itemsAll = [];
      // Promise.all preserves input order, so this matches the desktop Python
      // implementation's configured-feed priority even when responses race.
      results.forEach(function (result) {
        if (result.error) {
          snap.feedsFailed += 1;
          snap.failedNames.push(result.name);
          if (onLog) onLog('[!] فید ' + result.name + ' ناموفق: ' + result.error);
          return;
        }
        snap.feedsOk += 1;
        snap.rawCount += result.rawCount;
        var fresh = result.items.filter(function (it) {
          var k = O.dedupeKey(it.title);
          if (seen[k]) return false;
          seen[k] = true;
          return true;
        });
        if (!fresh.length && result.rawCount) {
          snap.staleFeeds.push(result.name);
          if (onLog) onLog('[i] ' + result.name + ': همهٔ ' + O.faNum(result.rawCount) + ' ورودی کهنه یا تکراری بودند — رد شد');
        } else {
          if (onLog) onLog('📰 ' + result.name + ': ' + O.faNum(fresh.length) + ' خبر تازه (از ' + O.faNum(result.rawCount) + ' ورودی)');
        }
        itemsAll = itemsAll.concat(fresh);
      });
      itemsAll.sort(function (a, b) { return (b.score - a.score) || (a.age_minutes - b.age_minutes); });
      snap.items = itemsAll.slice(0, totalMax);
      snap.ok = snap.items.length > 0;
      if (!snap.ok) snap.error = 'خبر مرتبطی در بازهٔ زمانی پیدا نشد';
      return snap;
    });
  };

  // ── چرخهٔ کامل تحلیل (معادل run_cycle بدون تلگرام) ──────────
  // فاز ۶: قابلیت‌ها از registry مصرف می‌شوند (caps) — ترتیب/لاگ‌ها/خروجی
  // بایت‌به‌بایت همان قبلی (میخ: tests/js/test_cycle_switch.js). رویدادهای
  // BUS افزودنی‌اند: بدون listener هیچ اثر رفتاری ندارند.
  /* ۶c (v0.28): runPipeline به دو بخشِ نام‌دار شکافته شد — collectMarket و
   * collectFundamental — تا cycleCore بتواند آن‌ها را در مراحلِ کانونیکالِ
   * pipeline بگذارد (ترتیبِ پایتون: fundamental *بعد از* journal_pre).
   * caps توسط صداکننده ساخته/رد می‌شود (چرخه یک caps دارد، نه دو تا)؛
   * بدون آن، هر بخش caps خودش را می‌سازد (رفتارِ مستقل حفظ شود).
   * wrapperِ O.runPipeline امضا و رفتارِ قدیم را بایت‌به‌بایت نگه می‌دارد:
   * fundamental فقط وقتی analyses هست (early-out امروز). */
  O.collectMarket = function (cfg, storage, log, caps) {
    log = log || function () { };
    caps = caps || O.makeCaps(cfg);
    var mkt = {
      analyses: [], datasets: {}, ranking: [], tvMap: {}, tvTf: '4h',
      sourceName: 'twelvedata', errors: 0
    };
    var syms = cfg.symbols;
    var total = syms.length;
    var done = 0;

    // منبع داده — connect/disconnect در adapter جاوااسکریپت no-op صادقانه‌اند
    // (fetch بی‌حالت است) ولی shape قراردادِ مشترک با دسکتاپ حفظ می‌شود.
    var source = caps.market;
    if (source && source.name) mkt.sourceName = source.name;
    if (!source) {
      log('❌ منبع داده در دسترس نیست — اینترنت/تنظیمات را بررسی کنید');
      mkt.errors = 1;
      O.BUS.emit(O.core.EVENTS.MARKET_COLLECTED, { analyses: 0, errors: mkt.errors });
      return Promise.resolve(mkt);
    }
    try { source.connect(); }
    catch (e) {
      log('❌ اتصال به منبع داده ناموفق: ' + String(e && e.message || e).slice(0, 120));
      mkt.errors = 1;
      O.BUS.emit(O.core.EVENTS.MARKET_COLLECTED, { analyses: 0, errors: mkt.errors });
      return Promise.resolve(mkt);
    }

    return Promise.all(syms.map(function (s) {
      log('📡 دریافت ' + s.name + '...');
      return source.fetch(s).then(function (md) {
        done++;
        if (!md) {
          mkt.errors++;
          var sourceError = source.getError ? source.getError(s.name) : '';
          log('[!] دادهٔ ' + s.name + ' ناقص است — رد شد' + (sourceError ? ' (' + sourceError + ')' : ''));
        } else {
          mkt.datasets[s.name] = md;
          try { mkt.analyses.push(caps.technical.analyzeSymbol(s, md, cfg.analysis)); }
          catch (e) { mkt.errors++; log('[!] خطای تحلیل ' + s.name + ': ' + e); }
        }
        log('(' + O.faNum(done) + '/' + O.faNum(total) + ') ' + s.name + (md ? ' ✅' : ' ❌'));
      });
    })).then(function () {
      try { source.disconnect(); } catch (e) { }
      if (!mkt.analyses.length) {
        log('❌ هیچ نمادی تحلیل نشد — اینترنت را بررسی کنید');
        mkt.errors = Math.max(mkt.errors, 1);
        O.BUS.emit(O.core.EVENTS.MARKET_COLLECTED, { analyses: 0, errors: mkt.errors });
        return mkt;
      }
      log('✅ تحلیل ' + O.faNum(mkt.analyses.length) + ' نماد انجام شد');
      mkt.ranking = caps.strength.currencyStrength(mkt.datasets, (cfg.analysis.strength_lookback_h1 | 0) || 24);
      // market.collected: payload همان کلیدهای پایتون {analyses, errors} —
      // اینجا منتشر می‌شود چون تعداد تحلیل‌ها قطعی است (TV لایهٔ تاییدیه است
      // و هم‌زمان با فاندامنتال واکشی می‌شود؛ در پایتون بخشی از collect_market است)
      O.BUS.emit(O.core.EVENTS.MARKET_COLLECTED,
        { analyses: mkt.analyses.length, errors: mkt.errors });
      return mkt;
    });
  };

  O.collectFundamental = function (cfg, storage, mkt, log, caps) {
    log = log || function () { };
    caps = caps || O.makeCaps(cfg);

      var tvCfg = cfg.tradingview || {};
      mkt.tvTf = tvCfg.timeframe || '4h';
      var tv = caps.tv;   // binding مانیفست: tradingview.enabled=false → null
      var tvP = (tvCfg.enabled !== false && tv)
        ? (log('🔍 دریافت تاییدیه تریدینگ‌ویو...'),
          tv.fetchTvSnapshot(cfg.symbols, mkt.tvTf).then(function (m) {
            mkt.tvMap = m || {};
            log('✅ تاییدیه تریدینگ‌ویو برای ' + O.faNum(Object.keys(mkt.tvMap).length) + ' نماد دریافت شد');
          }))
        : Promise.resolve();

      // فاز ۷ — تک‌مسیر: پلاگین خاموش (طبق binding) → همان snap
      // «غیرفعال در تنظیمات» درون‌خطی — بایت‌به‌بایت با خروجیِ guard داخلیِ
      // O.fetchCalendar (smoke_plugins برابری این دو را assert می‌کند).
      // guard داخلی سرِ جایش می‌ماند (دفاع لایهٔ دوم + سایر مصرف‌کننده‌ها).
      var cal = caps.calendar;
      var calP = (cal ? cal.fetchCalendar(cfg, storage) : Promise.resolve({
        events: [], ok: false, error: 'غیرفعال در تنظیمات', fetched: false,
        stale: false, fromCache: false, weekRange: ['', '']
      })).then(function (s) {
        mkt.calSnap = s;
        if (s && s.stale) {
          var ageMin = (typeof s.fetchedAt === 'number' && Number.isFinite(s.fetchedAt))
            ? Math.max(0, Math.floor((Date.now() - s.fetchedAt) / 60000)) : null;
          log('[!] تقویم اقتصادی کهنه است' + (ageMin !== null ? ' (' + O.faNum(ageMin) + ' دقیقه از آخرین دریافت)' : '') +
            ' — رویدادهای ذخیره‌شده فقط برای احتیاط استفاده می‌شوند؛ نبود رویداد را تأییدشده فرض نکنید');
        }
        if (s && s.ok) log('🏦 تقویم اقتصادی: ' + O.faNum(s.events.length) + ' رویداد' +
          (s.stale ? ' (کش کهنه)' : (s.fromCache ? ' (از کش تازه)' : '')));
        else log('[!] تقویم اقتصادی در دسترس نیست: ' + String((s && s.error) || '').slice(0, 80));
      });

      var news = caps.news;
      var newsP = (news ? news.fetchNews(cfg, log) : Promise.resolve({
        items: [], ok: false, error: 'غیرفعال در تنظیمات', feedsOk: 0,
        feedsFailed: 0, staleFeeds: [], failedNames: [], rawCount: 0
      })).then(function (s) {
        mkt.newsSnap = s;
        if (s && s.ok) {
          var br = s.items.filter(function (i) { return i.breaking; }).length;
          log('✅ موتور اخبار: ' + O.faNum(s.items.length) + ' خبر (' + O.faNum(s.feedsOk) + ' فید موفق، ' +
            O.faNum(s.feedsFailed) + ' نامفق' + (br ? '، ' + O.faNum(br) + ' فوری' : '') + ')');
        } else log('[!] موتور اخبار: ' + ((s && s.error) || 'خبری پیدا نشد'));
      });

      return Promise.all([tvP, calP, newsP]).then(function () {
        O.BUS.emit(O.core.EVENTS.FUNDAMENTAL_COLLECTED, {
          calendar_ok: !!(mkt.calSnap && mkt.calSnap.ok),
          news_items: (mkt.newsSnap && mkt.newsSnap.items) ? mkt.newsSnap.items.length : 0
        });
        return mkt;
      });
  };

  // wrapper سازگار: همان امضا/رفتارِ پیش از ۶c (مصرف‌کننده‌های مستقل نشکنند)
  O.runPipeline = function (cfg, storage, onProgress) {
    var log = onProgress || function () { };
    var caps = O.makeCaps(cfg);
    return O.collectMarket(cfg, storage, log, caps).then(function (mkt) {
      if (!mkt.analyses.length) return mkt;   // early-out امروز: fundamental واکشی نمی‌شود
      return O.collectFundamental(cfg, storage, mkt, log, caps);
    });
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
