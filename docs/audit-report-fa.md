# گزارش ممیزی فنی — ODIN Assistant

**تاریخ:** ۲۰۲۶-۱۱-۲۱
**شاخه:** `arena/24e21865-odin-assistant` (از `main` @ `4cd37cb`)
**نسخهٔ کد:** `1.0.1` (`src/app_paths.py` ← منبع حقیقت)
**پلتفرم فعال:** اپ اندروید WebView (`android/app/src/main/assets/www/`) با موتور JS (ES5).
پایتون «اوراکل» تست و مرجع است؛ نسخهٔ ویندوز از v0.21 منجمد است.

---

## ۱. خلاصهٔ اجرا

| خانواده | تعداد | نتیجه |
|---|---|---|
| `tests/test_*.py` (پایتون، ۱۲ فایل) | ۱۲ | ✅ همه سبز |
| `tests/js/*.js` | ۲۷ | ✅ همه سبز (۲ تای شکسته رفع شد) |
| `tests/manual/*` | ۱۶ | ✅ ۸ سبز · ⚠️ ۸ تای Qt به‌خاطر `libGL.so.1` در sandbox غیراجرایی |
| `tests/golden/*` (بازتولید و مقایسه) | — | ✅ طلایی بازتولید و سبز |
| `main.py --selftest` · `tests/check_config.py` | ۲ | ✅ |
| lint (`F401,F841,F811,F541,B008,PLR0124`) | — | ✅ All checks passed |
| `node --check` / `compileall` | — | ✅ |

> ۸ سوئیت Qt در sandbox اجرا نشدند چون `libGL.so.1` نصب نیست و `apt` بدون شبکه
> است؛ علت مربوط به کد نیست و در CI هم این سوئیت‌ها جزو گردش نیستند.

---

## ۲. یافته‌ها و رفع آن‌ها

### ۲.۱ باگ رفتاری واقعی در نسخهٔ ویندوز (منجمد، ولی در درخت)
| مورد | علت | رفع |
|---|---|---|
| بستن پنجره به‌جای پنهان‌شدن در tray | `panel.py` تابع `closeEvent` را **دوبار** تعریف کرده بود؛ نسخهٔ دوم (خط ۱۸۰۸) نسخهٔ اول (خط ۱۱۸۵) را می‌زد | تعریف تکراری حذف شد |

### ۲.۲ آستانهٔ داور ناهم‌تراز (باگ سند/کد + کد/کد)
- `config.yaml` و هر دو موتور آستانهٔ **۵** داشتند، ولی `src/report/signal.py`
  (دو محل) و `src/engine.py` هنوز **۷** را به‌کار می‌بردند؛ اسناد هم ۷ (و جایی
  «۷ از ۱۰») می‌گفتند.
- **رفع:** `src/report/signal.py`، `src/engine.py`، `js/judge.js` (کد و کامنت) → ۵؛
  `docs/step3-judge-signals-fa.md`، `docs/step2-fundamental-news-fa.md`،
  `docs/signal-assistant-design.md`، `README.md` و `docs/ODIN-AI-Context-Pack-fa.md`
  به آستانهٔ ۵ از ۱۱ اصلاح شدند.

### ۲.۳ نسخهٔ کهنه
- `Bridge.java`: `User-Agent` و مقدار پشتیبان `versionName` هنوز `0.28.0`.
- `installer/version_info.txt` و کامنت‌های `installer/odin.iss` و `build_exe.bat`.
- **رفع:** همه به `1.0.1`؛ `installer/stamp_version.py` اجرا شد (`(1,0,1,0)`).
  `build.gradle` خودش از `APP_VERSION` مشتق می‌کند و درست بود.

### ۲.۴ امنیت خرد
- نام فایل در `saveDownload`/`saveImage` از JS می‌آمد و مستقیم در `DISPLAY_NAME`
  رفت؛ احتمال path traversal با `../` یا نویسهٔ کنترلی.
  **رفع:** `sanitizeFileName(name, fallback)` در `Bridge.java` (فقط نام پایه،
  حذفِ `\/:*?"<>|` و کاراکترهای کنترل، سقف ۸۰ نویسه، fallback امن) در هر دو مسیر.
- تزریق اسکریپت از منبع بیرونی در WebView: **رفع:** `Content-Security-Policy`
  در `index.html` (`default-src 'none'`؛ script/style/img/font/connect فقط `'self'`).
- بررسی و **سالم** تأیید شد: `ShareFileProvider` (`exported=false` + بررسی
  canonical path) و whitelist  schemes در `shouldOverrideUrlLoading`.

### ۲.۵ سند/کد ناهم‌ترازی استراتژی (یافتهٔ اصلی)
اسناد (`Context Pack`، `plugin-architecture-fa`، `android-fa`،
`project-report-fa`، `release-device-checklist-fa` و `CHANGELOG` ۰٫۲۶/۰٫۲۷)
«استراتژی‌های ورود» (S1–S4) را ویژگیِ **فعال** توصیف می‌کردند، ولی در کد وجود
ندارد: `src/strategies/`، `js/strategies.js`، `strategies:` در `config.yaml`،
پلاگین‌های `strategy-*` و دروازهٔ توافق در داور — همه غایب‌اند.

**رفع (بدون حذفِ تاریخچه):**
- بخش S1–S4 در `plugin-architecture-fa.md` و دو بخش v0.26/v0.27 در `android-fa.md`
  با سرعنوان «تاریخی؛ در کد فعلی وجود ندارد» علامت خوردند.
- بخش‌های ادعایی از `Context Pack` (§۲ نقشهٔ ریپو و §۱۰ وضعیت) و ارجاعات از
  `project-report-fa.md`، `project-readiness-review-fa.md` (سند ۰٫۲۸ به‌عنوان
  تاریخی) و `release-device-checklist-fa.md` حذف/اصلاح شدند.
- `CHANGELOG.md` بخش `[1.0.1]` گرفت که این بازگردانی را مستند می‌کند.

### ۲.۶ lint عملی
- ۱۰۶۸ یافتهٔ ruff در برخورد اول بیشترشان نوادگی سبک بود (پروژه کانفیگ ruff
  ندارد). روی مجموعهٔ عملی `F401,F841,F811,F541,B008,PLR0124` تمرکز شد:
  پاک‌سازی importهای بلااستفاده، حذفِ `noqa: B008` نامعتبر، اصلاحِ `PLR0124`
  و رفعِ `F811` (بخش ۲.۱) در `panel.py`، `src/ui/*`، `src/core/*`،
  `src/report/sharecard.py`، چند فایل تست و `tools/make_project_report.py`.
- **نتیجه:** `All checks passed!`

### ۲.۷ تست‌های شکسته
- `tests/js/smoke_service.js`: `ENOENT js/strategies.js` → سناریو داده‌محور
  (`features_disabled`) با همان مجموعهٔ مراحلِ داور/ریسک بازنویسی شد.
- `tests/js/test_pipeline_events.js`: سناریو از `gen_cycle_golden.js` می‌خواست
  مرحلهٔ تعریف‌نشدهٔ `svc_gated_no_strategy` → به `features_disabled` منتقل شد.
- `tests/test_engine_switch.py`: طلاییِ بازتولیدشده کلید `signals` را در
  `result` داشت ولی تست فقط سمتِ «got» را می‌تراشید → حالا **هر دو سمت** قبل
  از `==` تراشیده می‌شوند و سیگنال‌ها جداگانه زیر آزمایه می‌شوند (۵۱ بررسی سبز).

### ۲.۸ پوشش CI ناقص
- `tests/js/smoke_service.js` و `tests/js/test_pipeline_events.js` در CI ارجاع
  نشده بودند → به `build-release.yml` اضافه شدند.
- سوئیت‌های آفلاینِ `tests/manual/`: `test_judge.py`، `test_veto_report.py`،
  `test_news_direction.py`، `test_audit_fixes.py` هم افزوده شدند.
- فایل‌های طلاییِ بی‌ارجاع (`judge_rules_golden.json`، `cycle_core_golden.json`،
  `judge_rules_js_golden.json`) که untracked مانده بودند، در ریپو track شدند.

---

## ۳. محدودیت‌ها و بدهی‌های باقی‌مانده (عمدی)

1. **لایسنس و ابزار تولید کلید دست‌نخورده** (طبق دستور کاربر):
   `src/license.py`، `js/license.js`، `LICENSE PANEL.html`، `LICENSE_GUIDE.md`.
   ⚠️ یادداشت امنیتی باز: ریپو عمومی است و راز HMAC لایسنس در همین فایل‌ها و در
   `LICENSE PANEL.html` کامیت شده است؛ خودِ `LICENSE_GUIDE.md` می‌گوید طرح در
   برابر جعل مقاوم نیست. این یافته رفع نشده و نیازمند تصمیم صاحب پروژه است.
2. **آستانهٔ ۵ عددِ بهینه‌شده نیست** — فقط نقطهٔ شروعِ محتاطانه؛ اعتبارسنجیِ آماری
   با ژورنالِ چندهفته‌ای لازم است (در سند step3 هم صادقانه نوشته شده).
3. **۸ سوئیت Qt** در sandbox اجرا نمی‌شوند (`libGL.so.1`)؛ در CI هم نیستند.
4. **بک‌تست مالی انجام نشده** — هیچ‌یک از این تغییرها سودآوری را اثبات
   نمی‌کنند؛ `tests/js/run_parity.js` زنده (نیازمند کلید/شبکهٔ Twelve Data و
   فیکسچرِ `fixtures.json` که gitignored است) در sandbox اجرا نشد.

---

## ۴. وضعیت نهایی

همهٔ تست‌های قابل‌اجرای sandbox سبزند؛ ۲۷/۲۷ تست JS، ۱۲/۱۲ تست پایتون،
۷ سوئیت manual آفلاین سبز و lint پاک. تنها قرمزها ۸ سوئیت Qt مبتنی بر نبودِ
`libGL.so.1` در sandbox‌اند (مربوط به محیط، نه کد) و `run_parity.js` که زنده و
نیازمند شبکه/کلید است.
