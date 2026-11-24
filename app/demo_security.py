"""Restricted public virtual-credit demo. No provider or money wallet admission."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import threading
import time
from collections import OrderedDict
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

COOKIE = "__Host-uno_demo_session"
PORTAL = "https://xd-play.com"
READ_API = {"/api/orbit/state", "/api/spin/history", "/api/spin/rules",
            "/api/ui-version", "/api/sounds/manifest", "/api/sounds/health"}
WRITE_API = {"/api/orbit/pick": "POST", "/api/spin/daily": "POST",
             "/api/spin/refill": "POST", "/api/spin/profile": "PATCH"}


def demo_mode(values=None):
    return (os.environ if values is None else values).get("UNO_RELEASE_MODE") == "virtual-demo"


def demo_admission(values=None):
    env = os.environ if values is None else values
    return demo_mode(env) and env.get("UNO_VIRTUAL_DEMO_ENABLED") == "1"


def csrf_token(token: str) -> str:
    # The session is 288 random bits, HttpOnly, host-only and never exposed.
    # Domain separation prevents using the CSRF token as a session credential.
    return hmac.new(token.encode(), b"uno-virtual-demo-csrf-v1", hashlib.sha256).hexdigest()


def guard_demo_write(request: Request):
    if not demo_mode():
        return
    origin = request.headers.get("origin", "")
    allowed = os.getenv("UNO_ALLOWED_ORIGINS", "").split(",")
    if origin not in allowed or urlsplit(origin).netloc != request.headers.get("host"):
        raise HTTPException(403, "Origin not allowed")
    raw = request.cookies.get(COOKIE, "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{30,90}", raw):
        raise HTTPException(401, "Open the game to create a demo session")
    if not hmac.compare_digest(request.headers.get("x-uno-csrf", ""), csrf_token(raw)):
        raise HTTPException(403, "CSRF token required; reload the game")


class Budget:
    """Bounded per-process limiter; the demo intentionally uses one replica."""
    def __init__(self):
        self.entries = OrderedDict()
        self.lock = threading.Lock()

    def allow(self, key, limit, now=None):
        minute = int((time.monotonic() if now is None else now) // 60)
        with self.lock:
            value = self.entries.get(key)
            count = value[1] if value and value[0] == minute else 0
            if count >= limit:
                return False
            if key not in self.entries and len(self.entries) >= 4096:
                # Fail closed when all slots belong to this minute.
                old = next(iter(self.entries))
                if self.entries[old][0] == minute:
                    return False
                self.entries.pop(old)
            self.entries[key] = (minute, count + 1)
            self.entries.move_to_end(key)
            return True


budget = Budget()


class DemoBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not demo_mode() or scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        headers = Headers(scope=scope)
        path, method = scope["path"], scope["method"]
        origins = os.getenv("UNO_ALLOWED_ORIGINS", "").split(",")
        host = headers.get("host", "")
        allowed_hosts = {urlsplit(o).netloc for o in origins if o.startswith("https://")}

        async def secure_send(message):
            if message["type"] == "http.response.start":
                h = MutableHeaders(scope=message)
                framed = path == "/play/" and method == "GET" and message["status"] == 200
                h["Content-Security-Policy"] = (
                    "default-src 'self'; base-uri 'none'; object-src 'none'; "
                    "script-src 'self'; style-src 'self'; img-src 'self' data:; "
                    "font-src 'self'; media-src 'self' blob:; connect-src 'self'; "
                    "form-action 'none'; frame-src 'none'; frame-ancestors " +
                    (PORTAL if framed else "'none'"))
                if not framed:
                    h["X-Frame-Options"] = "DENY"
                h["X-Content-Type-Options"] = "nosniff"
                h["Referrer-Policy"] = "no-referrer"
                h["Strict-Transport-Security"] = "max-age=31536000"
                h["Permissions-Policy"] = 'camera=(), microphone=(), geolocation=(), payment=(), fullscreen=(self "https://xd-play.com")'
                if path.startswith("/api/") or not path.startswith("/assets/") or message["status"] >= 400:
                    h["Cache-Control"] = "no-store"
            await send(message)

        async def deny(code, message):
            return await JSONResponse({"detail": message}, status_code=code)(scope, receive, secure_send)

        # Railway's internal health probe is the only host exception, and cannot
        # create a session or mutate gameplay state.
        if host not in allowed_hosts and path != "/health":
            return await deny(400, "Host not allowed")
        if any(part in path for part in ("/admin", "/studio", "sound-studio.js")) or path in {"/classic", "/spin-legacy", "/openapi.json"}:
            return await deny(404, "Not found")
        if path.startswith("/assets/") and path.endswith(".html"):
            return await deny(404, "Not found")
        if path.startswith("/api/"):
            if method in ("GET", "HEAD"):
                if path not in READ_API and not path.startswith("/api/sounds/files/"):
                    return await deny(404, "Not found")
            elif WRITE_API.get(path) != method:
                return await deny(403, "Public mutation not available")
            if headers.get("sec-fetch-site") in {"same-site", "cross-site"}:
                return await deny(403, "Cross-origin API access not allowed")
            origin = headers.get("origin")
            if origin and (origin not in origins or urlsplit(origin).netloc != host):
                return await deny(403, "Origin not allowed")
            request = Request(scope)
            raw = request.cookies.get(COOKIE, "")
            key = hashlib.sha256(raw.encode()).hexdigest() if raw else "anonymous"
            if not budget.allow("global", 6000) or not budget.allow(key, 180):
                return await deny(429, "Demo request limit; try again shortly")
            if path == "/api/orbit/state" and not raw and not budget.allow("new-session", 60):
                return await deny(429, "Demo session limit; try again shortly")
            if method not in ("GET", "HEAD"):
                if headers.get("content-type", "").split(";")[0] != "application/json":
                    return await deny(415, "JSON required")
                # Consume with a strict bound, including chunked bodies.
                body = bytearray()
                while True:
                    chunk = await receive()
                    if chunk["type"] == "http.disconnect":
                        return
                    body.extend(chunk.get("body", b""))
                    if len(body) > 16384:
                        return await deny(413, "Request too large")
                    if not chunk.get("more_body"):
                        break
                consumed = False
                async def bounded_receive():
                    nonlocal consumed
                    if consumed:
                        return await receive()
                    consumed = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await self.app(scope, bounded_receive, secure_send)
        await self.app(scope, receive, secure_send)
