"""Shared admin authentication; optional password hash and existing API token."""
import hashlib
import os
import secrets
import threading
import time
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

ITERATIONS = 600_000
WINDOW = 60
ATTEMPTS = 8
_attempts = {}
_lock = threading.Lock()


def hash_password(password: str) -> str:
    if not 8 <= len(password) <= 1024:
        raise ValueError("Password must contain 8–1024 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def _decode(encoded):
    try:
        algorithm, rounds, salt, digest = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or rounds != str(ITERATIONS):
            return None
        salt, digest = bytes.fromhex(salt), bytes.fromhex(digest)
        return (salt, digest) if len(salt) == 16 and len(digest) == 32 else None
    except (ValueError, TypeError):
        return None


def require_admin(request: Request) -> None:
    token = os.environ.get("UNO_SOUND_ADMIN_TOKEN", "")
    password = _decode(os.environ.get("UNO_ADMIN_PASSWORD_HASH", ""))
    if len(token) < 32 and password is None:
        raise HTTPException(503, "Akses admin belum dikonfigurasi")
    origin = request.headers.get("origin")
    if origin:
        parts = urlsplit(origin)
        if parts.scheme not in ("https", "http") or parts.netloc != request.headers.get("host", ""):
            raise HTTPException(403, "Origin tidak diizinkan")
    supplied = request.headers.get("x-uno-sound-admin", "")
    if len(token) >= 32 and secrets.compare_digest(supplied.encode(), token.encode()):
        return
    if password is None or not 8 <= len(supplied) <= 1024:
        raise HTTPException(403, "Password atau kunci admin salah")

    # Bound expensive password checks. Trust the server's client address, never
    # a caller-supplied forwarding header. State is local to this worker.
    peer = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _lock:
        for key in [key for key, (_, until) in _attempts.items() if until <= now]:
            del _attempts[key]
        count, until = _attempts.get(peer, (0, now + WINDOW))
        if count >= ATTEMPTS or (peer not in _attempts and len(_attempts) >= 1024):
            raise HTTPException(429, "Terlalu banyak percobaan. Coba lagi dalam 60 detik.",
                                headers={"Retry-After": str(WINDOW)})
        _attempts[peer] = (count + 1, until)
    salt, expected = password
    actual = hashlib.pbkdf2_hmac("sha256", supplied.encode(), salt, ITERATIONS)
    if not secrets.compare_digest(actual, expected):
        raise HTTPException(403, "Password atau kunci admin salah")
    with _lock:
        _attempts.pop(peer, None)
