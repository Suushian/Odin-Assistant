# فهرست مستندات ODIN Assistant

> **وضعیت این فهرست: ۲۰۲۶-۱۰-۱۳ · نسخهٔ منبع کد: 0.28.0**
>
> توسعه و انتشار فعال برای اندروید است. رابط ویندوز از v0.21.0 منجمد شده؛ بااین‌حال
> کد Python همچنان اوراکل تست موتور JavaScript و منبع حقیقت نسخه و توکن‌های تم است.
> اسناد تاریخی را به‌عنوان snapshot بخوانید، نه وضعیت لحظه‌ای پروژه.

## شروع سریع برای توسعه‌دهنده یا دستیار هوش مصنوعی

1. [ODIN-AI-Context-Pack-fa.md](ODIN-AI-Context-Pack-fa.md) — نقشهٔ مخزن، قواعد توسعه، جریان تست/ریلیز و بدهی‌های شناخته‌شده.
2. [plugin-architecture-fa.md](plugin-architecture-fa.md) — معماری Contract-Based + Plugin-Driven و راهنمای تغییر امن.
3. [../CHANGELOG.md](../CHANGELOG.md) — تاریخچهٔ نسخه‌ها و منبع یادداشت Release.
4. [android-fa.md](android-fa.md) — ساخت و معماری اپ اندروید.
5. [security-review-fa.md](security-review-fa.md) — وضعیت بازبینی امنیتی و ریسک‌های باز.
6. [project-report-fa.md](project-report-fa.md) — snapshot وضعیت پروژه و محدودیت‌های ارزیابی.

## اسناد اصلی

| سند | موضوع |
|---|---|
| [../README.md](../README.md) | معرفی محصول، قابلیت‌ها، نصب و معماری |
| [../CHANGELOG.md](../CHANGELOG.md) | تاریخچهٔ تغییرات و منبع یادداشت Release |
| [ODIN-AI-Context-Pack-fa.md](ODIN-AI-Context-Pack-fa.md) | زمینهٔ توسعه، نقشهٔ فایل‌ها، تست‌ها و قواعد طلایی |
| [plugin-architecture-fa.md](plugin-architecture-fa.md) | معماری پلاگین‌ها، قراردادها و pipeline |
| [android-fa.md](android-fa.md) | راهنمای اپ اندروید، WebView، ساخت APK و تست‌های parity |
| [project-report-fa.md](project-report-fa.md) | گزارش وضعیت تاریخ‌دار |
| [security-review-fa.md](security-review-fa.md) | یافته‌های امنیتی، اصلاحات و کارهای باز |
| [../LICENSE_GUIDE.md](../LICENSE_GUIDE.md) | تولید و اعتبارسنجی لایسنس آفلاین و محدودیت‌های آن |

## طراحی و منطق

| سند | موضوع |
|---|---|
| [signal-assistant-design.md](signal-assistant-design.md) | طراحی کلی، لایه‌ها و جریان داده |
| [step2-fundamental-news-fa.md](step2-fundamental-news-fa.md) | تقویم اقتصادی و تحلیل جهت‌دار خبر |
| [step3-judge-signals-fa.md](step3-judge-signals-fa.md) | داور، وتوها، امتیازدهی و محاسبهٔ SL/TP |
| [step4-journal-stats-fa.md](step4-journal-stats-fa.md) | ژورنال append-only و پیگیری نتیجهٔ سیگنال |
| [test-step1-fa.md](test-step1-fa.md) | راهنمای تست مرحلهٔ اولیهٔ داده و تحلیل تکنیکال |

## اسناد رابط ویندوز — تاریخی و منجمد

از v0.22.0 توسعهٔ محصول روی اندروید متمرکز است. آخرین نسخهٔ ویندوزِ مستندشده
v0.21.0 است. کد و راهنماهای ویندوز برای نگهداری و آزمون parity باقی مانده‌اند،
اما نباید آن‌ها را رابط فعال محصول تلقی کرد.

| سند | موضوع |
|---|---|
| [panel-guide-fa.md](panel-guide-fa.md) | راهنمای پنل ویندوزی و نصب؛ تاریخی |
| [ui-design-fa.md](ui-design-fa.md) | طراحی رابط ویندوز و توکن‌های تم؛ تاریخی |

> src/ui/theme.py همچنان منبع حقیقت توکن‌های تم است و آزمون
> tests/js/smoke_theme_parity.js آن را با CSS اندروید مقایسه می‌کند.

## تست‌ها و فرمان‌های مفید

فرمان‌ها از ریشهٔ مخزن اجرا می‌شوند. فهرست دقیق و فعلی را در
[build-release.yml](../.github/workflows/build-release.yml) و
[build-android.yml](../.github/workflows/build-android.yml) ببینید؛ این جدول
جایگزین workflow نیست.

| فرمان | هدف |
|---|---|
| python main.py --selftest | خودآزمایی backend |
| python tests/check_config.py | اعتبارسنجی پیکربندی |
| python -m compileall -q src panel.py main.py | بررسی نحوی Python |
| python tests/manual/test_paths_install.py | آزمون مسیرهای دادهٔ نصب/پرتابل؛ در CI اجرا می‌شود |
| node tests/js/run_parity.js | مقایسهٔ موتور JS با اوراکل Python |
| node tests/js/smoke_theme_parity.js | parity توکن‌های تم و CSS |
| node tests/js/smoke_journal.js | آزمون smoke ژورنال اندروید |
| node tests/js/smoke_plugins.js | وضعیت و سیم‌کشی پلاگین‌ها |
| node tests/js/smoke_service.js | مسیر چرخهٔ سرویس پس‌زمینه |

تست‌های tests/manual یکدست نیستند: بعضی آفلاین‌اند، بعضی به GUI یا اینترنت زنده
نیاز دارند. تنها تست‌هایی را که workflow فعلی صریحاً اجرا می‌کند جزو CI بدانید.

## قراردادهای نگهداری

1. APP_VERSION در src/app_paths.py منبع حقیقت نسخه است.
2. CHANGELOG.md منبع یادداشت Release است؛ هر نسخه باید بخش خودش را داشته باشد.
3. تغییر توکن تم باید با آزمون parity و CSS اندروید هماهنگ باشد.
4. تغییر موتور JS باید با اوراکل Python و تست‌های parity سنجیده شود.
5. ادعای عملکرد یا نرخ برد بدون replay تاریخی معتبر، کنترل lookahead و هزینهٔ معامله مطرح نشود.
6. گزارش‌های آماری باید تاریخ و روش اندازه‌گیری داشته باشند.
