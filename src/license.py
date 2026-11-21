#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سیستم لایسنس و قفل دستگاه برای ODIN Assistant.

v1.0.2 — **امضای نامتقارن Ed25519** (RFC 8032) به‌جای HMAC رازمشترک.

چرا این تغییر: با HMAC، رازِ ساختِ کلید باید داخلِ اپ باشد تا اپ بتواند کلید را
اعتبارسنجی کند؛ یعنی هر کس می‌تواند راز را از اپ/ریپو بردارد و keygen بسازد.
با امضای نامتقارن، اپ فقط **کلید عمومی** را دارد و فقط «تأیید» می‌کند. ساختن
کلید لایسنس به **کلید خصوصی** نیاز دارد که فقط در دست سازنده است و هرگز در
اپ یا ریپو نیست (در `.gitignore` هم `*.secret` می‌گیرد).

طرح:
  device_id   = SHA-256 از پایدارترین شناسهٔ سیستم (MachineGuid/machine-id/
                IOPlatformUUID/ANDROID_ID)
  device_code = ۱۲ رقم اولِ هگزِ device_id، بالا‌حروف، جداکنندهٔ ۴تایی
  message     = "ODIN1|" + device_code + "|" + YYYYMMDD   (دائمی: 00000000)
  signature   = Ed25519_sign(message, کلید_خصوصی)        → ۶۴ بایت
  کلید        = Base32(signature)                         → ۱۰۳ نویسه
  کلید زمان‌دار = Base32 + "-" + YYMMDD

اعتبارسنجی در اپ: Base32 → ۶۴ بایت → Ed25519_verify با کلید عمومی + انقضا +
قفل device_id. بدون کلید خصوصی، ساخت کلید معتبر ممکن نیست.

هشدار صداقت: این کار «ساختن keygen» را غیرممکن می‌کند، ولی مانعِ مهندسیِ معکوسِ
کلِ اپ (patch کردن دروازهٔ اعتبارسنجی) نیست — هیچ لایسنس آفلاینی را از آن
مصون نمی‌کند. برای صدور امن‌تر در آینده: فعال‌سازی آنلاین با سرور امضاکننده.

کلید خصوصی سازنده (هرگز در گیت نیست):
  installer/odin-license.secret   (الگوی *.secret در .gitignore)
  python -m src.license gen CODE [--days N | --until YYYY-MM-DD]

CLI (سمت سازنده):
    python -m src.license device                       # شناسه/کد این دستگاه
    python -m src.license public                       # کلید عمومی امضا
    python -m src.license keypair                      # جفت کلید تازه (خروجی)
    python -m src.license gen CODE [--days N | --until DATE] [--seed HEX|--seed-file PATH]
    python -m src.license check KEY CODE               # راستی‌آزمایی (با انقضا)
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from src import app_paths
from src import license_ed25519 as ed25519

# ══════════════════════════════════════════════════════════════
#  ثابت‌های طرح
# ══════════════════════════════════════════════════════════════
# کلید عمومی امضای لایسنس — همان مقدار در js/license.js و LICENSE PANEL.html.
# این کلید «عمومی» است: فقط تأیید می‌کند و اجازهٔ ساخت کلید نمی‌دهد.
PUBLIC_KEY_HEX = "7F2CCF1F739C9FC4BC479A966FA1527CAC462BED99C3D7693B5B124BA8111591"

# کلید خصوصی پیش‌فرض سازنده (اگر وجود داشته باشد). هرگز کامیت نمی‌شود.
DEFAULT_SEED_FILE = Path(__file__).resolve().parents[1] / "installer" / "odin-license.secret"

TRIAL_DAYS = 7                 # دورهٔ آزمایشی (روز)
_ROLLBACK_TOLERANCE_H = 48     # عقب‌رفتن ساعت تا این حد = خطای مجاز، بیشتر = تقلب

_MESSAGE_PREFIX = "ODIN1"
_PERMANENT_EXPIRY = "00000000"
_B32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
_SIG_B32_LEN = 103             # Base32 بدون padding از ۶۴ بایت
_KEY_RE = re.compile(rf"^([A-Z2-7]{{{_SIG_B32_LEN}}})(?:-([0-9]{{6}}))?$")
_HEX_RE = re.compile(r"^[0-9A-Fa-f]+$")

PUBLIC_KEY = bytes.fromhex(PUBLIC_KEY_HEX)


# ══════════════════════════════════════════════════════════════
#  Base32 (RFC 4648، بالا‌حروف، بدون padding)
# ══════════════════════════════════════════════════════════════
def b32_encode(data: bytes) -> str:
    out, val, bits = [], 0, 0
    for byte in data:
        val = (val << 8) | byte
        bits += 8
        while bits >= 5:
            bits -= 5
            out.append(_B32_ALPHABET[(val >> bits) & 31])
    if bits:
        out.append(_B32_ALPHABET[(val << (5 - bits)) & 31])
    return "".join(out)


def b32_decode(text: str) -> bytes:
    val, bits = 0, 0
    out = bytearray()
    for ch in text:
        val = (val << 5) | _B32_ALPHABET.index(ch)
        bits += 5
        if bits >= 8:
            bits -= 8
            out.append((val >> bits) & 0xFF)
    return bytes(out)


# ══════════════════════════════════════════════════════════════
#  شناسهٔ دستگاه
# ══════════════════════════════════════════════════════════════
def _first_existing(paths: list[str]) -> str | None:
    for p in paths:
        try:
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    v = f.read().strip()
                if v:
                    return v
        except Exception:
            continue
    return None


def _mac_fallback() -> str:
    """MAC از uuid.getnode — آخرین چاره (روی VPN/چند-NIC ممکن است عوض شود)."""
    return ":".join(f"{(uuid.getnode() >> i) & 0xFF:02x}" for i in range(40, -8, -8))


def _stable_hardware_id() -> str:
    """پایدارترین شناسهٔ هر پلتفرم — بدون وابستگی بیرونی."""
    system = platform.system()
    if system == "Linux":
        v = _first_existing(["/etc/machine-id", "/var/lib/dbus/machine-id"])
        if v:
            return f"linux-machine-id:{v}"
    elif system == "Windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\Microsoft\Cryptography") as k:
                guid, _ = winreg.QueryValueEx(k, "MachineGuid")
            if guid:
                return f"win-machineguid:{guid}"
        except Exception:
            pass
        try:  # زاپاس: UUID بایوس از PowerShell
            import subprocess
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"],
                capture_output=True, text=True, timeout=15)
            uid = (r.stdout or "").strip().splitlines()[-1].strip() if r.stdout else ""
            if uid and uid.lower() not in ("", "ffffffff-ffff-ffff-ffff-ffffffffffff"):
                return f"win-csuuid:{uid}"
        except Exception:
            pass
    elif system == "Darwin":
        try:
            import subprocess
            r = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                               capture_output=True, text=True, timeout=15)
            for line in (r.stdout or "").split("\n"):
                if "IOPlatformUUID" in line:
                    uid = line.split("=")[-1].strip().strip('"')
                    if uid:
                        return f"mac-uuid:{uid}"
        except Exception:
            pass
    return f"mac:{_mac_fallback()}"


def get_device_id() -> str:
    """SHA-256 هگز (۶۴ کاراکتر) از شناسهٔ پایدار دستگاه."""
    return hashlib.sha256(_stable_hardware_id().encode("utf-8")).hexdigest()


def format_code(raw: str) -> str:
    """«AB12CD34EF56» → «AB12-CD34-EF56» (جداسازی ۴تایی)."""
    return "-".join(raw[i:i + 4] for i in range(0, len(raw), 4))


def get_device_code(device_id: str | None = None) -> str:
    did = (device_id or get_device_id())[:12].upper()
    return format_code(did)


def normalize_code(code: str) -> str:
    """«ab12-cd34-ef56»/«AB12 CD34EF56» → «AB12CD34EF56»."""
    return re.sub(r"[^0-9A-Fa-f]", "", str(code or "")).upper()


# ══════════════════════════════════════════════════════════════
#  کلید لایسنس (Ed25519) — دائمی و زمان‌دار
# ══════════════════════════════════════════════════════════════
def expiry_to_8(until) -> str | None:
    """None | int(روز از امروز) | date/datetime | 'YYYY-MM-DD'/'YYYYMMDD' → 'YYYYMMDD'."""
    if until is None:
        return None
    if isinstance(until, bool):
        raise ValueError("bad expiry")
    if isinstance(until, int):
        if until <= 0:
            raise ValueError("days must be > 0")
        d = date.today() + timedelta(days=until)
    elif isinstance(until, datetime):
        d = until.date()
    elif isinstance(until, date):
        d = until
    else:
        s = re.sub(r"[^0-9]", "", str(until))
        if len(s) == 8:
            d = datetime.strptime(s, "%Y%m%d").date()
        else:
            raise ValueError("expiry must be YYYY-MM-DD / YYYYMMDD / int days / date")
    if not (2025 <= d.year <= 2099):
        raise ValueError("expiry year out of range")
    return d.strftime("%Y%m%d")


def _key_message(device_code: str, expiry8: str) -> bytes:
    return f"{_MESSAGE_PREFIX}|{device_code}|{expiry8}".encode("ascii")


def _vendor_seed(seed: str | None = None, seed_file: str | None = None) -> bytes:
    """کلید خصوصی سازنده — فقط از ورودی صریح یا فایل/متغیر محیطی (هرگز از گیت)."""
    if seed is not None:
        s = re.sub(r"\s+", "", str(seed))
        if len(s) != 64 or not _HEX_RE.match(s):
            raise ValueError("seed must be 64 hex chars")
        return bytes.fromhex(s)
    path = None
    if seed_file:
        path = Path(seed_file)
    elif os.environ.get("ODIN_LICENSE_SEED_FILE"):
        path = Path(os.environ["ODIN_LICENSE_SEED_FILE"])
    elif DEFAULT_SEED_FILE.exists():
        path = DEFAULT_SEED_FILE
    if path is not None:
        text = path.read_text(encoding="utf-8")
        m = re.search(r"[0-9A-Fa-f]{64}", text)
        if not m:
            raise ValueError(f"no 64-hex seed in {path}")
        return bytes.fromhex(m.group(0))
    env = os.environ.get("ODIN_LICENSE_SEED")
    if env:
        s = re.sub(r"\s+", "", env)
        if len(s) == 64 and _HEX_RE.match(s):
            return bytes.fromhex(s)
    raise ValueError(
        "کلید خصوصی سازنده در دسترس نیست — از --seed HEX، --seed-file PATH، "
        "متغیر ODIN_LICENSE_SEED یا فایل installer/odin-license.secret استفاده کنید")


def generate_license_key(device_code: str, until=None, seed: str | None = None,
                         seed_file: str | None = None) -> str:
    """تولید کلید — ابزار سمت سازنده (نیازمند کلید خصوصی).

    until=None → کلید دائمی «Base32 ۱۰۳ نویسه»
    otherwise  → «Base32-YYMMDD» (انقضا پایانِ آن روز، UTC)
    """
    expiry8 = expiry_to_8(until) or _PERMANENT_EXPIRY
    code = normalize_code(device_code)
    if len(code) != 12 or not _HEX_RE.match(code):
        raise ValueError("device_code must be 12 hex chars")
    signature = ed25519.sign(_key_message(code, expiry8), _vendor_seed(seed, seed_file))
    key = b32_encode(signature)
    return f"{key}-{expiry8[2:]}" if expiry8 != _PERMANENT_EXPIRY else key


def parse_key_input(raw: str) -> tuple[str, str | None]:
    """رشتهٔ ورودی کاربر → (Base32 ۱۰۳‌نویسه‌ایِ امضا, expiry8|None).

    Base32 بدون خط‌تیره است؛ خط‌تیره فقط جداکنندهٔ پسوند تاریخ است. اگر کاربر
    خط‌تیره تایپ کرد، حذفش می‌کنیم — به‌شرطی که پسوند تاریخ همچنان روشن باشد.
    """
    s = re.sub(r"\s+", "", str(raw or "")).upper()
    if not s:
        raise ValueError("empty key")
    expiry8 = None
    body = s
    if "-" in s:
        head, _, tail = s.rpartition("-")
        if head and len(tail) == 6 and tail.isdigit():
            expiry8 = _validate_yy_mm_dd(tail)     # ۳۱ فوریه اینجا رد می‌شود
            body = head
        # خط‌تیرهٔ داخلی/زائد در بدنه بعداً حذف می‌شود
    body = body.replace("-", "")
    # پسوند تاریخِ بدون خط‌تیره (تایپ دستی): ۱۰۹ نویسه که ۶ تای آخر رقم است.
    # کلید دائمی دقیقاً ۱۰۳ نویسه است، پس این حالت روی آن سرک نمی‌خورد.
    if expiry8 is None and len(body) == _SIG_B32_LEN + 6 and body[_SIG_B32_LEN:].isdigit():
        expiry8 = _validate_yy_mm_dd(body[_SIG_B32_LEN:])
        body = body[:_SIG_B32_LEN]
    if len(body) != _SIG_B32_LEN or not re.match(rf"^[A-Z2-7]{{{_SIG_B32_LEN}}}$", body):
        raise ValueError("key body must be 103 base32 chars")
    return body, expiry8


def _validate_yy_mm_dd(yy_mm_dd: str) -> str:
    try:
        d = datetime.strptime("20" + yy_mm_dd, "%Y%m%d")
    except ValueError:
        raise ValueError("bad expiry suffix")
    return d.strftime("%Y%m%d")


def validate_license(license_key: str, device_code: str | None = None,
                     now: datetime | None = None) -> tuple[bool, str]:
    """اعتبارسنجی کلید (دائمی/زمان‌دار) در برابر کد دستگاه و تاریخ امروز."""
    now = now or datetime.now()
    try:
        body, expiry8 = parse_key_input(license_key)
    except ValueError:
        return False, ("فرمت کلید نادرست است — کلِ رشتهٔ دریافتی از سازنده را وارد کنید "
                       "(کلیدها ۱۰۳ نویسه‌اند؛ کلیدهای زمان‌دار یک بخش تاریخ ۶ رقمی هم دارند)")
    try:
        code = normalize_code(device_code) if device_code else normalize_code(get_device_code())
        if len(code) != 12 or not _HEX_RE.match(code):
            raise ValueError
    except ValueError:
        return False, "شناسهٔ دستگاه نامعتبر است"
    eff_expiry = expiry8 or _PERMANENT_EXPIRY
    if expiry8 and now.strftime("%Y%m%d") > expiry8:
        d = datetime.strptime(expiry8, "%Y%m%d").date()
        return False, f"این کلید در {d.isoformat()} منقضی شده — برای تمدید با سازنده تماس بگیرید"
    try:
        signature = b32_decode(body)
    except ValueError:
        return False, "کلید نامعتبر است"
    if not ed25519.verify(signature, _key_message(code, eff_expiry), PUBLIC_KEY):
        return False, ("امضای این کلید نامعتبر است یا برای دستگاه دیگری صادر شده — "
                       "کد دستگاه را برای سازنده بفرستید و کلید همان دستگاه را بگیرید")
    if expiry8:
        return True, f"لایسنس معتبر است (تا {expiry8[:4]}-{expiry8[4:6]}-{expiry8[6:]})"
    return True, "لایسنس معتبر است (دائمی)"


# ══════════════════════════════════════════════════════════════
#  ذخیره‌سازی لایسنس
# ══════════════════════════════════════════════════════════════
def get_license_file_path() -> Path:
    data_dir = app_paths.data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "license.dat"


def save_license(license_key: str, device_id: str, user_name: str = "",
                 expires_at: str | None = None) -> bool:
    try:
        data = {
            "license_key": license_key,
            "device_id": device_id,
            "user_name": user_name,
            "expires_at": expires_at,
            "activated_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "version": "3.0",
        }
        f = get_license_file_path()
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        try:
            os.chmod(f, 0o600)
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"خطا در ذخیره لایسنس: {e}")
        return False


def load_license() -> dict | None:
    try:
        f = get_license_file_path()
        if not f.exists():
            return None
        with open(f, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _touch(path: Path, data: dict) -> None:
    try:
        data["last_seen"] = datetime.now().isoformat()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _rolled_back(last_seen_iso: str | None, now: datetime) -> bool:
    """عقب‌رفتن محسوس ساعت = نشانهٔ دستکاری (برای انقضا/تریال)."""
    if not last_seen_iso:
        return False
    try:
        ls = datetime.fromisoformat(last_seen_iso)
    except Exception:
        return False
    return now < ls - timedelta(hours=_ROLLBACK_TOLERANCE_H)


def is_activated(now: datetime | None = None) -> bool:
    """کلید معتبرِ همین دستگاه + عدم انقضا + قفل device_id + سلامت ساعت."""
    now = now or datetime.now()
    data = load_license()
    if not data:
        return False
    if data.get("device_id") != get_device_id():
        return False
    if _rolled_back(data.get("last_seen"), now):
        return False
    ok, _ = validate_license(data.get("license_key", ""), now=now)
    if ok:
        _touch(get_license_file_path(), data)
    return ok


def activate_program(license_key: str, user_name: str = "") -> tuple[bool, str]:
    ok, message = validate_license(license_key)
    if not ok:
        return False, message
    try:
        _, expiry8 = parse_key_input(license_key)
    except ValueError:
        expiry8 = None
    if not save_license(license_key, get_device_id(), user_name, expires_at=expiry8):
        return False, "خطا در ذخیره لایسنس"
    return True, message


def deactivate_program() -> bool:
    try:
        f = get_license_file_path()
        if f.exists():
            f.unlink()
        return True
    except Exception as e:
        print(f"خطا در غیرفعال‌سازی: {e}")
        return False


# ══════════════════════════════════════════════════════════════
#  دورهٔ آزمایشی (۷ روز، تمام امکانات)
# ══════════════════════════════════════════════════════════════
def get_trial_file_path() -> Path:
    data_dir = app_paths.data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "trial.dat"


def load_trial() -> dict | None:
    try:
        f = get_trial_file_path()
        if not f.exists():
            return None
        with open(f, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def start_trial(now: datetime | None = None) -> tuple[bool, str]:
    """یک‌بار قابل شروع است؛ تکرار آن روزها را تمدید نمی‌کند (ضدتقلب)."""
    now = now or datetime.now()
    if load_trial():
        return False, "دورهٔ آزمایشی قبلاً شروع شده است"
    try:
        f = get_trial_file_path()
        with open(f, "w", encoding="utf-8") as fh:
            json.dump({"started_at": now.isoformat(),
                       "last_seen": now.isoformat(),
                       "days": TRIAL_DAYS}, fh, indent=2)
        try:
            os.chmod(f, 0o600)
        except Exception:
            pass
        return True, f"دورهٔ آزمایشی {TRIAL_DAYS} روزه شروع شد"
    except Exception as e:
        return False, f"خطا در شروع دورهٔ آزمایشی: {e}"


def trial_status(now: datetime | None = None) -> dict:
    """→ {exists, active, days_left, tampered}"""
    now = now or datetime.now()
    data = load_trial()
    if not data:
        return {"exists": False, "active": False, "days_left": 0, "tampered": False}
    if _rolled_back(data.get("last_seen"), now):
        return {"exists": True, "active": False, "days_left": 0, "tampered": True}
    try:
        started = datetime.fromisoformat(data["started_at"])
    except Exception:
        return {"exists": True, "active": False, "days_left": 0, "tampered": True}
    days = int(data.get("days") or TRIAL_DAYS)
    used = max(0.0, (now - started).total_seconds() / 86400.0)
    days_left = max(0, days - int(used))
    return {"exists": True, "active": used < days,
            "days_left": days_left, "tampered": False}


# ══════════════════════════════════════════════════════════════
#  دروازهٔ اجرا
# ══════════════════════════════════════════════════════════════
def license_bypassed() -> bool:
    """حالت توسعه/تست: ODIN_SKIP_LICENSE=1 یا Qt offscreen."""
    if os.environ.get("ODIN_SKIP_LICENSE") == "1":
        return True
    return os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen"


def check_and_enforce_license(now: datetime | None = None) -> tuple[bool, str]:
    """دروازهٔ اجرا: bypass → لایسنس → تریال. Returns (اجازهٔ ادامه, پیام)."""
    if license_bypassed():
        return True, "حالت توسعه/تست — لایسنس نادیده گرفته شد"
    if is_activated(now):
        return True, "لایسنس معتبر است"
    t = trial_status(now)
    if t["active"]:
        return True, f"دورهٔ آزمایشی — {t['days_left']} روز باقی است"
    if t["tampered"]:
        return False, "دورهٔ آزمایشی نامعتبر است (ساعت دستگاه به عقب برگشته) — لایسنس وارد کنید"
    if t["exists"]:
        return False, "دورهٔ آزمایشی تمام شده است — کلید لایسنس وارد کنید"
    return False, "برنامه فعال نشده است. لایسنس بخرید یا دورهٔ آزمایشی ۷ روزه را شروع کنید."


# ══════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════
def _cli(argv: list[str]) -> int:
    cmd = (argv[0] if argv else "device").lower()
    if cmd == "device":
        did = get_device_id()
        print(f"شناسهٔ کامل دستگاه : {did}")
        print(f"کد دستگاه (برای سازنده): {get_device_code(did)}")
        return 0
    if cmd == "public":
        print(f"کلید عمومی امضای لایسنس: {PUBLIC_KEY_HEX}")
        print(f"پیش‌نمایش کلید عمومی (Base32): {b32_encode(PUBLIC_KEY)}")
        return 0
    if cmd == "keypair":
        import secrets
        seed = secrets.token_bytes(32)
        print(f"کلید خصوصی (۶۴ هگز، راز بسازید و نگه دارید): {seed.hex().upper()}")
        print(f"کلید عمومی  (همان کلید عمومی را در اپ بگذارید): "
              f"{ed25519.public_key(seed).hex().upper()}")
        return 0
    if cmd == "gen":
        args = argv[1:]
        until = None
        seed = None
        seed_file = None
        pos = []
        i = 0
        while i < len(args):
            if args[i] == "--days" and i + 1 < len(args):
                until = int(args[i + 1]); i += 2
            elif args[i] == "--until" and i + 1 < len(args):
                until = args[i + 1]; i += 2
            elif args[i] == "--seed" and i + 1 < len(args):
                seed = args[i + 1]; i += 2
            elif args[i] == "--seed-file" and i + 1 < len(args):
                seed_file = args[i + 1]; i += 2
            else:
                pos.append(args[i]); i += 1
        if not pos:
            print("کاربرد: python -m src.license gen <DEVICE-CODE> "
                  "[--days N | --until YYYY-MM-DD] [--seed HEX | --seed-file PATH]")
            return 2
        try:
            print(generate_license_key(pos[0], until, seed=seed, seed_file=seed_file))
        except ValueError as e:
            print(f"نامعتبر: {e}")
            return 2
        return 0
    if cmd == "check":
        if len(argv) < 3:
            print("کاربرد: python -m src.license check <KEY> <DEVICE-CODE>")
            return 2
        ok, msg = validate_license(argv[1], argv[2])
        print(("✅ " if ok else "❌ ") + msg)
        return 0 if ok else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
