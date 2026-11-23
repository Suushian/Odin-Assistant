# گزارش اسکن کامل و دقیق — ODIN Assistant

**تاریخ:** ۲۳ نوامبر ۲۰۲۶ (آذر ۱۴۰۵)
**مخزن:** `Suushian/Odin-Assistant`
**شاخه:** `arena/9ad0d7c8-odin-assistant` (برگرفته از `a620478`)
**نسخهٔ ثبت‌شده در کد:** `1.0.1` (`src/app_paths.py:17`)
**نوع بررسی:** ایستا + اجرای کامل تست‌های آفلاین + راستی‌آزمایی زنجیرهٔ تأمین
**وضعیت تغییرات:** هیچ فایل کد تغییر نکرد؛ فقط همین گزارش به `docs/` افزوده شد.

---

## ۱) خلاصهٔ مدیریتی

این پروژه از نظر **مهندسی نرم‌افزار** بالغ‌تر از میانگین پروژه‌های مشابه است: قراردادهای پلاگین، تست‌های طلایی، پاریتی دو موتور، گیت‌های امنیتی پل اندروید و مستندسازی فارسی گسترده دارد. در این اسکن **آسیب‌پذیری بحرانی** (RCE، نشت کلید خصوصی، اجرای کد از راه دور، یا توکنِ ثبت‌شده در مخزن) پیدا نشد.

با این حال، **پنج موضوع باید پیش از انتشار بعدی حل یا روی دستگاه واقعی تأیید شوند**:

1. **CSP و استایل‌های درون‌خطی:** `style-src 'self'` در `index.html` با **۱۲۷** `style="…"` تولیدشده در JS در تضاد است. اگر WebView استاندارد عمل کند، بخشی از فاصله‌ها/رنگ‌ها/چیدمان از دست می‌رود. این مورد **نیازمند تأیید روی دستگاه** است.
2. **وتوی خبر فوری طلا برای همهٔ نمادها:** هر خبر breaking که جهت آن `XAU` داشته باشد، سیگنال **همهٔ جفت‌ارزها** را وتو می‌کند (`src/judge/scoring.py:279` و معادل JS).
3. **سطل‌بندی امتیاز در آمار:** همهٔ امتیازهای کمتر از ۸ در سطل «۷» ریخته می‌شوند (`src/journal/stats.py:88-95`، `js/journal.js:220-225`)، در حالی که آستانهٔ پیش‌فرض اکنون **۵** است؛ بنابراین ارزیابی «آیا آستانهٔ ۵ درست است؟» با این آمار **معتبر نیست**.
4. **معنای `sent` در ژورنال و نبود نوشتن اتمیک:** پایتون `sent` را «واقعاً به تلگرام رسید» می‌داند و در حالت شبیه‌سازی اصلاً ژورنال نمی‌کند؛ JS همیشه رکورد می‌زند و `sent` را از «تکراری نبودن» می‌سازد. علاوه بر این، نوشتن ژورنال در SharedPreferences به‌صورت read-modify-write است و دو WebView می‌توانند هم‌زمان یک رکورد را از دست بدهند.
5. **ناسازگاری وضعیت لایسنس/رصد در جریان اجرا:** غیرفعال‌سازی لایسنس `S.accessOK` را صفر نمی‌کند (تا تیک ۳۰ ثانیه‌ای یا ریلود، اپ کار می‌کند)؛ «بازنشانی تنظیمات» سرویس پس‌زمینه را با مقدار جدید هم‌گام نمی‌کند؛ و شاخهٔ «رصد خاموش شده» در سرویس، سرویس را نمی‌بندد.

همچنین یک **تست نهفتهٔ شکست‌خورده** در `panel.py:2283` وجود دارد: خودآزمون پنل انتظار `min_score == 7` دارد، ولی `config.yaml:151` و `src/config.py:32` مقدار **۵** دارند. این تست در CI اجرا نمی‌شود، بنابراین سبزیِ فعلی CI آن را پنهان کرده است.

**حکم کلی:** برای توزیع کنترل‌شده (خارج از مارکت، با کاربران فعلی) قابل قبول است؛ برای انتشار عمومیِ بعدی، ابتدا موارد ۱ تا ۵ و هم‌ترازی نسخه/مستندات را اصلاح کنید.

---

## ۱.۱) وضعیت رفع — به‌روزرسانی ۲۰۲۶-۱۱-۲۳

این بخش بعد از اجرای رفع نوشته شده است؛ جزئیات اصلی هر یافته در §۵ دست‌نخورده مانده تا سابقهٔ ممیزی حفظ شود. نسخهٔ کد پس از رفع: **1.0.2**.

| گروه | یافته‌ها | وضعیت |
|---|---|---|
| رفع‌شده با تست | F-01 (CSP `style-src`)، F-02 (وتوی طلا فقط XAU)، F-03/F-31 (سطل‌های امتیاز + گزارش)، F-04 (`sent` صادق + `appendPref` اتمیک + چرخش ژورنال)، F-05/F-06/F-07 (وضعیت سرویس/لایسنس/بازنشانی)، F-08 (آستانهٔ پنل ۵)، F-09 (نسخه/CHANGELOG/نصب‌کننده)، F-10 (فهرست CI؛ حذف `run_parity` مرده)، F-11 (`requirements-test.txt` پین‌شده)، F-12 (bypass فقط سورس)، F-13 (redact توکن)، F-16 (نام یک‌خطی)، F-17/F-18 (MIME + `IS_PENDING`)، F-19/F-33 (نسخه از BuildConfig + تست Java/نصب‌کننده)، F-20 (timeout fetch + پاک‌سازی `pagehide`)، F-23 (pacing هر hop ریدایرکت)، F-30 (gitignore)، F-32 (نمایش تفکیک امتیاز/جهت در UI)، F-34/F-35/F-36 (مستندات)، F-37 (CSP پنل)، F-39 (`postMonitor` خاموش) | ✅ سبز؛ فهرست تست‌ها در §۱.۲ |
| رفع‌شده با مستندسازی/طراحی | F-14 (سیاست بکاپ در `docs/android-fa.md`)، F-15 (مستندات Ø + adaptive icon)، F-26 (پشتیبان رمز keystore)، F-28 (نگهبان monotonic نسبت به تگ) | ✅ با توضیح صادقانه |
| پذیرفته‌شده با ریسک کنترل‌شده | F-21 (۵ فید ثابت + استخر ۴ thread؛ هر فید catch دارد)، F-22 (allowlist نمی‌تواند فیدهای قابل‌تنظیم را مجاز کند؛ فقط https و همان میزبان در ریدایرکت)، F-24 (TLS سیستم؛ pinning اختیاری)، F-25 (یک اعلان زندهٔ عمدی؛ تاریخچه در ژورنال)، F-38 (فونت base64 برای فایل آفلاین)، F-40 (`BootReceiver` فقط `BOOT_COMPLETED` و خطاها catch) | ⚠️ آگاهانه، بدون ادعای رفع کامل |
| باقی‌مانده | F-27 (Gradle wrapper)، F-29 (lint مسدودکننده) | 🚧 بدهی ثبت‌شده |

**محدودیت راستی‌آزمایی:** `panel.py --selftest`/تست‌های Qt در این محیط اجرا نشدند (`PySide6` نصب نیست)؛ APK/Gradle هم بدون Android SDK ساخته نشد. تست‌های آفلاین پایتون، ۲۴ تست JS، `main.py --selftest` و `check_config.py` سبزند. جزئیات در §۱.۲ و پیوست ج.

## ۱.۲) فرمان‌های اجراشده پس از رفع

- `python main.py --selftest` → OK
- `python tests/check_config.py` → OK
- `python tests/test_*.py` (۱۱ فایل) → OK، از جمله `test_judge_rules.py` (۱۹۸ بررسی)
- `node tests/js/smoke_*.js` و `node tests/js/test_*.js` (۲۴ فایل) → OK
- `python tests/manual/test_{journal,judge,veto_report,news_direction,license,alerts,audit_fixes,paths_install}.py` → OK (Qt-only tests در این محیط اجرا نشدند)
- `python -m compileall`، `node --check`، parse YAML/XML → OK
- `python tests/js/gen_fixtures.py`/`run_parity.js` → **حذف شدند** (فیکسچر gitignored و منبع Yahoo منسوخ؛ پوشش از گلدن‌های داور/چرخه می‌آید)

## ۲) دامنه، حجم و روش

### ۲.۱) آنچه بررسی شد

- **پایتون:** ۶۲ ماژول در `src/` (حدود ۱۲٬۳۰۰ خط)، `main.py` (۵۱۸ خط)، `panel.py` (۲٬۴۰۰ خط).
- **اندروید:** ۲۳ ماژول JS در `assets/www/js` (حدود ۹٬۷۰۰ خط) و ۶ کلاس Java (حدود ۱٬۲۰۰ خط).
- **تست‌ها:** ۱۱ فایل `tests/test_*.py`، `tests/check_config.py`، ۲۵ فایل `tests/js/*.js` (۲۴ اجرایی + `run_parity.js`)، و ۱۶ فایل `tests/manual/`.
- **CI و انتشار:** هر سه workflow، اسکریپت‌های ساخت EXE/نصب‌کننده، `release_notes.py`، `make-keystore.sh`، `build.gradle`.
- **مستندات:** README، CHANGELOG، `docs/` (حدود ۳٬۹۰۰ خط)، راهنمای لایسنس، مستندات امنیت/آمادگی/اندروید.
- **زنجیرهٔ تأمین:** محتوای `www/js/nacl.js` با tarball رسمی `tweetnacl@1.0.3` مقایسه شد.

### ۲.۲) آنچه اجرا شد

| بررسی | نتیجه |
|---|---|
| `python main.py --selftest` | ✅ PASS |
| `python tests/check_config.py` | ✅ PASS |
| ۱۱ فایل `tests/test_*.py` | ✅ همه PASS |
| ۲۴ فایل `tests/js/*.js` (به‌جز `run_parity.js`) | ✅ همه PASS |
| ۷ سوئیت دستی آفلاین: `test_license`, `test_journal`, `test_judge`, `test_veto_report`, `test_audit_fixes`, `test_alerts`, `test_paths_install` | ✅ همه PASS |
| `ruff` (مجموعهٔ خطاهای مهلک) | ✅ پاک؛ ۱٬۶۹۰ هشدار گسترده عمدتاً `RUF` فارسی‌محور |
| `node --check` روی همهٔ JS | ✅ پاک |
| راستی‌آزمایی sha256 و diff با TweetNaCl 1.0.3 | ✅ یکسان |
| `git status` پیش از گزارش | ✅ پاک |

### ۲.۳) آنچه اجرا نشد (محدودیت صادقانه)

- **مرورگر/WebView واقعی:** در sandbox مرورگر نصب نیست؛ بنابراین اعمال‌شدن CSP روی `style` قابل بازتولید نبود.
- **دستگاه اندروید:** هیچ تست روی گوشی، Doze، OEM، بازگردانی بکاپ یا WebView قدیمی انجام نشد.
- **ساخت Gradle/APK:** Android SDK و Gradle در sandbox موجود نیست؛ فقط پیکربندی ایستا بررسی شد.
- **تست‌های Qt:** `PySide6` در محیط نصب نبود؛ `test_sharecard.py`، `test_layout_fit.py`، `test_gui_integration.py`، `test_activation_dialog.py`، `test_pages_render.py`، `test_settings_ui.py` و `panel.py --selftest` اجرا نشدند.
- **شبکهٔ زنده:** فقط میزبان‌های GitHub/npm/PyPI در دسترس بودند؛ Twelve Data، تلگرام و فیدهای RSS واقعی آزموده نشدند.
- **`run_parity.js`:** به `tests/js/fixtures.json` نیاز دارد که gitignore شده و موجود نیست؛ همچنین mockهای Yahoo آن با کد امروز هم‌خوان نیستند.

---

## ۳) معماری در یک نگاه

```
┌──────────────────────────── دسکتاپ (Python / PySide6) ────────────────────────────┐
│ main.py / panel.py                                                                  │
│   → src/engine.py  (PipelineRunner؛ ۱۱ مرحلهٔ نام‌دار)                              │
│      collect_market → journal_pre → fundamental → judge → report → dispatch_signals │
│      → price_alerts → chart_cache → journal_post → stats → briefing                │
│   → src/plugins (data, judge, journal, notify, alerts, report)                      │
│   → Twelve Data (تک‌منبع) · تقویم FairEconomy · ۵ فید RSS · تلگرام                 │
│   → signals.jsonl + ژورنال نتیجه + کارنامه                                          │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────── اندروید (WebView + Java) ─────────────────────────────┐
│ MainActivity (WebView محلی، file:///android_asset/www/index.html)                   │
│   → ۲۳ ماژول JS: core/plugins/data/judge/news/journal/calendar/...                  │
│   → Bridge.java: http · prefs · secrets · notify · share/save · service             │
│   → OdinService: WebView بی‌سر با ?svc=1 + زمان‌بندی نیتیو (Handler)                │
│   → Notif (کانال signals/monitor) · BootReceiver · ShareFileProvider                │
│   → SharedPreferences: odin / odin_secrets                                         │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**نکات معماری مهم:**

- موتور تحلیل **دو پیاده‌سازی** دارد (Python و JS) که با تست‌های طلایی/پاریتی هم‌تراز نگه داشته می‌شوند. این تصمیم آگاهانه است، اما هزینهٔ نگهداری و ریسک واگرایی دارد.
- منبع بازار **تک‌منبعی** است (Twelve Data) و هیچ fallback خودکاری به Yahoo/MT5/Binance وجود ندارد؛ این سیاست در کد و تست‌ها صریح است.
- اندروید برای پس‌زمینه یک **WebView دوم** اجرا می‌کند؛ بنابراین دو runtime JS می‌توانند هم‌زمان روی SharedPreferences بنویسند.
- نسخه از یک منبع (`APP_VERSION`) خوانده می‌شود، ولی چند نقطه (Java، batch، installer، docs) هنوز مقدار دستی دارند.

---

## ۴) نقاط قوت (آنچه نباید در بازنویسی از دست برود)

1. **پوشش تست واقعی برای یک پروژهٔ تک‌نفره:** ۱۱ تست پایتون + ۲۴ تست JS + ۷ سوئیت دستی آفلاین، همه سبز. تست‌ها فقط «بدون خطا» نیستند؛ قراردادها، ترتیب مراحل، طلایی‌ها و پاریتی را پین می‌کنند.
2. **معماری پلاگین و قراردادها:** `odin.*@1`، registry/resolver، جداسازی failure و رویدادهای pipeline؛ تغییر منبع داده بدون دست‌زدن به engine ممکن است.
3. **امنیت لایهٔ نمایش:** هیچ `eval`، `new Function`، `document.write` یا `insertAdjacentHTML` پیدا نشد؛ ۱۵ نقطهٔ `innerHTML` با `O.esc` یا ورودی ثابت محافظت می‌شوند؛ تست `test_news_render_xss.js` این را پین می‌کند.
4. **اعتبارسنجی URL:** `safeExternalUrl` سمت JS و `Bridge.openExternal`/`shouldOverrideUrlLoading` سمت Java، user-info و schemeهای غیرمجاز را رد می‌کنند؛ ریدایرکت‌ها محدود و cross-host ممنوع است.
5. **پل HTTP محافظه‌کار:** فقط `http/https`، بدون user-info، فقط GET/POST/HEAD، حداکثر ۵ ریدایرکت، سقف ۱MB درخواست/۴MB پاسخ، timeout اتصال ۲۰s و خواندن ۲۵s، `usesCleartextTraffic=false`.
6. **حریم فایل و بکاپ:** `ShareFileProvider` با `exported=false`، مسیر canonical، `MODE_READ_ONLY`؛ `odin_secrets` در هر دو فایل backup حذف شده است.
7. **لایسنس واقعاً نامتقارن:** Ed25519 خالص‌پایتون + TweetNaCl ۱٫۰٫۳ + پنل صدور آفلاین؛ کلید خصوصی در مخزن نیست؛ نسخهٔ ژورنال لایسنس ۳٫۰؛ تریال ۷ روزه با تشخیص عقب‌کشیدن ساعت.
8. **زنجیرهٔ تأمین crypto راستی‌آزمایی شد:** `www/js/nacl.js` = سرصفحهٔ فارسی + TweetNaCl ۱٫۰٫۳ دست‌نخورده؛ sha256 tarball با مقدار مستندشده یکی است.
9. **کیفیت داده:** اعتبارسنجی کندل‌ها، تشخیص کهنگی، تقویم با TTL ۳۰ دقیقه، اخبار با پنج فید و ضدتکرار؛ تست‌های `test_data_quality` و `test_calendar_quality`.
10. **حسابداری ریسک و ژورنال:** ورود/SL/TP/RR، بستن بر اساس کندل‌های M15 بعد از ورود، ثبت `R` و توضیح علت؛ مسیر «سیگنال → نتیجه → آمار» واقعاً بسته است.
11. **UI فارسی و RTL با تست:** `smoke_layout`، `smoke_theme_parity`، `smoke_icons`، `smoke_ui_polish` و `smoke_brand_identity` جلوی افت‌های چیدمان/ایموجی/تم را می‌گیرند.
12. **صداقت در مستندات:** سلب مسئولیت، «سیگنال پیشنهاد است نه دستور»، هشدار نبود بک‌تست و اذعان به شکستن‌پذیری لایسنس آفلاین.

---

## ۵) یافته‌ها با شدت

> شدت‌ها: **بالا** = اثر مستقیم بر تجربهٔ اصلی/اعتبار سیگنال/یکپارچگی داده؛ **متوسط** = ریسک عملیاتی/نگهداری/امنیت جانبی؛ **کم** = پولیش/مستندات/سخت‌سازی.
> هیچ یافتهٔ «بحرانی» (RCE/نشت کلید خصوصی/توکنِ کامیت‌شده) پیدا نشد.

### ۵.۱) یافته‌های بالا

#### F-01 — CSP با ۱۲۷ استایل درون‌خطی در تضاد است (نیازمند تأیید دستگاه)

**شاهد:**
- `android/app/src/main/assets/www/index.html:10-11`: `style-src 'self'` و `script-src 'self'`.
- در `www/js` دقیقاً **۱۲۷** رخداد `style="…"` وجود دارد (بیشتر فاصله/رنگ/عرض).

**اثر:** طبق استاندارد CSP، وقتی `style-src` بدون `'unsafe-inline'` باشد، **style attribute**های داخل HTML تولیدشده با `innerHTML` نادیده گرفته می‌شوند. این می‌تواند فاصله‌ها، رنگ‌های تأکیدی و بخشی از چیدمان کارت‌ها/مودال‌ها را روی دستگاه خراب کند. چون در sandbox مرورگر/WebView نیست، این مورد **باید روی گوشی** دیده شود. توجه: انتساب‌های CSSOM مثل `el.style.display = ...` مشمول این محدودیت نیستند؛ مشکل فقط attributeهای متنی است.

**پیشنهاد:**
1. روی دستگاه (Android ۷ و ۱۴) صفحه‌های خانه/تنظیمات/مودال/ژورنال را باز و اسکرین‌شات بگیرید.
2. اگر تأیید شد، سریع‌ترین اصلاح: `style-src 'self' 'unsafe-inline'` (با حفظ `script-src 'self'`). راه پاک‌تر: تبدیل ۱۲۷ مورد به کلاس‌های CSS.
3. یک تست به `smoke_layout.js` اضافه کنید که مطمئن شود `style-src` اجازهٔ inline دارد و `script-src` هرگز `'unsafe-inline'`/`'unsafe-eval'` ندارد.

#### F-02 — خبر فوری طلا، سیگنال همهٔ نمادها را وتو می‌کند

**شاهد:** `src/judge/scoring.py:279`:

```python
if base in it.direction or quote in it.direction or "XAU" in it.direction:
```

معادل JS در `judge.js` (`breakingNewsFor`) همین شرط را دارد.

**اثر:** یک تیتر breaking دربارهٔ طلا با جهت `XAU` باعث می‌شود EURUSD، GBPUSD، USDJPY و… هم وتوی «خبر فوری» بخورند. این یک **خطای منطقی** است، نه سیاست محافظه‌کارانهٔ عمدی؛ چون خبر طلا لزوماً به جفت‌ارزهای غیرطلا مربوط نیست.

**پیشنهاد:** شرط را به «نماد خودِ تحلیل» محدود کنید:

```python
gold_pair = base == "XAU" or quote == "XAU"
if base in it.direction or quote in it.direction or (gold_pair and "XAU" in it.direction):
```

سپس دو تست طلایی اضافه کنید: (الف) خبر breaking طلا + EURUSD ⇒ بدون وتو؛ (ب) خبر breaking طلا + XAUUSD ⇒ وتو.

#### F-03 — سطل‌بندی امتیاز، سیگنال‌های ۵ و ۶ را «۷» نشان می‌دهد

**شاهد:**
- `src/journal/stats.py:88-95` و `android/.../js/journal.js:220-225`: هر امتیاز `< 8` به سطل `"۷"` می‌رود.
- `src/report/journal.py:90-98` فقط سطل‌های `۷`, `۸`, `۹`, `۱۰–۱۱` را چاپ می‌کند.
- آستانهٔ پیش‌فرض در `config.yaml:151` و `src/config.py:32` **۵** است.

**اثر:** بخش «به تفکیک امتیاز» کارنامه، سیگنال‌های ۵ و ۶ را با ۷ ادغام می‌کند. بنابراین مقایسهٔ نرخ برد «۵ در برابر ۷» — که برای ارزیابی تغییر آستانه از ۷ به ۵ لازم است — **گمراه‌کننده** است. این دقیقاً همان «حلقهٔ صداقت» است که مستندات وعده داده‌اند.

**پیشنهاد:** سطل‌ها را به `۵`, `۶`, `۷`, `۸`, `۹`, `۱۰–۱۱` تغییر دهید، حلقهٔ گزارش را داینامیک کنید، و تست/گلدن جدید بسازید. برای دادهٔ قدیمی، مهاجرت یا برچسب «سطل قدیمی» در نظر بگیرید.

#### F-04 — `sent` در ژورنال دو معنای متفاوت دارد + نوشتن غیراتمیک و رشد نامحدود

**شاهد:**
- پایتون `src/engine.py:552-579`: در حالت simulated اصلاً `journal_signal` صدا زده نمی‌شود؛ در حالت واقعی `sent` = نتیجهٔ واقعی ارسال تلگرام (موفق/ناموفق).
- JS `android/.../js/app.js:437-441`: همیشه `appendRec(jn.signalToJournal(sig, dec.go))`؛ `dec.go` یعنی «تکراری نیست»، نه «اعلان واقعاً رفت».
- `journal.js:79`: `sent: rec.sent !== false` — رکوردهای فاقد فیلد هم «sent» شمرده می‌شوند.
- `journal.js:23-25`: کل `journal.jsonl` از SharedPreferences خوانده و دوباره نوشته می‌شود (read-modify-write).
- `report/journal.py:132` `sent` را «به تلگرام رفت» تفسیر می‌کند.

**اثر:**
1. کارنامهٔ اندروید ممکن است سیگنالی را «ارسال‌شده» بشمارد که به‌خاطر خاموش بودن اعلان‌ها یا خطای پل، هرگز به کاربر نرسیده است.
2. دو WebView (رابط + سرویس) می‌توانند هم‌زمان append کنند؛ چون append در JS و روی یک رشتهٔ SharedPreferences است، یکی از رکوردها می‌تواند گم شود.
3. ژورنال هیچ سقف/چرخش/فشرده‌سازی ندارد؛ با رشد سیگنال‌ها، خواندن/نوشتن کل رشته کندتر و backup سنگین‌تر می‌شود.

**پیشنهاد:**
- معنای `sent` را صریح کنید: `delivered` (اعلان واقعاً نمایش داده شد) در برابر `analyzed`/`emitted`.
- `Bridge.notify` را به `boolean` برگردانید (یا `areNotificationsEnabled` را قبل از ثبت چک کنید) و همان را در ژورنال بنویسید.
- یک متد نیتیو `appendJournal(String line)` با `synchronized` و نوشتن فایل/صف اضافه کنید؛ یا حداقل `setPref` را داخل یک قفل نیتیو با read-modify-write اتمیک انجام دهید.
- چرخش دوره‌ای (مثلاً ۵٬۰۰۰ رکورد) + خروجی/آرشیو.

### ۵.۲) یافته‌های متوسط

#### F-05 — غیرفعال‌سازی لایسنس، دسترسی در همان نشست را قطع نمی‌کند

**شاهد:** `android/.../js/app.js:845-850`: `O.licDeactivate`، `S.licensed = false`، `stopBackground()`، ناوبری؛ اما `S.accessOK` و `S.licenseInfo` به‌روز نمی‌شوند. گیت تحلیل/چرخه به `S.accessOK` نگاه می‌کند (`app.js:322`, `563`). تیک ۳۰ ثانیه‌ای بعدی (`app.js:1142-1147`) آن را بازمحاسبه می‌کند و «خودترمیمی» می‌شود.

**اثر:** کاربر «غیرفعال شد» را می‌بیند ولی تا ۳۰ ثانیه یا تا ریلود، تحلیل/چرخه همچنان اجرا می‌شود. همچنین اگر تریال هنوز فعال باشد، باید مشخص شود که دسترسی تریال برمی‌گردد یا نه.

**پیشنهاد:**

```js
O.licDeactivate(S.storage);
S.licensed = false;
S.licenseInfo = null;
S.trial = O.trialStatus(S.storage);
S.accessOK = !!(S.trial && S.trial.active);
O.native.stopBackground();
O.renderHeaderStatus();
```

و متن مودال را با همین رفتار هم‌تراز کنید («اگر تریال فعال باشد تا پایان آن کار می‌کند»).

#### F-06 — بازنشانی تنظیمات، سرویس پس‌زمینه را هم‌گام نمی‌کند

**شاهد:** `app.js:865-871`: `S.settings = deep(DEFAULT_SETTINGS)` (شامل `background_enabled: true`)، `saveSettings()`، ناوبری؛ هیچ `startBackground`/`stopBackground` صدا زده نمی‌شود.

**اثر:** اگر کاربر قبلاً رصد را خاموش کرده باشد و «بازنشانی» بزند، UI می‌گوید روشن است ولی سرویس نیتیو خاموش می‌ماند (یا برعکس، با تغییر آیندهٔ پیش‌فرض). تا باز شدن بعدی اپ/بوت، وضعیت ناهم‌گام است.

**پیشنهاد:** بعد از بازنشانی:

```js
if (S.settings.background_enabled) O.native.startBackground();
else O.native.stopBackground();
```

#### F-07 — شاخهٔ «رصد خاموش است» سرویس را نمی‌بندد

**شاهد:** `app.js:684-687`: اگر `background_enabled === false` باشد، اعلان «متوقف» می‌گذارد و `bgCycleDone(30)` را صدا می‌زند و برمی‌گردد؛ سرویس و اعلان ماندگار زنده می‌مانند.

**اثر:** در مسیرهایی که تنظیمات از بیرون UI عوض شود (بکاپ/ریستور، ویرایش دستی، خطای UI)، سرویس هر ۳۰ دقیقه بیدار می‌شود و اعلان «متوقف» را نگه می‌دارد؛ باتری و شفافیت.

**پیشنهاد:** در همین شاخه `O.native.stopBackground()` را صدا بزنید و `return` کنید؛ زمان‌بندی بعدی لازم نیست.

#### F-08 — `panel.py --selftest` با آستانهٔ ۵ شکست می‌خورد

**شاهد:**
- `panel.py:2283`: `assert ... cfg3["judge"]["min_score"] == 7`
- `config.yaml:151` و `src/config.py:32`: مقدار **۵**
- `panel.py:1649`: fallback `int(j.get("min_score", 7))`

**اثر:** این یک تست **نهفتهٔ شکست‌خورده** است که چون `panel.py --selftest` در CI اجرا نمی‌شود، دیده نشده. اگر توسعه‌دهنده‌ای با PySide6 اجرا کند، بلافاصله fail می‌شود و اعتماد به بقیهٔ خودآزمون‌ها را می‌برد.

**پیشنهاد:** assertion را به مقدار `config.yaml` (یا مقدار پیش‌فرض ۵) تغییر دهید؛ fallback خط ۱۶۴۹ را هم ۵ کنید یا از config بخوانید. سپس `panel.py --selftest` را در یک job اختیاری (با `QT_QPA_PLATFORM=offscreen`) اجرا کنید.

#### F-09 — رانش نسخه، آدرس مخزن و یادداشت‌های انتشار

**شاهد:**
- `src/app_paths.py:17` → `1.0.1`؛ `docs/security-review-fa.md:17,67` از «رفع شد (v1.0.2)» حرف می‌زند.
- `CHANGELOG.md:43` و `:107` **دو بخش `[1.0.1]`** دارند (۲۰۲۶-۱۰-۲۷ و ۲۰۲۶-۱۱-۲۱). `installer/release_notes.py` اولین تطابق را برمی‌دارد، بنابراین یادداشت انتشار ممکن است اصلاحات ۲۱ نوامبر را نشان ندهد.
- `docs/README.md:16,48` و `installer/odin.iss:25` هنوز `KhodeSushianm/Trading-Bot` و `v0.21.0` را دارند.
- `build_exe.bat:50-51` نسخه را دستی `1.0.1` می‌گذارد؛ `Bridge.java:56,286` هم UA و fallback نسخه را دستی `1.0.1` دارد.
- `CHANGELOG.md` می‌گوید UA از `0.28.0` به `1.0.1` اصلاح شد، ولی مقدار **همچنان hardcode** است؛ نسخهٔ بعدی دوباره کهنه می‌شود.

**اثر:** کاربر/توسعه‌دهنده نمی‌داند نسخهٔ رسمی کدام است؛ یادداشت انتشار می‌تواند ناقص باشد؛ لینک‌های قدیمی به مخزن اشتباه می‌روند.

**پیشنهاد:** یک تصمیم واحد بگیرید (مثلاً «نسخهٔ اندروید 1.0.2، ویندوز منجمد در 0.21»)، `APP_VERSION` را یک‌بار bump کنید، دو بخش CHANGELOG را ادغام کنید، `release_notes` را به آخرین بخش یا بخش یکتا محدود کنید، و یک تست «هیچ `KhodeSushianm` و هیچ نسخهٔ سه‌بخشیِ متناقض در فایل‌های منتشرشده نباشد» اضافه کنید.

#### F-10 — شکاف‌های CI و پاریتی مرده

**شاهد:**
- `build-release.yml` فهرست JS را دارد اما `test_news_dedupe_order.js` و `run_parity.js` را **ندارد**.
- `build-android.yml` (بیلد اصلی) `smoke_service.js`، `smoke_ui_polish.js` و `test_pipeline_events.js` را ندارد؛ `build-android-debug.yml` همین سه مورد به‌علاوهٔ `test_twelvedata.js` را ندارد. (این تست‌ها در `build-release` اجرا می‌شوند، ولی بیلد APK مستقل از آن‌ها سبز می‌شود.)
- `tests/js/run_parity.js` در هیچ workflow اجرا نمی‌شود، به `fixtures.json` (gitignore) نیاز دارد، و mockهای Yahoo آن (`:179-189`) با کد امروز (Yahoo حذف شده) هم‌خوان نیستند.
- `build-release.yml` فقط تست است؛ artifact EXE نمی‌سازد. `lint` در Gradle با `abortOnError false` و `checkReleaseBuilds false` عملاً غیرمسدودکننده است.
- هیچ تست instrumentation/Robolectric برای Bridge/Service/Provider وجود ندارد.

**اثر:** تغییرات «فقط اندرویدی» یا «فقط داده» می‌توانند بی‌صدا از CI رد شوند؛ پاریتی دو موتور عملاً به گلدن‌های دستی متکی است، نه یک تست زنده.

**پیشنهاد:** همهٔ فایل‌های `tests/js` را در یک matrix اجرا کنید (به‌جز پاریتیِ نیازمند fixture)؛ `run_parity` را با fixture تولیدشده و mockهای به‌روز احیا یا حذف کنید؛ یک job lint با `abortOnError true` برای فایل‌های Java اضافه کنید؛ حداقل یک تست instrumented برای `Bridge.validateHttpUrl`/`ShareFileProvider`/`BootReceiver` بنویسید.

#### F-11 — وابستگی‌های پایتون pin نشده‌اند و یکی غیررسمی است

**شاهد:** `requirements.txt`: `pandas>=2.0`, `numpy>=1.24`, `PyYAML>=6.0`, `requests>=2.31`, `feedparser>=6.0`, `PySide6>=6.6`, `tradingview-ta>=3.3.0`. CI فقط `pandas numpy PyYAML requests feedparser` را نصب می‌کند و Python را ۳٫۱۱ پین می‌کند.

**اثر:** یک نصب تازه ممکن است pandas 3 یا نسخهٔ ناسازگار PySide6 بگیرد؛ `tradingview-ta` API غیررسمی است و می‌تواند بدون هشدار بشکند؛ reproducibility پایین.

**پیشنهاد:** `requirements.lock` یا `constraints.txt` با نسخه‌های تست‌شده و hash؛ `tradingview-ta` را پشت extra/اختیاری ببرید؛ در CI همان lock را نصب کنید.

#### F-12 — دروازهٔ لایسنس دسکتاپ قابل دور زدن است و CLI گیت ندارد

**شاهد:**
- `src/license.py:502-506`: `ODIN_SKIP_LICENSE=1` یا `QT_QPA_PLATFORM=offscreen` → bypass.
- `main.py` حالت‌های `--alerts`, `--signals`, `--journal`, `--briefing`, `--nightly` را بدون `check_and_enforce_license` اجرا می‌کند؛ گیت فقط در `MainWindow` (`panel.py:292-299`) است.
- `LICENSE_GUIDE.md:149` این bypass را مستند کرده است.

**اثر:** با `ODIN_SKIP_LICENSE=1` (یا `QT_QPA_PLATFORM=offscreen` برای اجرای بدون پنجره) می‌توان بدون لایسنس اجرا کرد؛ مدل تجاری آفلاین به‌هرحال قابل patch است، اما این یک دور زدن **بدون patch** است. CLI نیز عملاً نسخهٔ رایگان موتور است.

**پیشنهاد:** bypass را فقط در build توسعه/CI مجاز کنید (مثلاً `if not getattr(sys, "frozen", False)` یا یک flag ساخت)؛ برای CLI یک سیاست صریح (رایگان/نیازمند لایسنس) تعیین و همان را اجرا کنید؛ برای نسخهٔ تجاری جدی، فعال‌سازی آنلاین با سرور امضا.

#### F-13 — احتمال نشت توکن تلگرام در متن خطا

**شاهد:** `src/notify/telegram.py:74-104`: توکن در URL است؛ در `except`، `str(e)[:80]` به UI/لاگ برمی‌گردد. بعضی خطاهای `requests` آدرس URL را در متن استثنا می‌آورند.

**اثر:** توکن بات می‌تواند در پیام خطای پنل یا لاگ دیده شود (نه در مخزن، ولی در محیط کاربر).

**پیشنهاد:** قبل از نمایش، `token` را از پیام حذف/redact کنید؛ URL کامل را لاگ نکنید؛ از `requests.Session` با `params` به‌جای path (تا حد امکان) یا یک تابع `scrub_secrets()` استفاده کنید.

#### F-14 — بکاپ اندروید شامل ژورنال/تنظیمات است، نه اسرار

**شاهد:** `AndroidManifest.xml:24` `allowBackup=true`؛ `res/xml/backup_rules.xml` و `data_extraction_rules.xml` `odin_secrets` را حذف می‌کنند ولی `odin` (شامل `journal.jsonl`, `settings`, `license.dat`, `trial.dat`) را نه.

**اثر:** تاریخچهٔ معاملات/سیگنال‌ها و تنظیمات (نه API key) به Google Backup می‌رود. `license.dat` به دستگاه گره خورده و در بازیابی همان دستگاه مفید است؛ اما حریم خصوصی ژورنال باید آگاهانه باشد.

**پیشنهاد:** تصمیم صریح بگیرید: یا `journal.jsonl` را از بکاپ خارج کنید (با یک کلید جدا)، یا در سیاست حریم خصوصی/راهنما توضیح دهید. API key در `odin_secrets` درست جدا شده است.

### ۵.۳) یافته‌های کم / سخت‌سازی

| # | موضوع | شاهد / اثر | پیشنهاد |
|---|---|---|---|
| F-15 | آیکون لانچر با مستندات نمی‌خواند | `res/drawable/odin_launcher_icon.xml` یک Ø سفید روی زمینهٔ مشکی است؛ `CHANGELOG.md:39` و `docs/android-fa.md:10` از «حباب گفت‌وگوی آبی» حرف می‌زنند؛ `mipmap-anydpi-v26` وجود ندارد | یا آیکون آبی را پیاده کنید یا مستندات را اصلاح کنید؛ adaptive icon اضافه کنید |
| F-16 | نام برنامه دوخطی | `res/values/strings.xml`: `Odin Assistant\nSushian` | اگر دوخطی عمدی است مستند کنید؛ وگرنه یک نام واحد |
| F-17 | MIME ذخیرهٔ فایل | `Bridge.saveDownload` همیشه `application/json` می‌دهد | MIME را از پسوند/نوع فایل انتخاب کنید |
| F-18 | MediaStore ناقص | `Bridge.saveImage` روی API 29+ `IS_PENDING` را ست نمی‌کند | الگوی استاندارد MediaStore با `IS_PENDING` |
| F-19 | UA و نسخهٔ hardcode | `Bridge.java:56,286` | از `BuildConfig.VERSION_NAME` و `Build.VERSION.RELEASE` استفاده کنید؛ تست نسخه را به Java هم بکشید |
| F-20 | نقشهٔ callback بدون پاک‌سازی | `data.js:30-55` فقط با `O.httpDone` پاک می‌شود؛ fetch fallback `AbortController` ندارد | timeout/abort و cleanup در `pagehide` |
| F-21 | بارگذاری موازی نامحدود اخبار | `data.js:438` `Promise.all` روی ۵ فید؛ pool نیتیو ۴ تایی | `Promise.allSettled` + سقف هم‌زمانی |
| F-22 | نبود allowlist مقصد اولیه | `Bridge.http` هر میزبان https را می‌پذیرد؛ ریدایرکت cross-host و https→http مسدود است، اما allowlist مقصد اولیه ندارد | برای Twelve Data/تلگرام/فیدها allowlist یا حداقل لاگ میزبان |
| F-23 | pacing فقط برای میزبان اولیه | `paceTwelveData` یک‌بار قبل از حلقه، بر اساس میزبان اولیه اجرا می‌شود؛ ریدایرکت همان میزبان دوباره pace نمی‌شود | در صورت نیاز، هر تلاش شبکهای را pace/شمارش کنید (رفتار فعلی امن است، فقط سهمیه را دقیق مدل نمی‌کند) |
| F-24 | گواهی TLS pin نمی‌شود | `HttpURLConnection` با اعتبارسنجی پیش‌فرض سیستم | pinning اختیاری + مستندسازی چرخش گواهی |
| F-25 | اعلان سیگنال با ID ثابت | `Notif.SIGNALS_ID=1001` اعلان قبلی را جایگزین می‌کند | اگر تاریخچه مهم است، ID افزایشی/گروه‌بندی |
| F-26 | کلید امضا غیرقابل بازیابی | `make-keystore.sh` رمز تصادفی ۲۴ کاراکتری را یک‌بار چاپ می‌کند و اگر `.jks` باشد خارج می‌شود؛ `.jks` و properties gitignore‌اند | روند پشتیبان‌گیری رمز (مدیر رمز/کاغذ امن) + تست بازیابی |
| F-27 | Gradle wrapper ندارد | CI با `gradle 8.7` نصب‌شده کار می‌کند؛ توسعهٔ محلی به Gradle سیستم وابسته است | `gradlew` + `gradle-wrapper.properties` را commit کنید |
| F-28 | نگهبان versionCode ضعیف | `build-android.yml:169` فقط `> 1900` را چک می‌کند؛ نسخهٔ فعلی 10001 است | monotonic check نسبت به آخرین tag/release |
| F-29 | lint غیرمسدودکننده | `build.gradle`: `abortOnError false` و `checkReleaseBuilds false` | lint روی فایل‌های تغییرکرده با fatal error |
| F-30 | `sent_signals.json` در gitignore نیست | `src/engine.py:281`؛ معمولاً در `data/cache/` است، ولی در portable ممکن است ریشه بیفتد | `/sent_signals.json` و `/cache/` را ignore کنید |
| F-31 | گزارش فقط سطل‌های ۷+ را چاپ می‌کند | `src/report/journal.py:90-98` | با F-03 یکجا اصلاح شود |
| F-32 | آمارهای JS بلااستفاده | `journal.js` `by_direction/by_score/by_evidence` را می‌سازد ولی `ui.js` مصرف نمی‌کند | یا در UI نشان دهید یا حذف/مستند کنید |
| F-33 | تست نسخه فقط `www` را می‌بیند | `smoke_theme_parity.js:445-509` | Java/installer/batch را هم اسکن کنید |
| F-34 | مستندات متناقض | `docs/project-readiness-review-fa.md` در بنر می‌گوید XSS/redirect رفع شد، در §۱ هنوز «اعتبارسنجی نشده» است | نسخهٔ تاریخی را واضح‌تر ببندید یا بخش §۱ را به‌روز کنید |
| F-35 | README دستی/CI قدیمی | `tests/manual/README.md` فقط ۴ تست را فهرست می‌کند ولی ۱۶ فایل وجود دارد؛ می‌گوید «هر سه» در حالی که سه فرمان است | فهرست را از workflow تولید یا کامل کنید |
| F-36 | `docs/README` و installer | لینک `Trading-Bot` و `v0.21.0` | آدرس/نسخه را یکدست کنید |
| F-37 | پنل صدور CSP ندارد | `LICENSE PANEL.html` فایل محلی و بدون ورودی غیرقابل‌اعتماد است | در صورت میزبانی وب، CSP اضافه کنید |
| F-38 | `LICENSE PANEL.html` سنگین | فونت TTF به‌صورت base64 (حدود ۵۰۰KB) | برای فایل آفلاین قابل قبول است؛ اگر حجم مهم شد subset کنید |
| F-39 | اعلان `monitor` در حالت خاموش می‌ماند | `Notif.postMonitor` هنگام خاموشی هم اعلان می‌گذارد | با F-07 یکجا اصلاح شود |
| F-40 | `BootReceiver` exported | فقط `BOOT_COMPLETED` محافظت‌شده را می‌پذیرد | قابل قبول؛ در صورت امکان `exported=false` را با رفتار سیستم تست کنید |

---

## ۶) امنیت: جمع‌بندی و مدل تهدید

### ۶.۱) آنچه خوب است

- **بدون اجرای کد پویا:** هیچ `eval`/`new Function`/`document.write`/`insertAdjacentHTML` نیست.
- **XSS:** خروجی‌های خبر/ژورنال/خطا با `O.esc` escape می‌شوند؛ تست اختصاصی `test_news_render_xss.js` دارد. لینک‌ها `href="#"` + `data-ext` هستند و فقط از طریق `safeExternalUrl` باز می‌شوند.
- **پل بومی:** `addJavascriptInterface` فقط روی صفحهٔ محلی `file:///android_asset` نصب می‌شود؛ `validateHttpUrl` فقط http/https بدون user-info؛ `openExternal` هم همان محدودیت را دارد.
- **حریم فایل:** `ShareFileProvider` با authority اختصاصی، `exported=false`، canonical-prefix check و `MODE_READ_ONLY`.
- **بکاپ:** `odin_secrets` در هر دو XML حذف شده؛ API key در `odin_secrets` نگه داشته می‌شود و از `settings` حذف می‌شود.
- **شبکه:** `usesCleartextTraffic=false`؛ هیچ URL دادهٔ plaintext در مسیرهای اصلی پیدا نشد (پل، برای سازگاری، خودِ http را می‌پذیرد ولی HTTPS را ترجیح می‌دهد).
- **لایسنس:** Ed25519 واقعی؛ کلید خصوصی در مخزن نیست (`*.secret` ignore)؛ تست بردی سه‌زبانه؛ پنل آفلاین فقط کلید عمومی دارد.
- **زنجیرهٔ تأمین crypto:** TweetNaCl ۱٫۰٫۳ دست‌نخورده و با checksum تأییدشده.
- **بدون secret کامیت‌شده:** grep روی توکن/کلید/keystore چیزی پیدا نکرد؛ `.gitignore` درست است.

### ۶.۲) باقی‌مانده‌ها

| ریسک | شدت | توضیح |
|---|---|---|
| CSP/inline style | متوسط تا بالا (عملکردی) | F-01؛ نه نشت داده، ولی می‌تواند UI را بشکند |
| توکن در پیام خطا | کم تا متوسط | F-13 |
| بدون pinning/allowlist | کم | F-22/F-24؛ TLS کافی است ولی سطح حملهٔ supply-chain باقی است |
| بکاپ ژورنال | کم (حریم خصوصی) | F-14 |
| لایسنس آفلاین | متوسط (تجاری) | F-12؛ ذاتیِ مدل آفلاین است و مستند هم شده |
| SharedPreferences plaintext | کم | API key رمزنگاری‌شده نیست؛ محافظت = sandbox + عدم بکاپ |
| `allowBackup` + `adb backup` | کم | اگر دستگاه روت/دیباگ باشد، ژورنال/تنظیمات قابل استخراج است |

**نتیجهٔ امنیتی:** برای یک اپ آفلاینِ خارج از مارکت، مدل تهدید معقول است. بزرگ‌ترین ریسک باقی‌مانده، **خطای پیکربندی CSP** و **نشت توکن در متن خطا** است؛ نه نفوذ از بیرون.

---

## ۷) درستی سیگنال و داده

### ۷.۱) نقاط قوت

- **تک‌منبعی بودن داده** تصادفی نیست: `data_source` فقط `twelvedata` پذیرفته می‌شود و تست `test_data_fallback` منابع حذف‌شده را رد می‌کند.
- **اعتبارسنجی کیفیت:** تعداد کندل، شکاف، کهنگی، سازگاری M15/H1/H4؛ تست‌های `test_data_quality` و `test_twelvedata_source`.
- **تقویم:** TTL ۳۰ دقیقه، کش، وتوی رویداد پراثر با پنجرهٔ زمانی؛ تست `test_calendar_quality`.
- **اخبار:** پنج فید، dedupe با md5، تشخیص کهنگی، حذف roundup/سؤال، قاعدهٔ مداخلهٔ JPY؛ `test_news_dedupe_order` و `test_source_freshness`.
- **داور:** ۷ وتو + ۸ شاهد + ریاضی SL/TP/RR؛ گلدن‌های ۵۸ سناریویی در JS و پایتون.
- **ژورنال:** `sid` مشترک، JSONL با تحمل خطای خط خراب، بستن بر اساس M15 بعد از ورود، `R` و یادداشت.

### ۷.۲) محدودیت‌های واقعی (نه باگ)

- **بدون بک‌تست/کالیبراسیون آماری:** هیچ ادعای نرخ برد معتبری وجود ندارد؛ خود مستندات هم این را می‌گوید. آمار ژورنال فقط «پس‌رویدادی» است.
- **جهت خبر از تیتر:** `score_text` جهت را عمدتاً از عنوان می‌گیرد؛ خلاصه فقط برای تشخیص ارز استفاده می‌شود. تیترهای مبهم/کنایه‌ای می‌توانند اشتباه دسته‌بندی شوند.
- **وتوی طلا:** F-02 یک باگ است، نه محدودیت.
- **تک منبع:** قطعی Twelve Data = توقف تحلیل (بدون fallback)، که سیاست امنیتی است ولی دسترس‌پذیری را کم می‌کند.
- **زمان‌بندی:** حداقل ۳۰ دقیقه برای ۸ نماد با پلن رایگان منطقی است؛ اما هیچ retry/backoff برای 429 وجود ندارد (`twelvedata_source.py:67-77`).
- **اخبار سریالی:** ۵ فید با timeout ۱۵ ثانیه در پایتون به‌صورت سری = تا ۷۵ ثانیه در بدترین حالت؛ روی UI دسکتاپ محسوس است.

---

## ۸) لایسنس و تریال: جزئیات

| مورد | وضعیت | توضیح |
|---|---|---|
| الگوریتم | ✅ Ed25519 (RFC 8032) | `src/license_ed25519.py`, `js/nacl.js`, پنل خالص-JS |
| کلید عمومی همسان | ✅ | همان مقدار در سه پیاده‌سازی؛ تست `smoke_license` |
| کلید خصوصی | ✅ خارج از مخزن | `installer/odin-license.secret` ignore؛ در این checkout موجود نیست |
| قالب کلید | ✅ ۱۰۳ / ۱۱۰ نویسه | Base32 + پسوند `-YYMMDD`؛ جداکننده/حروف کوچک پذیرفته می‌شود |
| قفل دستگاه | ✅ | `device_code` از SSAID/هش پایدار؛ کلید دستگاه دیگر رد می‌شود |
| انقضا | ✅ | تاریخ داخل کلید؛ مقایسهٔ محلی |
| تریال ۷ روزه | ✅ | `trial.dat`، `last_seen`، تشخیص عقب‌کشیدن ۴۸ ساعته |
| غیرفعال‌سازی | ⚠️ F-05 | فایل حذف می‌شود ولی `accessOK` تا تیک بعدی نمی‌افتد |
| بایپس | ⚠️ F-12 | `ODIN_SKIP_LICENSE=1` یا `offscreen` |
| نشت کلید | ✅ | هیچ مسیر لاگ/خطایی کلید خصوصی را چاپ نمی‌کند |
| resilience | ✅/⚠️ | آفلاین قابل patch است (ذاتی)؛ مستند شده |

**نکته:** کاهش آستانهٔ ۷→۵ در CHANGELOG آمده و در `config.yaml`/`DEFAULT_SETTINGS` اعمال شده؛ اما `panel.py` و چند تست قدیمی هنوز ۷ را انتظار دارند. این یک **ناسازگاری واقعی** است، نه صرفاً سلیقه.

---

## ۹) پیشنهادهای اجرایی (به ترتیب اولویت)

### P0 — قبل از انتشار بعدی (۱ تا ۳ روز)

1. **F-01:** روی دستگاه واقعی تست کنید؛ سپس `style-src 'self' 'unsafe-inline'` یا تبدیل استایل‌ها به کلاس. تست CSP اضافه کنید.
2. **F-02:** وتوی خبر طلا را به نماد خودش محدود کنید + دو تست طلایی.
3. **F-03:** سطل‌های امتیاز را ۵/۶/۷/۸/۹/۱۰–۱۱ کنید و گزارش را داینامیک کنید.
4. **F-04:** معنای `sent` را یکسان کنید؛ نوشتن ژورنال را اتمیک/نیتیو کنید؛ سقف/چرخش بگذارید.
5. **F-05/F-06/F-07:** وضعیت `accessOK`، بازنشانی تنظیمات و توقف سرویس را هم‌گام کنید.
6. **F-08:** assertion پنل را ۵ کنید؛ `panel.py --selftest` را در CI اختیاری اجرا کنید.
7. **F-09:** نسخه/CHANGELOG/لینک‌ها را یکدست کنید؛ یادداشت انتشار را از بخش یکتا بخوانید.

### P1 — یک اسپرینت

8. **F-10:** `test_news_dedupe_order.js` را به `build-release` اضافه کنید؛ تست‌های جاافتاده را به workflow بیلد اندروید/دیباگ برگردانید؛ `run_parity` را با fixture/به‌روزرسانی احیا یا حذف کنید.
9. **F-11:** lockfile/constraints و pin کردن pandas/numpy/PySide6؛ `tradingview-ta` را اختیاری کنید.
10. **F-12:** bypass را به build توسعه محدود کنید؛ سیاست CLI را مشخص کنید.
11. **F-13:** redact توکن در خطاها.
12. **F-14:** تصمیم مستند دربارهٔ بکاپ ژورنال.
13. **F-19/F-27/F-28:** نسخهٔ Java از `BuildConfig`، افزودن wrapper، monotonic version check.
14. **تست دستگاه:** چک‌لیست Android 7/13/14 + Doze + بوت + بکاپ + آپدیت درجا.

### P2 — بهبود مستمر

15. آیکون adaptive و هم‌ترازی مستندات (F-15/F-16).
16. MediaStore/MIME (F-17/F-18).
17. allowlist/pinning اختیاری (F-22/F-24).
18. چرخش/خروجی ژورنال و آمارهای UI (F-31/F-32).
19. یکدست‌سازی مستندات تاریخی/راهنمای تست (F-34/F-35/F-36).
20. در بلندمدت: فعال‌سازی آنلاین برای لایسنس، بک‌تست/کالیبراسیون واقعی، و حذف تدریجی موتور دوم یا جایگزینی پاریتی با تولید کد از یک منبع.

---

## ۱۰) جمع‌بندی نهایی

- **کیفیت مهندسی:** بالا برای یک پروژهٔ مستقل؛ تست‌ها واقعاً محافظ رگرسیون‌اند، نه تشریفاتی.
- **امنیت:** هیچ یافتهٔ بحرانی؛ نقاط قوت جدی (CSP، escape، Bridge، FileProvider، بکاپ، Ed25519). ریسک‌های باقی‌مانده قابل مدیریت‌اند.
- **درستی محصول:** دو باگ واقعی (وتوی طلا و سطل امتیاز) و یک ناسازگاری داده (ژورنال `sent`) باید قبل از ادعای «آمار قابل اتکا» حل شوند.
- **عملیات/انتشار:** بزرگ‌ترین بدهی، **رانش نسخه و مستندات** و **شکاف‌های CI** است؛ نه کد هسته.
- **آمادگی:** برای کاربران فعلی و توزیع کنترل‌شده: بله. برای انتشار عمومی بعدی: پس از P0، بله.

> این گزارش یک ممیزی ایستا/تست آفلاین است، نه تست نفوذ کامل، نه تأیید سودآوری، و نه جایگزین تست روی دستگاه. هر یافتهٔ «نیازمند تأیید» باید روی سخت‌افزار واقعی بازتولید شود.

---

## پیوست الف — نقشهٔ فایل‌های کلیدی

| موضوع | فایل/خط |
|---|---|
| نسخهٔ واحد | `src/app_paths.py:17` |
| CSP | `android/app/src/main/assets/www/index.html:10-11` |
| وتوی طلا | `src/judge/scoring.py:279` / `www/js/judge.js` |
| سطل امتیاز | `src/journal/stats.py:88-95` / `www/js/journal.js:220-225` |
| ژورنال JS | `www/js/journal.js:23-25,79` |
| ارسال/ژورنال پایتون | `src/engine.py:552-579` |
| غیرفعال‌سازی | `www/js/app.js:845-850` |
| بازنشانی تنظیمات | `www/js/app.js:865-871` |
| شاخهٔ رصد خاموش | `www/js/app.js:684-687` |
| خودآزمون پنل | `panel.py:2283` |
| بایپس لایسنس | `src/license.py:502-506` |
| توکن تلگرام | `src/notify/telegram.py:74-104` |
| Bridge | `android/.../Bridge.java:56,79-230,286` |
| سرویس | `android/.../OdinService.java:44-140` |
| اعلان | `android/.../Notif.java:26-140` |
| بکاپ | `android/app/src/main/res/xml/backup_rules.xml`, `data_extraction_rules.xml` |
| آیکون | `android/app/src/main/res/drawable/odin_launcher_icon.xml` |
| CHANGELOG تکراری | `CHANGELOG.md:43,107` |
| یادداشت انتشار | `installer/release_notes.py:61-88,97` |
| CI اصلی | `.github/workflows/build-release.yml` |
| CI اندروید | `.github/workflows/build-android.yml` |
| CI دیباگ | `.github/workflows/build-android-debug.yml` |

## پیوست ب — فرمان‌های بازتولید

```bash
# پایتون
python main.py --selftest
python tests/check_config.py
for f in tests/test_*.py; do python "$f"; done

# JS (به‌جز پاریتیِ نیازمند fixture)
for f in tests/js/*.js; do
  case "$f" in *run_parity.js) continue;; esac
  node "$f"
done

# دستی آفلاین
for t in test_license test_journal test_judge test_veto_report \
         test_audit_fixes test_alerts test_paths_install; do
  python "tests/manual/$t.py"
done

# زنجیرهٔ تأمین crypto
curl -sL https://registry.npmjs.org/tweetnacl/-/tweetnacl-1.0.3.tgz -o /tmp/t.tgz
sha256sum /tmp/t.tgz          # باید 5f8dc49c…b9e102 باشد
tar -xzf /tmp/t.tgz -C /tmp
tail -n +12 www/js/nacl.js | diff - /tmp/package/nacl.js
```

## پیوست ج — محدودیت‌های این گزارش

1. بدون مرورگر/WebView واقعی، یافتهٔ CSP فقط «استاندارد + شاهد کد» است.
2. بدون Android SDK و دستگاه، رفتار FGS/Doze/OEM و MediaStore آزموده نشد.
3. تست‌های Qt و `panel.py --selftest` به‌دلیل نبود PySide6 اجرا نشدند؛ F-08 از خواندن کد و مقایسهٔ config است.
4. شبکهٔ زنده (Twelve Data/Telegram/RSS) در sandbox در دسترس نبود؛ تست‌های مربوطه mock/آفلاین‌اند.
5. این گزارش ادعای «نفوذ ناپذیری» یا «سودآوری» ندارد؛ فقط وضعیت مهندسی و ریسک‌های قابل مشاهده را ثبت می‌کند.

---

**پایان گزارش — ۲۳ نوامبر ۲۰۲۶**
