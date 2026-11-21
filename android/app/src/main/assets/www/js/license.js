/* لایسنس و قفل دستگاه — همزاد دقیقِ src/license.py برای اندروید.
 * v1.0.2: امضای نامتقارن Ed25519 (RFC 8032) به‌جای HMAC رازمشترک.
 *
 * چرا: با HMAC رازِ ساختِ کلید باید داخلِ اپ باشد تا اپ بتواند اعتبارسنجی کند،
 * یعنی هر کس می‌تواند keygen بسازد. اینجا اپ فقط «کلید عمومی» را دارد و فقط
 * تأیید می‌کند؛ ساخت کلید به کلید خصوصی سازنده نیاز دارد که در اپ نیست.
 *
 * طرح (یکسان در دو پلتفرم):
 *   device_id   = SHA-256 هگز (۶۴ کاراکتر) — در اندروید از ANDROID_ID
 *                 (سمت Bridge.getDeviceId محاسبه می‌شود: sha256("android:"+id))
 *   device_code = ۱۲ رقم اولِ device_id، بالا‌حروف، جداکنندهٔ ۴تایی
 *   message     = "ODIN1|" + device_code + "|" + YYYYMMDD   (دائمی: 00000000)
 *   کلید        = Base32(امضای Ed25519 روی message)  → ۱۰۳ نویسه
 *   کلید زمان‌دار = Base32 + "-" + YYMMDD
 *
 * اعتبارسنجی: nacl.sign.detached.verify (TweetNaCl 1.0.3 — js/nacl.js) با
 * کلید عمومی + انقضا + قفل device_id. همهٔ بُرِدهای آزمایشی مشترک در
 * tests/js/smoke_license.js و main.py --selftest قفلش کرده‌اند.
 */
(function (O) {
  'use strict';

  // کلید عمومی امضای لایسنس — همان PUBLIC_KEY_HEX در src/license.py.
  // این کلید عمومی است: فقط تأیید می‌کند و اجازهٔ ساخت کلید نمی‌دهد.
  O.LICENSE_PUBLIC_KEY_HEX = '7F2CCF1F739C9FC4BC479A966FA1527CAC462BED99C3D7693B5B124BA8111591';

  var K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ];

  function rotr(x, n) { return ((x >>> n) | (x << (32 - n))) >>> 0; }

  function utf8Bytes(str) {
    var out = [];
    for (var i = 0; i < str.length; i++) {
      var c = str.charCodeAt(i);
      if (c < 0x80) { out.push(c); }
      else if (c < 0x800) { out.push(0xc0 | (c >> 6), 0x80 | (c & 63)); }
      else if (c >= 0xd800 && c <= 0xdbff && i + 1 < str.length) {
        var c2 = str.charCodeAt(++i);
        var cp = 0x10000 + ((c & 0x3ff) << 10) + (c2 & 0x3ff);
        out.push(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 63),
          0x80 | ((cp >> 6) & 63), 0x80 | (cp & 63));
      } else { out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63)); }
    }
    return out;
  }

  function toHex(bytes, upper) {
    var h = '';
    for (var i = 0; i < bytes.length; i++) {
      h += (bytes[i] < 16 ? '0' : '') + bytes[i].toString(16);
    }
    return upper ? h.toUpperCase() : h;
  }

  function hexBytes(hex) {
    var s = String(hex == null ? '' : hex).replace(/[^0-9A-Fa-f]/g, '');
    var out = [];
    for (var i = 0; i + 1 < s.length; i += 2) out.push(parseInt(s.substr(i, 2), 16));
    return out;
  }

  /** SHA-256 روی آرایهٔ بایت → آرایهٔ ۳۲ بایت (FIPS 180-4) */
  function sha256(bytes) {
    var H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
    var l = bytes.length;
    var total = (((l + 8) >> 6) + 1) << 6;
    var msg = bytes.slice();
    msg.push(0x80);
    while (msg.length < total) msg.push(0);
    var bitHi = Math.floor(l / 536870912);
    var bitLo = (l << 3) >>> 0;
    msg[total - 8] = (bitHi >>> 24) & 255; msg[total - 7] = (bitHi >>> 16) & 255;
    msg[total - 6] = (bitHi >>> 8) & 255;  msg[total - 5] = bitHi & 255;
    msg[total - 4] = (bitLo >>> 24) & 255; msg[total - 3] = (bitLo >>> 16) & 255;
    msg[total - 2] = (bitLo >>> 8) & 255;  msg[total - 1] = bitLo & 255;

    var W = new Array(64);
    for (var off = 0; off < total; off += 64) {
      for (var i = 0; i < 16; i++) {
        W[i] = ((msg[off + i * 4] << 24) | (msg[off + i * 4 + 1] << 16) |
          (msg[off + i * 4 + 2] << 8) | msg[off + i * 4 + 3]) >>> 0;
      }
      for (i = 16; i < 64; i++) {
        var x = W[i - 15], y = W[i - 2];
        var s0 = (rotr(x, 7) ^ rotr(x, 18) ^ (x >>> 3)) >>> 0;
        var s1 = (rotr(y, 17) ^ rotr(y, 19) ^ (y >>> 10)) >>> 0;
        W[i] = (W[i - 16] + s0 + W[i - 7] + s1) >>> 0;
      }
      var a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (i = 0; i < 64; i++) {
        var S1 = (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) >>> 0;
        var ch = ((e & f) ^ (~e & g)) >>> 0;
        var t1 = (h + S1 + ch + K[i] + W[i]) >>> 0;
        var S0 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) >>> 0;
        var maj = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
        var t2 = (S0 + maj) >>> 0;
        h = g; g = f; f = e; e = (d + t1) >>> 0;
        d = c; c = b; b = a; a = (t1 + t2) >>> 0;
      }
      H[0] = (H[0] + a) >>> 0; H[1] = (H[1] + b) >>> 0;
      H[2] = (H[2] + c) >>> 0; H[3] = (H[3] + d) >>> 0;
      H[4] = (H[4] + e) >>> 0; H[5] = (H[5] + f) >>> 0;
      H[6] = (H[6] + g) >>> 0; H[7] = (H[7] + h) >>> 0;
    }
    var out = [];
    for (i = 0; i < 8; i++) {
      out.push((H[i] >>> 24) & 255, (H[i] >>> 16) & 255, (H[i] >>> 8) & 255, H[i] & 255);
    }
    return out;
  }

  /** HMAC-SHA256 (RFC 2104) — ابزار کمکی/تست (دیگر برای لایسنس به کار نمی‌رود) */
  function hmacSha256Hex(keyStr, msgStr) {
    var key = utf8Bytes(keyStr);
    if (key.length > 64) key = sha256(key);
    var ipad = new Array(64), opad = new Array(64);
    for (var i = 0; i < 64; i++) {
      var k = i < key.length ? key[i] : 0;
      ipad[i] = k ^ 0x36;
      opad[i] = k ^ 0x5c;
    }
    var inner = sha256(ipad.concat(utf8Bytes(msgStr)));
    return toHex(sha256(opad.concat(inner)), false);
  }

  // ── Base32 (RFC 4648، بالا‌حروف، بدون padding) ─────────────────
  var B32 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  function b32Encode(bytes) {
    var out = '', val = 0, bits = 0;
    for (var i = 0; i < bytes.length; i++) {
      val = (val << 8) | bytes[i];
      bits += 8;
      while (bits >= 5) { bits -= 5; out += B32[(val >>> bits) & 31]; }
    }
    if (bits) out += B32[(val << (5 - bits)) & 31];
    return out;
  }
  function b32Decode(s) {
    var val = 0, bits = 0, out = [];
    for (var i = 0; i < s.length; i++) {
      var idx = B32.indexOf(s.charAt(i));
      if (idx < 0) throw new Error('bad base32');
      val = (val << 5) | idx;
      bits += 5;
      if (bits >= 8) { bits -= 8; out.push((val >>> bits) & 255); }
    }
    return out;
  }

  // ── API هم‌نام با پایتون ─────────────────────────────────────
  O.sha256Hex = function (s) { return toHex(sha256(utf8Bytes(String(s == null ? '' : s))), false); };
  O.hmacSha256Hex = hmacSha256Hex;
  O.b32Encode = function (bytes) { return b32Encode(bytes); };
  O.b32Decode = function (s) { return b32Decode(s); };

  O.normalizeCode = function (s) {
    return String(s == null ? '' : s).replace(/[^0-9A-Fa-f]/g, '').toUpperCase();
  };
  O.formatCode = function (raw) {
    return String(raw).replace(/(.{4})(?=.)/g, '$1-');
  };
  // ⚠️ «خلاصه» همان کد است: device_id ۶۴ هگز است و کد = ۱۲ رقمِ اولِ آن.
  //   اینجا همان کار را می‌کنیم (نه slice) تا پایتون/JS هم‌بُر بمانند.
  O.deviceCodeFromId = function (deviceId) {
    return O.formatCode(O.normalizeCode(deviceId).slice(0, 12));
  };

  var SIG_B32_LEN = 103;
  O.LICENSE_TRIAL_DAYS = 7;
  var ROLLBACK_MS = 48 * 3600 * 1000;   // تلورانس عقب‌رفتن ساعت (مثل پایتون)
  var TOUCH_MS = 6 * 3600 * 1000;       // throttle به‌روزرسانی last_seen

  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function ymd8(d) { return '' + d.getFullYear() + pad2(d.getMonth() + 1) + pad2(d.getDate()); }

  function keyMessage(code, expiry8) {
    return utf8Bytes('ODIN1|' + code + '|' + expiry8);
  }

  /**
   * رشتهٔ کلید → {sig: Base32 ۱۰۳‌نویسه‌ای, expiry8:'YYYYMMDD'|null} یا null.
   * دائمی: ۱۰۳ نویسه Base32 · زمان‌دار: ۱۰۳ نویسه + «-» + ۶ رقم YYMMDD.
   */
  O.parseKeyInput = function (raw) {
    var s = String(raw == null ? '' : raw).replace(/\s+/g, '').toUpperCase();
    if (!s) return null;
    var body = s, expiry8 = null;
    var dash = s.lastIndexOf('-');
    if (dash > 0) {
      var tail = s.slice(dash + 1);
      if (tail.length === 6 && /^[0-9]{6}$/.test(tail)) {
        var yy = +tail.slice(0, 2), mm = +tail.slice(2, 4), dd = +tail.slice(4, 6);
        if (mm < 1 || mm > 12 || dd < 1 || dd > 31) return null;
        var d = new Date(2000 + yy, mm - 1, dd);
        if (d.getMonth() !== mm - 1 || d.getDate() !== dd) return null;   // مثلاً ۳۱ فوریه
        body = s.slice(0, dash);
        expiry8 = '20' + tail;
      }
    }
    body = body.replace(/-/g, '');
    // پسوند تاریخِ بدون خط‌تیره (تایپ دستی): ۱۰۹ نویسه که ۶ تای آخر رقم است.
    if (expiry8 === null && body.length === SIG_B32_LEN + 6 &&
        /^[0-9]{6}$/.test(body.slice(SIG_B32_LEN))) {
      var nb = body.slice(SIG_B32_LEN);
      var nyy = +nb.slice(0, 2), nmm = +nb.slice(2, 4), ndd = +nb.slice(4, 6);
      if (nmm < 1 || nmm > 12 || ndd < 1 || ndd > 31) return null;
      var nd = new Date(2000 + nyy, nmm - 1, ndd);
      if (nd.getMonth() !== nmm - 1 || nd.getDate() !== ndd) return null;
      expiry8 = '20' + nb;
      body = body.slice(0, SIG_B32_LEN);
    }
    if (body.length !== SIG_B32_LEN || !new RegExp('^[A-Z2-7]{' + SIG_B32_LEN + '}$').test(body)) return null;
    return { sig: body, expiry8: expiry8 };
  };

  /** تولید کلید با کلید خصوصی سازنده — فقط ابزار/تست (اپ این را صدا نمی‌زند). */
  O.licenseKeyFor = function (deviceCode, expiry8, seedHex) {
    var code = O.normalizeCode(deviceCode);
    if (code.length !== 12) return '';
    if (typeof nacl === 'undefined' || !nacl.sign) return '';
    var seed = hexBytes(seedHex);
    if (seed.length !== 32) return '';
    var kp = nacl.sign.keyPair.fromSeed(new Uint8Array(seed));
    var sig = nacl.sign.detached(new Uint8Array(keyMessage(code, expiry8 || '00000000')),
                                 kp.secretKey);
    var b32 = b32Encode(Array.prototype.slice.call(sig));
    return expiry8 ? (b32 + '-' + expiry8.slice(2)) : b32;
  };

  /** اعتبارسنجی: امضای Ed25519 با کلید عمومی + انقضا (تاریخ محلی دستگاه) */
  O.validateKey = function (key, deviceCode, nowMs) {
    var p = O.parseKeyInput(key);
    if (!p) return false;
    var code = O.normalizeCode(deviceCode);
    if (code.length !== 12) return false;
    if (p.expiry8 && ymd8(new Date(nowMs || Date.now())) > p.expiry8) return false;
    if (typeof nacl === 'undefined' || !nacl.sign) return false;
    var sig;
    try { sig = b32Decode(p.sig); } catch (e) { return false; }
    return nacl.sign.detached.verify(
      new Uint8Array(keyMessage(code, p.expiry8 || '00000000')),
      new Uint8Array(sig),
      new Uint8Array(hexBytes(O.LICENSE_PUBLIC_KEY_HEX)));
  };

  /** کلید کاربر را به قالب فشردهٔ ذخیره‌سازی نرمال کن */
  O.normalizeKey = function (key) {
    var p = O.parseKeyInput(key);
    if (!p) return '';
    return p.sig + (p.expiry8 ? '-' + p.expiry8.slice(2) : '');
  };

  function rolledBack(lastSeenIso, nowMs) {
    if (!lastSeenIso) return false;
    var ls = Date.parse(lastSeenIso);
    if (!isFinite(ls)) return false;
    return (nowMs || Date.now()) < ls - ROLLBACK_MS;
  }
  O.rolledBack = rolledBack;

  // ── چرخهٔ ذخیره (SharedPreferences — کلید license.dat مثل دسکتاپ) ──
  O.licLoad = function (storage) {
    try {
      var raw = storage.get('license.dat');
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  };

  /** قفل‌ها: device_id == دستگاه فعلی · امضای درست · انقضا نگذشته · ساعت دستکاری نشده */
  O.licIsActive = function (storage, deviceId, nowMs) {
    var now = nowMs || Date.now();
    var d = O.licLoad(storage);
    if (!d || !deviceId || d.device_id !== deviceId) return false;
    if (rolledBack(d.last_seen, now)) return false;
    if (!O.validateKey(d.license_key, O.deviceCodeFromId(deviceId), now)) return false;
    try {
      if (!d.last_seen || now - Date.parse(d.last_seen) > TOUCH_MS) {
        d.last_seen = new Date(now).toISOString();
        storage.set('license.dat', JSON.stringify(d));
      }
    } catch (e) { }
    return true;
  };

  O.licActivate = function (storage, key, deviceId, userName, nowMs) {
    var now = nowMs || Date.now();
    if (!O.validateKey(key, O.deviceCodeFromId(deviceId), now)) return false;
    var p = O.parseKeyInput(key);
    try {
      storage.set('license.dat', JSON.stringify({
        license_key: O.normalizeKey(key),
        device_id: deviceId,
        user_name: userName || '',
        expires_at: p ? p.expiry8 : null,
        activated_at: new Date(now).toISOString(),
        last_seen: new Date(now).toISOString(),
        version: '3.0'
      }));
      return true;
    } catch (e) { return false; }
  };

  O.licDeactivate = function (storage) {
    try { storage.del('license.dat'); } catch (e) { }
  };

  // ── دورهٔ آزمایشی (trial.dat — مثل trial پایتون) ────────────────
  O.trialStatus = function (storage, nowMs) {
    var now = nowMs || Date.now();
    var t = null;
    try { var raw = storage.get('trial.dat'); t = raw ? JSON.parse(raw) : null; } catch (e) { t = null; }
    if (!t) return { exists: false, active: false, daysLeft: 0, tampered: false };
    if (rolledBack(t.last_seen, now)) return { exists: true, active: false, daysLeft: 0, tampered: true };
    var started = Date.parse(t.started_at);
    if (!isFinite(started)) return { exists: true, active: false, daysLeft: 0, tampered: true };
    var days = t.days || O.LICENSE_TRIAL_DAYS;
    var used = Math.max(0, (now - started) / 86400000);
    return { exists: true, active: used < days, daysLeft: Math.max(0, days - Math.floor(used)), tampered: false };
  };

  O.trialStart = function (storage, nowMs) {
    if (O.trialStatus(storage, nowMs).exists) return false;   // یک‌بار بیشتر نه (ضدتقلب)
    var now = new Date(nowMs || Date.now());
    try {
      storage.set('trial.dat', JSON.stringify({
        started_at: now.toISOString(), last_seen: now.toISOString(),
        days: O.LICENSE_TRIAL_DAYS
      }));
      return true;
    } catch (e) { return false; }
  };

  O.trialTouch = function (storage, nowMs) {
    var now = nowMs || Date.now();
    try {
      var raw = storage.get('trial.dat');
      if (!raw) return;
      var t = JSON.parse(raw);
      if (!t.last_seen || now - Date.parse(t.last_seen) > TOUCH_MS) {
        t.last_seen = new Date(now).toISOString();
        storage.set('trial.dat', JSON.stringify(t));
      }
    } catch (e) { }
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
