/* اسموک‌تست لایسنس اندروید (v1.0.2) — js/license.js در برابر وکتورهای قطعی.
 *
 * پوشش: sha256/hmac (مطابق node:crypto روی طول‌های مرزی) · امضای Ed25519 در
 * برابر node:crypto · بُرِدهای مشترک با src/license.py (دائمی + زمان‌دار) ·
 * پارس کلید ۱۰۳ نویسه‌ای · انقضا · قفل device_id · دورهٔ آزمایشی ۷ روزه ·
 * ضدِ عقب‌کشیدن ساعت (high-water-mark).
 *
 * اجرا: node tests/js/smoke_license.js */
'use strict';
const fs = require('fs');
const vm = require('vm');
const crypto = require('crypto');
const assert = require('assert');
const path = require('path');

const WWW = path.join(__dirname, '..', '..', 'android', 'app', 'src', 'main', 'assets', 'www', 'js');
const ctx = { console };
ctx.globalThis = ctx;
ctx.self = ctx;                       // wrapper تانگرNaCl به «self» نیاز دارد
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(WWW, 'nacl.js'), 'utf8'), ctx, { filename: 'nacl.js' });
vm.runInContext(fs.readFileSync(path.join(WWW, 'license.js'), 'utf8'), ctx, { filename: 'license.js' });
const O = ctx.ODIN;

// ── ۰) قرارداد شناسهٔ اندروید: فقط SSAID، بدون UUID ناپایدار ──
const ROOT = path.join(__dirname, '..', '..');
const bridgeSource = fs.readFileSync(
  path.join(ROOT, 'android', 'app', 'src', 'main', 'java', 'com', 'odin', 'assistant', 'Bridge.java'),
  'utf8'
);
const methodStart = bridgeSource.indexOf('public String getDeviceId()');
const methodEnd = bridgeSource.indexOf('\n    }\n', methodStart);
assert(methodStart >= 0 && methodEnd > methodStart, 'Bridge.getDeviceId باید موجود باشد');
const deviceIdMethod = bridgeSource.slice(methodStart, methodEnd);
assert(deviceIdMethod.includes('Settings.Secure.ANDROID_ID'), 'شناسه باید از ANDROID_ID/SSAID بیاید');
assert(!deviceIdMethod.includes('UUID.randomUUID') && !deviceIdMethod.includes('device.fallback'),
  'شناسهٔ تصادفیِ پاک‌شونده با uninstall نباید fallback باشد');
assert(deviceIdMethod.includes('aid.matches("(?i)[0-9a-f]{16}")'),
  'SSAID باید به قالب ۶۴بیتی hex اعتبارسنجی شود');

const appSource = fs.readFileSync(path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www', 'js', 'app.js'), 'utf8');
assert(!appSource.includes('deadbeefcafebabedeadbeefcafebabe'),
  'شناسهٔ ساختگی نباید در مسیر فعال‌سازی/بوت استفاده شود');

// ── ۱) SHA-256/HMAC در برابر node:crypto (لبه‌های padding) ──
for (const n of [0, 1, 54, 55, 56, 57, 63, 64, 65, 118, 119, 120, 1000]) {
  const s = 'x'.repeat(n);
  assert.strictEqual(O.sha256Hex(s), crypto.createHash('sha256').update(s).digest('hex'),
    'sha256 mismatch at len ' + n);
  const k = 'secret-key-' + n;
  assert.strictEqual(O.hmacSha256Hex(k, s), crypto.createHmac('sha256', k).update(s).digest('hex'),
    'hmac mismatch at len ' + n);
}

// ── ۲) خودِ پیاده‌سازی Ed25519 در برابر node:crypto ──
{
  const { privateKey, publicKey } = crypto.generateKeyPairSync('ed25519');
  const seed = privateKey.export({ format: 'der', type: 'pkcs8' }).subarray(-32);
  const pub = publicKey.export({ format: 'der', type: 'spki' }).subarray(-32);
  const msg = Buffer.from('ODIN1|AB12CD34EF56|00000000');
  const sig = crypto.sign(null, msg, privateKey);
  const bad = Buffer.from(sig); bad[7] ^= 1;
  Object.assign(ctx, {
    _msg: Array.from(msg), _sig: Array.from(sig), _bad: Array.from(bad),
    _pub: Array.from(pub), _seed: Array.from(seed)
  });
  const r = vm.runInContext(`({
    verify: nacl.sign.detached.verify(new Uint8Array(_msg), new Uint8Array(_sig), new Uint8Array(_pub)),
    bad: nacl.sign.detached.verify(new Uint8Array(_msg), new Uint8Array(_bad), new Uint8Array(_pub)),
    seedPub: Array.from(nacl.sign.keyPair.fromSeed(new Uint8Array(_seed)).publicKey).map(b => b.toString(16).padStart(2, '0')).join('')
  })`, ctx);
  assert.strictEqual(r.verify, true, 'TweetNaCl باید امضای node:crypto را بپذیرد');
  assert.strictEqual(r.bad, false, 'امضای دستکاری‌شده باید رد شود');
  assert.strictEqual(r.seedPub, pub.toString('hex'), 'کلید عمومی از سید باید با node:crypto یکی باشد');
}

// ── ۳) بُرِدهای مشترک با پایتون (main.py --selftest هم همین‌ها را چک می‌کند) ──
// سیدِ تست فقط همین‌جا و در main.py است؛ کلید عمومیِ اپ یک کلید دیگر است.
const TEST_SEED = '8D9FADA9722DA1DDF8EBA1CA0E3E7AA8A7AB9F3DC120C65BB9ED211B8842BC9E';
const OTHER_SEED = '1111111111111111111111111111111111111111111111111111111111111111';
assert.strictEqual(
  O.licenseKeyFor('AB12-CD34-EF56', null, TEST_SEED),
  'SAYIKVXA2JU7SPMLWBA5OIEXNGDBR6OYM6AVJ2ZGUQYQYL22ZCL3YX35EXT2XOALBXXZVAAY7WZGCWH4FRUAU4CICLOVJUSHKCH6GCI');
assert.strictEqual(
  O.licenseKeyFor('D9AC-5560-5559', null, TEST_SEED),
  '7TAHMUJW7ODWGPFYNQ3INXTI7XE2BXNAV5PRYTQ373D2BSVFHXKY723OYNYXLWDFTIQEMKJ3TRKBZPKSBGVRTCWJEREPC3I6APLKSCQ');
assert.strictEqual(
  O.licenseKeyFor('AB12-CD34-EF56', '20301231', TEST_SEED),
  'CYU2HFS6GV2WLA2VFPGLLSYCX2BKIOUD3BSBBEXXEBZBOJZDQ6HIIFFLX2CUDY2A4ZIVWVNWV3SUKOWTGB7VMNEBAQBK7TG37IZKKAQ-301231');

// کلیدهای امضاشده با کلید خصوصیِ واقعی (کلید عمومیِ اپ)
const PROD_PERM = 'ODGLQ6OP5YOE22KNKAF7S6GLFBNFG7LVLROLG7ZR4NTM3CP7FEWYXZN2SXUWVZJIOE3DL472XM4MLA2WDROVNWEJ47YMHOH5CAFIOBQ';
const PROD_TIMED = 'IU5IBZ2PQNDY6YJBNKAQ4JE6FGHTTABGWXZWVEDUIS6FS3X7MEZ2J6BGTIHO25WAU4MJKNZB46NCRMA4SCGB7AIKQ52TCNZYGRWUADY-301231';

// ── ۴) پارس کلید (۱۰۳ = دائمی، ۱۰۳+۶ = زمان‌دار، بقیه رد) ──
let p = O.parseKeyInput(PROD_TIMED.toLowerCase());
assert(p && p.sig === PROD_TIMED.slice(0, 103) && p.expiry8 === '20301231');
assert.strictEqual(O.parseKeyInput(PROD_PERM).expiry8, null);
assert.strictEqual(O.parseKeyInput('short'), null);
assert.strictEqual(O.parseKeyInput(PROD_PERM.slice(0, 102)), null);          // کوتاه
assert.strictEqual(O.parseKeyInput(PROD_PERM.slice(0, 103) + '-310231'), null); // ۳۱ فوریه!
assert.strictEqual(O.parseKeyInput(PROD_PERM.slice(0, 103) + '-3012'), null);   // پسوند کوتاه
assert.strictEqual(O.licenseKeyFor('short', null, TEST_SEED), '');
assert.strictEqual(O.licenseKeyFor('AB12CD34EF56', null, 'abcd'), '');

// ── ۵) اعتبارسنجی: دائمی/زمان‌دار/انقضا/دستگاه دیگر/کلید خصوصیِ دیگر ──
// شناسه‌ای که کدش دقیقاً AB12-CD34-EF56 باشد (مثل خروجی Bridge.getDeviceId)
const deviceId = 'ab12cd34ef56' + '0'.repeat(52);
const code = O.deviceCodeFromId(deviceId);
assert.strictEqual(code, 'AB12-CD34-EF56');
assert(O.validateKey(PROD_PERM, 'AB12CD34EF56'), 'دائمی معتبر');
assert(O.validateKey(PROD_PERM.toLowerCase(), 'AB12CD34EF56'), 'مقاوم به کوچک‌بزرگی');
assert(O.validateKey(PROD_TIMED, 'AB12CD34EF56'), 'زمان‌دار معتبر');
assert(O.validateKey(PROD_TIMED, 'AB12CD34EF56', new Date('2030-12-31T10:00:00').getTime()),
  'روز انقضا هنوز معتبر');
assert(!O.validateKey(PROD_TIMED, 'AB12CD34EF56', new Date('2031-01-01T00:00:00').getTime()),
  'منقضی رد می‌شود');
assert(!O.validateKey(PROD_PERM, 'FF00-FF00-FF00'), 'کلید دستگاه دیگر');
assert(!O.validateKey(PROD_PERM.slice(0, 103) + '-301231', 'AB12CD34EF56'),
  'کلید دائمی با پسوند تاریخ → رد (امضا روی تاریخ هم هست)');
// کلید ساخته‌شده با سیدِ تست/دیگر باید مردود شود (کلید عمومیِ اپ یکی است)
assert(!O.validateKey(O.licenseKeyFor('AB12CD34EF56', null, TEST_SEED), 'AB12CD34EF56'),
  'کلید ساخته‌شده با کلید خصوصیِ دیگر رد می‌شود');
assert(!O.validateKey(O.licenseKeyFor('AB12CD34EF56', null, OTHER_SEED), 'AB12CD34EF56'),
  'کلید ساخته‌شده با سیدِ تصادفی رد می‌شود');

// ── ۶) چرخهٔ ذخیره + قفل device_id + انقضا ──
const mem = {};
const storage = { get: k => mem[k] || '', set: (k, v) => { mem[k] = String(v); }, del: k => { delete mem[k]; } };
assert(!O.licIsActive(storage, deviceId), 'بدون لایسنس: غیرفعال');
assert(O.licActivate(storage, PROD_TIMED, deviceId, 'تستر'), 'فعال‌سازی زمان‌دار');
assert(O.licIsActive(storage, deviceId), 'فعال');
assert(!O.licIsActive(storage, deviceId, new Date('2031-01-02T00:00:00').getTime()), 'پس از انقضا: غیرفعال');
assert(!O.licIsActive(storage, 'ff'.repeat(32)), 'device_id بیگانه → غیرفعال (ضدکپی)');
const rec = JSON.parse(mem['license.dat']);
assert.strictEqual(rec.version, '3.0');
assert.strictEqual(rec.expires_at, '20301231');
assert(rec.last_seen, 'last_seen برای ضدِ دستکاری ساعت ذخیره شود');
// دستکاری رکورد: last_seen آینده → rollback
const tampered = Object.assign({}, rec, { last_seen: new Date(Date.now() + 96 * 3600e3).toISOString() });
mem['license.dat'] = JSON.stringify(tampered);
assert(!O.licIsActive(storage, deviceId), 'عقب‌کشیدن ساعت → غیرفعال');
mem['license.dat'] = JSON.stringify(rec);
assert(!O.licActivate(storage, 'AAAA-BBBB-CCCC-DDDD', deviceId, 'هکر'), 'فعال‌سازی با کلید غلط رد می‌شود');
assert(!O.licActivate(storage, O.licenseKeyFor('ABABABABABAB', null, TEST_SEED), deviceId, 'هکر'),
  'فعال‌سازی با کلیدِ دستگاهِ دیگر رد می‌شود');
O.licDeactivate(storage);
assert(!O.licIsActive(storage, deviceId), 'پس از غیرفعال‌سازی');

// ── ۷) دورهٔ آزمایشی: ۷ روز، یک‌بار، ضد ساعت ──
let t0 = O.trialStatus(storage);
assert(!t0.exists && !t0.active && t0.daysLeft === 0);
assert(O.trialStart(storage), 'شروع تریال');
assert(!O.trialStart(storage), 'تریال دوباره شروع نمی‌شود (ضدتقلب)');
let t1 = O.trialStatus(storage);
assert(t1.active && t1.daysLeft === 7);
let t2 = O.trialStatus(storage, Date.now() + 6.5 * 864e5);
assert(t2.active && t2.daysLeft === 1, 'روز ۶.۵ → ۱ روز باقی');
let t3 = O.trialStatus(storage, Date.now() + 7.2 * 864e5);
assert(!t3.active && t3.daysLeft === 0, 'پایان تریال');
let t4 = O.trialStatus(storage, Date.now() - 96 * 36e5);
assert(t4.tampered && !t4.active, 'عقب‌کشیدن ساعت → tampered');

console.log('SMOKE LICENSE OK — Ed25519/node:crypto + بُرِدهای مشترک پایتون/JS (دائمی+زمان‌دار)، انقضا، قفل دستگاه، تریال ۷ روزه، ضدساعت');
