"""Fail-closed guardrails for an *unqualified* public production release.

The active staging/QA behavior is untouched.  A future production release
needs a separately reviewed replacement for the hard-coded admissions freeze.
These checks never authorize wallet writes or validate a live economy.
"""
from __future__ import annotations

import os
from pathlib import PurePosixPath
from typing import Mapping
from urllib.parse import urlsplit
from .demo_security import demo_mode, demo_admission, READ_API, WRITE_API


PRODUCTION_KEYS = ("RAILWAY_ENVIRONMENT_NAME", "UNO_DEPLOYMENT_TIER", "UNO_ENVIRONMENT")
PRIVATE_EDITOR_PATHS = frozenset({
    "/admin", "/admin/", "/assets/admin.html", "/assets/admin.js", "/assets/admin.css",
})


def is_production(values: Mapping[str, str] | None = None) -> bool:
    env = os.environ if values is None else values
    return any(str(env.get(key, "")).strip().lower() == "production"
               for key in PRODUCTION_KEYS)


def data_volume_path(raw: str) -> bool:
    """Require a normalized file/folder below /data, never /tmp or /data itself."""
    if not isinstance(raw, str) or not raw.startswith("/data/"):
        return False
    p = PurePosixPath(raw)
    return bool(raw == str(p) and p.is_absolute() and len(p.parts) >= 3
                and ".." not in raw.split("/") and "\x00" not in raw)


def allowed_https_origins(raw: str) -> bool:
    items = [part.strip() for part in raw.split(",") if part.strip()]
    if not items:
        return False
    for item in items:
        split = urlsplit(item)
        if (split.scheme != "https" or not split.hostname
                or split.username or split.password
                or split.path not in ("", "/") or split.query or split.fragment
                or "*" in item or split.hostname in ("localhost", "127.0.0.1")
                or item != split.geturl().rstrip("/")):
            return False
    return len(items) == len(set(items))


def check_production_environment(values: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Named configuration problems only. Never output secret values."""
    env = os.environ if values is None else values
    if not is_production(env):
        return ()
    errors: list[str] = []
    if not data_volume_path(str(env.get("UNO_SPIN_DB_PATH", ""))):
        errors.append("UNO_SPIN_DB_PATH must be an explicit persistent /data file")
    if not data_volume_path(str(env.get("UNO_SOUND_STORAGE_DIR", ""))):
        errors.append("UNO_SOUND_STORAGE_DIR must be an explicit persistent /data folder")
    if not allowed_https_origins(str(env.get("UNO_ALLOWED_ORIGINS", ""))):
        errors.append("UNO_ALLOWED_ORIGINS must list exact HTTPS origins")
    if env.get("UNO_SOUND_ADMIN_TOKEN"):
        errors.append("Public production service must not hold UNO_SOUND_ADMIN_TOKEN")
    if env.get("GAMEOPS_WALLET_COMMANDS_ENABLED", "").strip() == "1":
        errors.append("GAMEOPS_WALLET_COMMANDS_ENABLED must remain disabled")
    if env.get("UNO_PUBLIC_ROUNDS_ENABLED", "").strip() == "1":
        errors.append("UNO_PUBLIC_ROUNDS_ENABLED is not qualified for production")
    if demo_mode(env):
        if env.get("GAMEOPS_BRIDGE_ENABLED", "0") != "0":
            errors.append("Public demo must have GAMEOPS_BRIDGE_ENABLED=0")
        if any(env.get(k) for k in ("GAMEOPS_BRIDGE_SECRET", "DATABASE_URL", "REDIS_URL", "UNO_SOUND_ADMIN_TOKEN")):
            errors.append("Public demo must not hold staging/provider credentials")
        origins = env.get("UNO_ALLOWED_ORIGINS", "").split(",")
        if "https://uno.xd-play.com" not in origins or any(
            o != "https://uno.xd-play.com" and not re_full_demo_host(o) for o in origins
        ):
            errors.append("Demo origins must be canonical UNO and its production Railway host")
    if any(k.startswith(("UNO_QA_", "UNO_DEMO_"))
           and str(v).strip().lower() not in ("", "0", "false", "off")
           for k, v in env.items()):
        errors.append("UNO_QA_/UNO_DEMO_ fixtures are active")
    return tuple(errors)


def re_full_demo_host(origin):
    import re
    return bool(re.fullmatch(r"https://uno-demo-web-production\.[a-z0-9-]*up\.railway\.app", origin))


def require_safe_production_configuration(values: Mapping[str, str] | None = None) -> None:
    issues = check_production_environment(values)
    if issues:
        raise RuntimeError("UNO LUCK production startup blocked: " + "; ".join(issues))


def public_request_block(method: str, path: str,
                         values: Mapping[str, str] | None = None) -> str | None:
    """An explicit hard stop, not permission based on a user-controlled header."""
    if not is_production(values):
        return None
    if path in PRIVATE_EDITOR_PATHS:
        return "private_editor"
    if path == "/api/sounds/admin/check":
        return "private_editor"
    if path.startswith("/api/sounds/") and method.upper() not in ("GET", "HEAD", "OPTIONS"):
        return "sound_publish"
    # These original guest and Orbit endpoints are not the certified Genesis
    # admission/wallet protocol. No environment flag unlocks them in this patch.
    if path.startswith(("/api/spin/", "/api/orbit/")):
        if demo_admission(values) and (
            (method.upper() in ("GET", "HEAD") and path in READ_API)
            or WRITE_API.get(path) == method.upper()
        ):
            return None
        return "rounds_closed"
    return None
