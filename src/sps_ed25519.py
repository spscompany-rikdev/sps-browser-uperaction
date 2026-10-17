"""
Ed25519 signatures (RFC 8032), pure Python - no third-party dependency.

SPS Browser uses it ONLY to check that an update announcement was signed by the SPS Browser owner's private key
(see sps_updater.py).  The private key never ships with the browser; signing is done by tools/publish_update.py.

This is the reference algorithm of RFC 8032 section 6.  It is not constant-time, which is fine for verification of
public data; do not reuse it to sign secrets on a shared machine.  It is checked against the RFC test vectors in
tests/test_updater.py and by the start-up self-test (sps_ed25519.self_test()).
"""
import hashlib

_P = 2 ** 255 - 19
_Q = 2 ** 252 + 27742317777372353535851937790883648493


def _sha512(data):
    return hashlib.sha512(data).digest()


def _inv(x):
    return pow(x, _P - 2, _P)


_D = -121665 * _inv(121666) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _recover_x(y, sign):
    if y >= _P:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_GY = 4 * _inv(5) % _P
_GX = _recover_x(_GY, 0)
_G = (_GX, _GY, 1, _GX * _GY % _P)


def _add(a, b):
    A = (a[1] - a[0]) * (b[1] - b[0]) % _P
    B = (a[1] + a[0]) * (b[1] + b[0]) % _P
    C = 2 * a[3] * b[3] * _D % _P
    D = 2 * a[2] * b[2] % _P
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _P, G * H % _P, F * G % _P, E * H % _P)


def _mul(s, pt):
    result = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            result = _add(result, pt)
        pt = _add(pt, pt)
        s >>= 1
    return result


def _equal(a, b):
    return (a[0] * b[2] - b[0] * a[2]) % _P == 0 and (a[1] * b[2] - b[1] * a[2]) % _P == 0


def _compress(pt):
    zinv = _inv(pt[2])
    x, y = pt[0] * zinv % _P, pt[1] * zinv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(s):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _expand(secret):
    if len(secret) != 32:
        raise ValueError("an Ed25519 secret key is 32 bytes")
    h = _sha512(secret)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_key(secret):
    """32-byte secret key -> 32-byte public key."""
    return _compress(_mul(_expand(secret)[0], _G))


def sign(secret, message):
    """-> 64-byte signature."""
    a, prefix = _expand(secret)
    A = _compress(_mul(a, _G))
    r = int.from_bytes(_sha512(prefix + message), "little") % _Q
    Rs = _compress(_mul(r, _G))
    h = int.from_bytes(_sha512(Rs + A + message), "little") % _Q
    s = (r + h * a) % _Q
    return Rs + int.to_bytes(s, 32, "little")


def verify(public, message, signature):
    """True only for a valid signature. Never raises on malformed input."""
    try:
        if len(public) != 32 or len(signature) != 64:
            return False
        A = _decompress(public)
        if A is None:
            return False
        Rs = signature[:32]
        R = _decompress(Rs)
        if R is None:
            return False
        s = int.from_bytes(signature[32:], "little")
        if s >= _Q:
            return False
        h = int.from_bytes(_sha512(Rs + public + message), "little") % _Q
        return _equal(_mul(s, _G), _add(R, _mul(h, A)))
    except Exception:
        return False


def self_test():
    """RFC 8032 test vector 1 (empty message). True when this implementation is correct."""
    sk = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    pk = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    sig = bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
                        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
    return public_key(sk) == pk and sign(sk, b"") == sig and verify(pk, b"", sig) and not verify(pk, b"x", sig)
