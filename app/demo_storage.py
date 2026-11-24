"""Initialize an independent demo volume from an immutable public audio snapshot."""
import hashlib
import json
import os
import shutil
from pathlib import Path


def prepare_demo_storage():
    from .orbit import open_db
    source = Path(__file__).parent / "published_audio"
    manifest = json.loads((source / "manifest.json").read_text())
    target = Path(os.environ["UNO_SOUND_STORAGE_DIR"])
    target.mkdir(parents=True, exist_ok=True)
    (target / "audio").mkdir(exist_ok=True)
    for info in manifest["cues"].values():
        name = info["storageName"]
        asset = source / "audio" / name
        if hashlib.sha256(asset.read_bytes()).hexdigest() != info["sha256"]:
            raise RuntimeError("Published sound snapshot checksum mismatch")
        dest = target / "audio" / name
        if not dest.exists():
            shutil.copyfile(asset, dest)
        if hashlib.sha256(dest.read_bytes()).hexdigest() != info["sha256"]:
            raise RuntimeError("Demo sound volume checksum mismatch")
    # No remote staging reads at runtime, and no overwrite of an existing manifest.
    if not (target / "manifest.json").exists():
        with (target / "manifest.json").open("x") as output:
            json.dump(manifest, output)
            output.flush()
            os.fsync(output.fileno())
    existing = json.loads((target / "manifest.json").read_text())
    if existing != manifest:
        raise RuntimeError("Demo sound manifest differs from approved release")
    db = open_db()
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("Demo database integrity check failed")
        # Force full durability for the isolated single-replica SQLite runtime.
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
    finally:
        db.close()
