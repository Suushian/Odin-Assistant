# -*- coding: utf-8 -*-
"""تست کامل سیستم لایسنس (v1.0.2) — امضای Ed25519 + قفل دستگاه + چرخهٔ فعال‌سازی.

آفلاین و قطعی؛ روی هر سه پلتفرم. ذخیره‌سازی با ODIN_DATA_DIR موقت ایزوله می‌شود
تا به دادهٔ واقعی کاربر دست نزند.

نکتهٔ تست: چون کلید عمومیِ اپ اجازهٔ امضای با سیدِ تست را نمی‌دهد، این تست
«کلید عمومیِ ماژول» را موقتاً به کلید عمومیِ سیدِ تست می‌زند تا چرخهٔ کامل
پوشش داده شود؛ در پایان سراغ کلید عمومیِ واقعی هم می‌رود.

اجرا: python tests/manual/test_license.py
"""
import json
import os
import pathlib
import sys
import tempfile

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

FAILS = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


TEST_SEED = "8D9FADA9722DA1DDF8EBA1CA0E3E7AA8A7AB9F3DC120C65BB9ED211B8842BC9E"
OTHER_SEED = "1111111111111111111111111111111111111111111111111111111111111111"

# کلیدهای امضاشده با کلید خصوصیِ واقعی (کلید عمومیِ اپ) — بُرِد مشترک با JS
PROD_PERM = ("ODGLQ6OP5YOE22KNKAF7S6GLFBNFG7LVLROLG7ZR4NTM3CP7FEWYXZN2SXUWVZJIOE"
             "3DL472XM4MLA2WDROVNWEJ47YMHOH5CAFIOBQ")
PROD_TIMED = ("IU5IBZ2PQNDY6YJBNKAQ4JE6FGHTTABGWXZWVEDUIS6FS3X7MEZ2J6BGTIHO25WAU4M"
              "JKNZB46NCRMA4SCGB7AIKQ52TCNZYGRWUADY-301231")

with tempfile.TemporaryDirectory() as td:
    os.environ["ODIN_DATA_DIR"] = td          # ایزوله‌سازی license.dat
    os.environ.pop("ODIN_SKIP_LICENSE", None)

    from src import license as lic
    from src import license_ed25519 as ed

    print("=" * 70)
    print("۱) شناسه و کد دستگاه")
    print("=" * 70)
    did = lic.get_device_id()
    check(len(did) == 64 and all(c in "0123456789abcdef" for c in did),
          "device_id = ۶۴ هگز کوچک")
    check(did == lic.get_device_id(), "device_id قطعی است (دو فراخوانی یکی)")
    code = lic.get_device_code(did)
    check(code == f"{did[:12].upper()[:4]}-{did[:12].upper()[4:8]}-{did[:12].upper()[8:12]}",
          f"device_code از ۱۲ رقم اول ساخته می‌شود: {code}")
    check(lic.normalize_code(" ab12-cd34 ef56 ") == "AB12CD34EF56", "normalize_code مقاوم است")

    print("=" * 70)
    print("۲) تولید و اعتبارسنجی کلید (Ed25519)")
    print("=" * 70)
    # مسیر اعتبارسنجی با کلید عمومیِ واقعی اپ
    check(len(PROD_PERM) == 103 and PROD_PERM.isalnum(), "کلید دائمی ۱۰۳ نویسهٔ Base32 است")
    check(len(PROD_TIMED) == 110 and PROD_TIMED.endswith("-301231"), "کلید زمان‌دار ۱۰۳+۶ است")
    check(lic.validate_license(PROD_PERM, "AB12-CD34-EF56")[0], "کلید دائمیِ امضاشده با کلید واقعی معتبر است")
    check(lic.validate_license(PROD_PERM.lower(), "AB12CD34EF56")[0], "کوچک‌بزرگی مقاوم است")
    check(not lic.validate_license(PROD_PERM, "FF00-FF00-FF00")[0], "کلید دستگاه دیگر رد می‌شود")
    check(not lic.validate_license("AAAA-BBBB-CCCC-DDDD", "AB12CD34EF56")[0], "کلید تصادفی رد می‌شود")
    check(not lic.validate_license("short", "AB12CD34EF56")[0], "رشتهٔ کوتاه رد می‌شود")

    # بُرِد مشترک پایتون/JS با سیدِ تست
    check(lic.generate_license_key("AB12CD34EF56", seed=TEST_SEED) ==
          "SAYIKVXA2JU7SPMLWBA5OIEXNGDBR6OYM6AVJ2ZGUQYQYL22ZCL3YX35EXT2XOALBXXZVAAY7WZGCWH4FRUAU4CICLOVJUSHKCH6GCI",
          "بُرِد آزمایشی مشترک دائمی با JS")
    check(lic.generate_license_key("D9AC55605559", seed=TEST_SEED) ==
          "7TAHMUJW7ODWGPFYNQ3INXTI7XE2BXNAV5PRYTQ373D2BSVFHXKY723OYNYXLWDFTIQEMKJ3TRKBZPKSBGVRTCWJEREPC3I6APLKSCQ",
          "بُرِد آزمایشی مشترک دوم با JS")
    check(lic.generate_license_key("AB12-CD34-EF56", until="2030-12-31", seed=TEST_SEED) ==
          "CYU2HFS6GV2WLA2VFPGLLSYCX2BKIOUD3BSBBEXXEBZBOJZDQ6HIIFFLX2CUDY2A4ZIVWVNWV3SUKOWTGB7VMNEBAQBK7TG37IZKKAQ-301231",
          "بُرِد آزمایشی مشترک زمان‌دار با JS")
    check(lic.generate_license_key("AB12-CD34-EF56", seed=TEST_SEED) ==
          lic.generate_license_key("AB12-CD34-EF56", seed=TEST_SEED), "کلید قطعی است")

    # کلید عمومیِ ماژول را موقتاً به سیدِ تست می‌زنیم تا چرخهٔ کامل پوشش شود
    _real_pub = lic.PUBLIC_KEY
    lic.PUBLIC_KEY = ed.public_key(bytes.fromhex(TEST_SEED))
    try:
        key = lic.generate_license_key(code, seed=TEST_SEED)
        check(len(key) == 103, f"کلید دائمی ۱۰۳ نویسه است: {len(key)}")
        ok, _ = lic.validate_license(key)
        check(ok, "کلیدِ دستگاهِ فعلی معتبر است")
        ok, _ = lic.validate_license(key.lower())
        check(ok, "اعتبارسنجی به کوچک‌بزرگی مقاوم است")
        ok, msg = lic.validate_license(key, "FF00-FF00-FF00")
        check(not ok, "کلیدِ دستگاهِ دیگر روی این دستگاه رد می‌شود")
        # کلید ساخته‌شده با کلید خصوصیِ دیگر باید مردود شود
        ok, _ = lic.validate_license(lic.generate_license_key(code, seed=OTHER_SEED))
        check(not ok, "کلید ساخته‌شده با کلید خصوصیِ دیگر رد می‌شود (فقط کلید عمومیِ اپ امضا را می‌پذیرد)")

        print("=" * 70)
        print("۳) چرخهٔ فعال‌سازی (save/load/enforce/deactivate)")
        print("=" * 70)
        check(not lic.is_activated(), "ماشین تازه: فعال نیست")
        ok, msg = lic.check_and_enforce_license()
        check(not ok, "دروازهٔ اجرا بدون لایسنس بسته است")

        ok, msg = lic.activate_program("AAAA-BBBB-CCCC-DDDD", "کاربر تست")
        check(not ok, "فعال‌سازی با کلید غلط رد می‌شود")
        ok, msg = lic.activate_program(key, "کاربر تست")
        check(ok, "فعال‌سازی با کلید درست موفق است")
        check(lic.is_activated(), "پس از فعال‌سازی، is_activated=True")
        ok, msg = lic.check_and_enforce_license()
        check(ok, "دروازهٔ اجرا باز شد")

        lf = lic.get_license_file_path()
        check(lf.exists(), "license.dat ساخته شد")
        data = json.loads(lf.read_text(encoding="utf-8"))
        check(data["device_id"] == did and data["version"] == "3.0",
              "device_id کامل قفل شد (نسخهٔ رکورد 3.0)")

        saved = dict(data)
        saved["device_id"] = "0" * 64
        lf.write_text(json.dumps(saved), encoding="utf-8")
        check(not lic.is_activated(), "license.dat با device_id بیگانه رد می‌شود (ضدکپی)")
        lf.write_text(json.dumps(data), encoding="utf-8")

        os.environ["ODIN_SKIP_LICENSE"] = "1"
        check(lic.license_bypassed(), "ODIN_SKIP_LICENSE=1 → bypass")
        os.environ.pop("ODIN_SKIP_LICENSE")

        check(lic.deactivate_program(), "غیرفعال‌سازی موفق")
        check(not lf.exists() and not lic.is_activated(), "پس از غیرفعال‌سازی: فایل حذف و قفل بسته")

        print("=" * 70)
        print("۴) CLI سازنده")
        print("=" * 70)
        check(lic._cli(["gen", "AB12-CD34-EF56", "--seed", TEST_SEED]) == 0, "gen با کد درست → خروج ۰")
        check(lic._cli(["gen", "AB12-CD34-EF56", "--seed", OTHER_SEED]) == 0, "gen با سید → خروج ۰")
        check(lic._cli(["check", lic.generate_license_key("AB12CD34EF56", seed=TEST_SEED),
                        "AB12CD34EF56"]) == 0, "check کلید درست → ۰")
        check(lic._cli(["check", "AAAA-BBBB-CCCC-DDDD", "AB12CD34EF56"]) == 1, "check کلید غلط → ۱")
        check(lic._cli(["gen", "xyz", "--seed", TEST_SEED]) == 2, "gen با کد نامعتبر → ۲")
        check(lic._cli(["gen", "AB12-CD34-EF56", "--until", "2030-12-31", "--seed", TEST_SEED]) == 0,
              "gen --until → ۰")
        check(lic._cli(["gen", "AB12-CD34-EF56", "--days", "30", "--seed", TEST_SEED]) == 0, "gen --days → ۰")
        check(lic._cli(["public"]) == 0, "public → ۰")
        check(lic._cli(["keypair"]) == 0, "keypair → ۰")

        print("=" * 70)
        print("۵) کلید زمان‌دار")
        print("=" * 70)
        from datetime import datetime, timedelta
        kt = lic.generate_license_key("AB12-CD34-EF56", until="2030-12-31", seed=TEST_SEED)
        check(kt == "CYU2HFS6GV2WLA2VFPGLLSYCX2BKIOUD3BSBBEXXEBZBOJZDQ6HIIFFLX2CUDY2A4ZIVWVNWV3SUKOWTGB7VMNEBAQBK7TG37IZKKAQ-301231",
              f"بُرِد مشترک زمان‌دار با JS: {kt}")
        body, exp8 = lic.parse_key_input(kt)
        check(exp8 == "20301231" and len(body) == 103, "پارس پسوند تاریخ")
        check(lic.validate_license(kt, "AB12-CD34-EF56")[0], "کلید زمان‌دار معتبر است")
        check(not lic.validate_license(kt, "AB12-CD34-EF56", now=datetime(2031, 1, 1))[0],
              "پس از انقضا رد می‌شود")
        check(not lic.validate_license(kt[:103], "AB12-CD34-EF56")[0],
              "حذف پسوند تاریخ → رد (امضا روی تاریخ هم هست)")
        try:
            lic.parse_key_input(kt[:103] + "-310231")
            check(False, "۳۱ فوریه باید رد شود")
        except ValueError:
            check(True, "تاریخ نامعتبر (۳۱ فوریه) رد می‌شود")
        kd = lic.generate_license_key(code, 90, seed=TEST_SEED)
        _, e90 = lic.parse_key_input(kd)
        delta = (datetime.strptime(e90, "%Y%m%d").date() - datetime.now().date()).days
        check(delta in (89, 90), f"--days 90 → انقضا ~۹۰ روز (={delta})")

        print("=" * 70)
        print("۶) دورهٔ آزمایشی ۷ روزه + ضدِ ساعت")
        print("=" * 70)
        t0 = lic.trial_status()
        check(not t0["exists"] and not t0["active"], "تریال شروع نشده")
        ok, _m = lic.check_and_enforce_license()
        check(not ok, "بدون لایسنس/تریال → دروازه بسته")
        check(lic.start_trial()[0], "start_trial موفق")
        check(not lic.start_trial()[0], "start_trial دوباره → رد (ضدتقلب)")
        t1 = lic.trial_status()
        check(t1["active"] and t1["days_left"] == 7, "روز ۰ → فعال، ۷ روز باقی")
        ok, msg = lic.check_and_enforce_license()
        check(ok and "آزمایشی" in msg, "دروازه با تریال باز است")
        t2 = lic.trial_status(now=datetime.now() + timedelta(days=6, hours=12))
        check(t2["active"] and t2["days_left"] == 1, "روز ۶.۵ → ۱ روز باقی")
        t3 = lic.trial_status(now=datetime.now() + timedelta(days=7, hours=3))
        check(not t3["active"] and t3["days_left"] == 0, "روز ۷.۱ → تمام")
        t4 = lic.trial_status(now=datetime.now() - timedelta(hours=96))
        check(t4["tampered"] and not t4["active"], "عقب‌کشیدن ساعت → tampered")
        kdev = lic.generate_license_key(code, until="2030-12-31", seed=TEST_SEED)
        ok, msg = lic.activate_program(kdev, "تستر")
        check(ok, "فعال‌سازی با کلید زمان‌دار")
        check(lic.is_activated(), "is_activated با کلید زمان‌دار")
        check(not lic.is_activated(now=datetime(2031, 1, 2)), "is_activated پس از انقضا → False")
        data = json.loads(lic.get_license_file_path().read_text(encoding="utf-8"))
        check(data.get("expires_at") == "20301231" and data.get("version") == "3.0",
              "expires_at/version در license.dat ذخیره شد")
    finally:
        lic.PUBLIC_KEY = _real_pub

    # بازگشت به کلید عمومیِ واقعی: کلیدِ سیدِ تست دیگر باید رد شود
    check(not lic.validate_license(lic.generate_license_key("AB12CD34EF56", seed=TEST_SEED),
                                   "AB12CD34EF56")[0],
          "پس از بازگشت کلید عمومیِ واقعی، کلیدِ سیدِ تست رد می‌شود")
    check(lic._cli(["check", PROD_PERM, "AB12CD34EF56"]) == 0,
          "check کلید دائمیِ امضاشده با کلید خصوصیِ واقعی → ۰")

print("=" * 70)
if FAILS:
    print(f"❌ {len(FAILS)} تست شکست خورد:")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("✅ همهٔ تست‌های لایسنس پاس شد")
sys.exit(0)
