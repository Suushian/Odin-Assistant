# -*- coding: utf-8 -*-
"""Ed25519 (RFC 8032) — پیاده‌سازی خالص‌پایتون، بدون هیچ وابستگی.

چرا Ed25519: لایسنس ODIN باید **آفلاین** و **بدون سرور** اعتبارسنجی شود، ولی
با HMAC رازِ مشترک داخلِ اپ است و هر کس می‌تواند keygen بسازد. با امضای
نامتقارن، اپ فقط **کلید عمومی** را دارد و فقط «تأیید» می‌کند؛ ساختن کلید
لایسنس به **کلید خصوصی** نیاز دارد که هرگز در اپ/ریپو نیست.

منبع حقیقت: RFC 8032 و پیاده‌سازی مرجعِ ed25519.cr.yp.to (همان نسخه‌ای که
تصدیق شده با node:crypto و وکتورهای RFC 8032).
"""
from __future__ import annotations

import hashlib

P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
D = (-121665 * pow(121666, P - 2, P)) % P


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _inv(x: int) -> int:
    return pow(x, P - 2, P)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(D * y * y + 1) % P
    x = pow(xx, (P + 3) // 8, P)
    if (x * x - xx) % P != 0:
        x = x * pow(2, (P - 1) // 4, P) % P
    if x % 2 != 0:
        x = P - x
    return x


_BY = (4 * _inv(5)) % P
_BX = _xrecover(_BY)
_B = (_BX, _BY, 1, (_BX * _BY) % P)          # نقطهٔ پایه در مختصات ocin


def _edwards_add(p, q):
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % P
    b = (y1 + x1) * (y2 + x2) % P
    c = 2 * D * t1 * t2 % P
    d = 2 * z1 * z2 % P
    e = b - a
    f = d - c
    g = d + c
    h = b + a
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _scalarmult(pt, e: int):
    q = (0, 1, 1, 0)
    while e > 0:
        if e & 1:
            q = _edwards_add(q, pt)
        pt = _edwards_add(pt, pt)
        e >>= 1
    return q


def _encode_int(y: int) -> bytes:
    return y.to_bytes(32, "little")


def _encode_point(pt) -> bytes:
    x, y, z, _t = pt
    zi = _inv(z)
    x = x * zi % P
    y = y * zi % P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _decode_int(b: bytes) -> int:
    return int.from_bytes(b, "little")


def _on_curve(pt) -> bool:
    x, y, z, t = pt
    return (-x * x + y * y - z * z - D * t * t) % P == 0 and (x * y - z * t) % P == 0


def _decode_point(b: bytes):
    y = int.from_bytes(b, "little") & ((1 << 255) - 1)
    x = _xrecover(y)
    if (x & 1) != ((b[31] >> 7) & 1):
        x = P - x
    pt = (x, y, 1, x * y % P)
    if not _on_curve(pt):
        raise ValueError("point not on curve")
    return pt


def _clamp_seed_scalar(h: bytes) -> int:
    """۳۲ بایت اولِ hash سید → اسکالر امضای Ed25519 (RFC 8032 §5.1.6)."""
    a = _decode_int(h[:32])
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a


def public_key(seed: bytes) -> bytes:
    """سید ۳۲ بایتی → کلید عمومی ۳۲ بایتی."""
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    return _encode_point(_scalarmult(_B, _clamp_seed_scalar(_sha512(seed))))


def sign(message: bytes, seed: bytes, public: bytes | None = None) -> bytes:
    """امضای ۶۴ بایتی روی message. (Ed25519 قطعی است: هر بار یک امضا.)"""
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    h = _sha512(seed)
    a = _clamp_seed_scalar(h)
    if public is None:
        public = _encode_point(_scalarmult(_B, a))
    r = _decode_int(_sha512(h[32:64] + message))
    r_pt = _scalarmult(_B, r)
    s = (r + _decode_int(_sha512(_encode_point(r_pt) + public + message)) * a) % L
    return _encode_point(r_pt) + _encode_int(s)


def verify(signature: bytes, message: bytes, public: bytes) -> bool:
    """آیا امضا با کلید عمومی روی message درست است؟ (بدون استثنا ↔ False)"""
    if len(signature) != 64 or len(public) != 32:
        return False
    try:
        r_pt = _decode_point(signature[:32])
        a_pt = _decode_point(public)
    except Exception:
        return False
    s = _decode_int(signature[32:])
    if s >= L:
        return False
    h = _decode_int(_sha512(signature[:32] + public + message))
    left = _scalarmult(_B, s)
    right = _edwards_add(r_pt, _scalarmult(a_pt, h))
    return _encode_point(left) == _encode_point(right)


def is_valid_public_key(public: bytes) -> bool:
    if len(public) != 32:
        return False
    try:
        _decode_point(public)
        return True
    except Exception:
        return False
