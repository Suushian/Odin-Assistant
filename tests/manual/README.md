# 🧪 تست‌های دستی و تست‌های رگرسیون با اجرای مستقل

بیشتر تست‌های این پوشه عمداً در GitHub Actions اجرا نمی‌شوند، چون بعضی از آن‌ها
به اینترنت زنده یا کتابخانهٔ GUI نیاز دارند و می‌توانند flaky باشند. بااین‌حال،
`test_paths_install.py`، `test_journal.py`، `test_judge.py`، `test_veto_report.py`،
`test_news_direction.py` و `test_license.py` آفلاین‌اند و در workflow تست‌ها اجرا می‌شوند.

تست‌های اصلی CI شامل موارد زیرند (فهرست کامل فرمان‌ها در
`.github/workflows/build-release.yml` است):

| فرمان | فایل |
|---|---|
| `python main.py --selftest` | خودآزمایی backend |
| `python tests/check_config.py` | اعتبارسنجی پیکربندی |
| `python tests/manual/test_paths_install.py` | مسیر دادهٔ نصب‌شده/پرتابل |
| `python -m compileall -q src panel.py main.py` | بررسی نحوی کد پایتون |

---

## تست‌های این پوشه

| فایل | نیازمندی | چه می‌سنجد |
|---|---|---|
| `test_alerts.py` | آفلاین | هشدارهای قیمت/تقویم/بریفینگ و ضدتکرار |
| `test_audit_fixes.py` | آفلاین | رگرسیون یافته‌های ممیزی امنیتی/داده |
| `test_journal.py` | آفلاین | پیگیری نتیجه از کندل، آمار، گزارش و سطل‌های امتیاز |
| `test_judge.py` | آفلاین (pandas) | **جامع‌ترین تست داور**: مسیر طلایی، هر ۷ وتو، تنظیم‌پذیری، ریاضی SL/TP، سقف/`CAPPED`، ضداسپم، فیلدهای ژورنال |
| `test_license.py` | آفلاین | Ed25519، انقضا، قفل دستگاه، تریال و ضدساعت |
| `test_news_direction.py` | اینترنت (RSS زنده) | ۱۴ حالت جهت‌دهی + توزیع امتیازها روی دادهٔ واقعی |
| `test_paths_install.py` | آفلاین | مسیر دادهٔ نصب‌شده/پرتابل |
| `test_veto_report.py` | آفلاین | رندر وتو در گزارش، یکدستی `now`، `main.py --alerts --dry-run` |
| `test_activation_dialog.py` | PySide6 | دیالوگ فعال‌سازی و پیام‌های خطا |
| `test_gui_integration.py` | PySide6 + اینترنت | سیم‌کشی پنل↔موتور و زمان‌بند بریفینگ |
| `test_layout_fit.py` | PySide6 | جا شدن ویجت‌ها در پنجره‌های کوچک |
| `test_pages_render.py` | PySide6 | رندر ۵ تب بدون خطا |
| `test_settings_ui.py` | PySide6 | ذخیره/بازنشانی تنظیمات و clamp |
| `test_sharecard.py` | PySide6 | کارت اشتراک تصویری |
| `render_dash.py` / `render_shots.py` | PySide6 | ابزارهای تولید اسکرین‌شات (نه تست CI) |

---

## اجرا

```bash
pip install -r requirements.txt          # برای تست GUI به PySide6 نیاز داری

python tests/manual/test_judge.py            # آفلاین و قطعی — مهم‌ترین تست مرحله ۳
python tests/manual/test_news_direction.py
python tests/manual/test_veto_report.py

# تست GUI بدون مانیتور (لینوکس/CI):
QT_QPA_PLATFORM=offscreen python tests/manual/test_gui_integration.py
```

در ویندوز:
```bat
set QT_QPA_PLATFORM=offscreen
python tests\manual\test_gui_integration.py
```

همهٔ تست‌های آفلاین با کد خروجی `0` و پیام «✅ همهٔ تست‌ها پاس شدند» تمام می‌شوند.

---

## نکته دربارهٔ تست GUI

`test_gui_integration.py` در بخشی از تست، تابع `engine.run_briefing` را با یک
mock جایگزین می‌کند تا زمان‌بند را **بدون انتظار برای ساعت واقعی** بسنجد.
بعد از تست، تابع اصلی بازگردانده می‌شود و خود تست هم این بازگشت را
assert می‌کند — وگرنه بخش‌های بعدی (که چرخهٔ واقعی می‌زنند) با mock اجرا
می‌شدند و نتیجهٔ کاذب می‌دادند. (این باگ یک بار در همین تست رخ داد و رفع شد.)

> 💡 **چرا تست‌های داور با دادهٔ مصنوعی‌اند؟** چون داور به «الان کی است» وابسته است
> (سشن، روز هفته، فاصله تا رویداد تقویم). اگر تست به زمان واقعی وابسته بود،
> آخر هفته‌ها همه‌چیز وتوی «بازار بسته» می‌خورد و مسیر اصلی سیگنال هرگز
> اجرا نمی‌شد. پس `now` تزریق می‌شود تا تست قطعی و آفلاین بماند.
