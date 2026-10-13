# تست‌های دستی و تست‌های رگرسیون

این پوشه تست‌هایی با نیازمندی‌های متفاوت دارد. نام پوشه به معنی خارج‌بودن همهٔ تست‌ها از CI نیست: فایل tests/manual/test_paths_install.py در workflow تست‌ها اجرا می‌شود. فایل .github/workflows/build-release.yml مرجع نهایی وضعیت CI است.

## تست‌های مهم

| فایل | نیازمندی | هدف |
|---|---|---|
| test_news_direction.py | اینترنت و RSS زنده | جهت‌دهی خبر و توزیع امتیازها روی دادهٔ واقعی |
| test_veto_report.py | عمدتاً آفلاین | رندر دلیل وتو، یکدستی زمان گزارش، ترجمه و dry-run هشدار |
| test_judge.py | آفلاین؛ pandas | داور، وتوها، امتیاز، SL/TP، سقف سیگنال و فیلدهای ژورنال |
| test_gui_integration.py | PySide6؛ بعضی مسیرها وابسته به اینترنت | اتصال پنل، وضعیت تب‌ها و زمان‌بند بریفینگ |
| test_paths_install.py | آفلاین | مسیرهای دادهٔ نصب‌شده و پرتابل؛ در CI هم اجرا می‌شود |

برای فهرست دقیق فرمان‌های CI، workflow فعلی را ببینید؛ این جدول جایگزین آن نیست. تست‌های وابسته به GUI یا اینترنت ممکن است در محیط محدود اجرا نشوند یا نتیجهٔ وابسته به محیط بدهند.

## تست‌های اجراشده در CI

- python main.py --selftest
- python tests/check_config.py
- python tests/manual/test_paths_install.py
- python -m compileall -q src panel.py main.py
- تست‌های واحد و parity که صریحاً در build-release.yml آمده‌اند
- اسموک‌های JavaScript که صریحاً در workflow آمده‌اند

## اجرا

از ریشهٔ مخزن:

    python tests/manual/test_judge.py
    python tests/manual/test_veto_report.py
    python tests/manual/test_paths_install.py
    python tests/manual/test_news_direction.py

تست GUI در صورت نصب PySide6 و فراهم‌بودن محیط مناسب:

    QT_QPA_PLATFORM=offscreen python tests/manual/test_gui_integration.py

در ویندوز:

    set QT_QPA_PLATFORM=offscreen
    python tests\manual\test_gui_integration.py

موفقیت یک تست به معنی موفقیت همهٔ تست‌ها یا معتبر بودن بک‌تست مالی نیست. خروجی و کد خروجی هر فرمان را جداگانه بررسی کنید.

## نکته دربارهٔ تست GUI

test_gui_integration.py در بخشی از تست، engine.run_briefing را با mock جایگزین می‌کند تا زمان‌بند بدون انتظار برای ساعت واقعی سنجیده شود. تابع اصلی باید پس از بخش mock بازگردانده شود؛ در غیر این صورت چرخه‌های بعدی ممکن است ناخواسته با mock اجرا شوند.

> سشن بازار، روز هفته و فاصله تا رویداد تقویم به زمان وابسته‌اند. تزریق now تست داور را قطعی و آفلاین نگه می‌دارد و از شکست تصادفی مسیر سیگنال در تعطیلات جلوگیری می‌کند.
