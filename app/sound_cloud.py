"""Admin-published virtual-game sound catalog shared by desktop and mobile.

Sound files and trims are stored outside the image on a Railway persistent
volume. Browsing / playback is public. Publishing requires a server-only secret.
No coupling to accounts, ledger, RNG, or virtual-coin tables.
"""
from __future__ import annotations

import json
import math
import os
import re
import secrets
import threading
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/sounds", tags=["UNO LUCK Shared Sounds"])
CUES = (
    "soft-tech-splash-screen", "loading-scene", "background-music",
    "push-button", "spinning-sound", "chosen-card", "result-sound",
    "jackpot-1", "jackpot-2", "jackpot-3", "jackpot-4", "jackpot-5",
)
EXT_MIMES = {
    ".mp3": "audio/mpeg", ".wav": "audio/wav",
    ".m4a": "audio/mp4", ".aac": "audio/aac",
    ".ogg": "audio/ogg", ".webm": "audio/webm",
}
MAX_FILE = 16 * 1024 * 1024
LOCK = threading.RLock()
NO_CACHE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def storage() -> Path:
    """No accidental ephemeral publishing on an unconfigured deployment."""
    root = os.environ.get("UNO_SOUND_STORAGE_DIR", "").strip()
    if not root or not Path(root).is_absolute():
        raise HTTPException(503, "Persistent sound storage belum dikonfigurasi")
    path = Path(root)
    try:
        path.mkdir(parents=True, exist_ok=True)
        (path / "audio").mkdir(exist_ok=True)
    except OSError:
        raise HTTPException(503, "Persistent sound storage tidak tersedia")
    return path


def _read(root: Path) -> dict:
    path = root / "manifest.json"
    if not path.exists():
        return {"revision": "initial", "cues": {}}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(manifest, dict) and isinstance(manifest.get("cues"), dict):
            return manifest
    except (ValueError, OSError):
        pass
    raise HTTPException(503, "Sound manifest tidak dapat dibaca")


def _write(root: Path, data: dict) -> None:
    tmp = root / ("manifest-" + secrets.token_hex(12) + ".tmp")
    try:
        with tmp.open("x", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, separators=(",", ":"))
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, root / "manifest.json")
    finally:
        tmp.unlink(missing_ok=True)


def require_admin(request: Request) -> None:
    expected = os.environ.get("UNO_SOUND_ADMIN_TOKEN", "")
    supplied = request.headers.get("x-uno-sound-admin", "")
    if len(expected) < 32:
        raise HTTPException(503, "Sound publishing belum dikonfigurasi")
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(403, "Admin Sound Studio authorization diperlukan")
    origin = request.headers.get("origin")
    if origin:
        parts = urlsplit(origin)
        if parts.scheme not in ("https", "http") or parts.netloc != request.headers.get("host", ""):
            raise HTTPException(403, "Origin tidak diizinkan")


def check_cue(key: str) -> None:
    if key not in CUES:
        raise HTTPException(404, "Sound tidak ditemukan")


def settings(value: object, *, duration: float | None = None) -> dict:
    if not isinstance(value, dict):
        raise HTTPException(422, "Sound settings tidak valid")
    try:
        start = float(value.get("start", 0))
        stop = float(value.get("stop", duration if duration is not None else 0))
        fade_in = float(value.get("fadeIn", 0))
        fade_out = float(value.get("fadeOut", 0))
        file_duration = float(value.get("fileDuration", duration or 0))
    except (TypeError, ValueError, OverflowError):
        raise HTTPException(422, "Format durasi tidak valid")
    if not all(math.isfinite(n) for n in (start, stop, fade_in, fade_out, file_duration)):
        raise HTTPException(422, "Sound settings tidak finite")
    if not (0 <= start < stop <= 3600 and stop-start >= .02 and
            fade_in >= 0 and fade_out >= 0 and
            fade_in + fade_out <= stop-start + .001 and
            0 < file_duration <= 3600 and stop <= file_duration + .01):
        raise HTTPException(422, "Rentang START, STOP, dan fade tidak valid")
    return {
        "start": round(start, 3), "stop": round(stop, 3),
        "fadeIn": round(fade_in, 3), "fadeOut": round(fade_out, 3),
        "fileDuration": round(file_duration, 3),
        "repeat": value.get("repeat", True) is not False,
    }


def _safe_name(filename: str) -> str:
    filename = unquote(filename).replace("\\", "/").split("/")[-1]
    filename = re.sub(r"[^\w .()\-]", "_", filename, flags=re.UNICODE).strip(" .")
    return (filename[:96] or "sound.mp3")


def _audio_mime(filename: str, data: bytes) -> tuple[str, str]:
    ext = Path(filename).suffix.lower()
    mime = EXT_MIMES.get(ext)
    if not mime:
        raise HTTPException(415, "Format audio tidak didukung")
    valid = {
        ".wav": data.startswith(b"RIFF") and data[8:12] == b"WAVE",
        ".mp3": data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 255 and data[1] & 224 == 224),
        ".m4a": len(data) >= 12 and data[4:8] == b"ftyp",
        ".aac": len(data) >= 2 and data[0] == 255 and data[1] & 240 == 240,
        ".ogg": data.startswith(b"OggS"),
        ".webm": data.startswith(bytes.fromhex("1a45dfa3")),
    }[ext]
    if not valid:
        raise HTTPException(415, "File tidak dikenali sebagai audio " + ext)
    return mime, ext


@router.get("/admin/check")
def check_admin(request: Request):
    require_admin(request)
    return Response(content='{"ok":true}', media_type="application/json", headers=NO_CACHE)


@router.get("/manifest")
def manifest():
    try:
        with LOCK:
            data = _read(storage())
    except HTTPException as error:
        if error.status_code == 503 and "belum dikonfigurasi" in str(error.detail):
            return Response(
                content=json.dumps({"ready": False, "revision": "initial", "cues": {}}),
                media_type="application/json", headers=NO_CACHE,
            )
        raise
    public = {}
    for cue, info in data["cues"].items():
        if cue not in CUES:
            continue
        clean = {name: info[name] for name in
                 ("source", "start", "stop", "fadeIn", "fadeOut", "fileDuration",
                  "repeat", "fileName", "revision") if name in info}
        if info.get("source") == "custom":
            clean["url"] = "/api/sounds/files/" + quote(cue) + "?v=" + quote(info["revision"])
        public[cue] = clean
    return Response(
        content=json.dumps({"ready": True, "revision": data["revision"], "cues": public,
                            "mixer": data.get("mixer", None)}),
        media_type="application/json", headers=NO_CACHE,
    )


@router.patch("/mixer")
async def publish_mixer(request: Request):
    require_admin(request)
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError()
        levels = {key: float(body[key]) for key in ("master", "music", "sfx")}
    except (ValueError, KeyError, TypeError, OverflowError):
        raise HTTPException(422, "Mixer settings tidak valid")
    if any(not math.isfinite(v) or v < 0 or v > 1 for v in levels.values()):
        raise HTTPException(422, "Mixer level harus antara 0 dan 1")
    with LOCK:
        root = storage()
        data = _read(root)
        data["mixer"] = levels
        data["revision"] = secrets.token_hex(12)
        _write(root, data)
    return {"published": True, "mixer": levels}


@router.get("/files/{cue}")
def download(cue: str):
    check_cue(cue)
    with LOCK:
        root = storage()
        info = _read(root)["cues"].get(cue)
        if not info or info.get("source") != "custom":
            raise HTTPException(404, "Sound file tidak ditemukan")
        filename = info.get("storageName", "")
        # Never trust manifest values as arbitrary filesystem paths.
        if not re.fullmatch(re.escape(cue) + r"-[a-f0-9]{24}\.(mp3|wav|m4a|aac|ogg|webm)", filename):
            raise HTTPException(503, "Sound manifest file invalid")
        path = root / "audio" / filename
        if not path.is_file():
            raise HTTPException(503, "Published audio file missing")
        return FileResponse(
            path, media_type=EXT_MIMES[Path(filename).suffix],
            headers={"Cache-Control": "public, max-age=60",
                     "X-Content-Type-Options": "nosniff"},
        )


async def _read_upload(request: Request) -> bytes:
    if request.headers.get("content-length"):
        try:
            if int(request.headers["content-length"]) > MAX_FILE:
                raise HTTPException(413, "File audio maksimal 16 MB")
        except ValueError:
            raise HTTPException(400, "Invalid upload length")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_FILE:
            raise HTTPException(413, "File audio maksimal 16 MB")
    if len(raw) < 32:
        raise HTTPException(422, "File audio terlalu kecil")
    return bytes(raw)


@router.put("/cues/{cue}")
async def publish_file(cue: str, request: Request):
    check_cue(cue)
    require_admin(request)
    name = _safe_name(request.headers.get("x-uno-sound-name", "sound.mp3"))
    try:
        meta = json.loads(request.headers.get("x-uno-sound-settings", ""))
    except ValueError:
        raise HTTPException(422, "X-UNO-Sound-Settings wajib JSON")
    config = settings(meta)
    data = await _read_upload(request)
    mime, ext = _audio_mime(name, data)
    with LOCK:
        root = storage()
        current = _read(root)
        revision = secrets.token_hex(12)
        filename = f"{cue}-{revision}{ext}"
        dest = root / "audio" / filename
        try:
            with dest.open("xb") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            current["cues"][cue] = {
                **config, "source": "custom", "storageName": filename,
                "fileName": name, "contentType": mime, "revision": revision,
            }
            current["revision"] = secrets.token_hex(12)
            _write(root, current)
            # Keep the active file and one previous version for in-flight clients.
            # Prevent repeated uploads from filling the 512 MB staging volume.
            versions = sorted(
                (old for old in (root / "audio").glob(cue + "-*")
                 if re.fullmatch(re.escape(cue) + r"-[a-f0-9]{24}\.(mp3|wav|m4a|aac|ogg|webm)", old.name)),
                key=lambda old: old.stat().st_mtime_ns, reverse=True,
            )
            for old in versions[2:]:
                old.unlink(missing_ok=True)
        except Exception:
            dest.unlink(missing_ok=True)
            raise
    return {"published": True, "cue": cue, "revision": revision}


@router.patch("/cues/{cue}")
async def publish_settings(cue: str, request: Request):
    check_cue(cue)
    require_admin(request)
    try:
        info = await request.json()
    except ValueError:
        raise HTTPException(422, "Settings JSON invalid")
    with LOCK:
        root = storage()
        data = _read(root)
        previous = data["cues"].get(cue)
        config = settings(info)
        revision = secrets.token_hex(12)
        data["cues"][cue] = ({
            **(previous or {"source": "default", "fileName": ""}),
            **config, "revision": revision,
        })
        data["revision"] = secrets.token_hex(12)
        _write(root, data)
    return {"published": True, "cue": cue, "revision": revision}


@router.delete("/cues/{cue}")
def unpublish(cue: str, request: Request):
    check_cue(cue)
    require_admin(request)
    with LOCK:
        root = storage()
        data = _read(root)
        data["cues"].pop(cue, None)
        data["revision"] = secrets.token_hex(12)
        _write(root, data)
    return {"published": False, "cue": cue}
