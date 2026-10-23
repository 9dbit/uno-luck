"""Activate the reviewed economy preset exactly once.

This maintenance command is intended for an operator shell after a deployment:

    python -m app.activate_economy_preset

It never overwrites a published revision. Further changes continue through the
authenticated Economy Lab so every adjustment remains versioned.
"""
from __future__ import annotations

import time

from . import economy, orbit


def activate(db) -> dict:
    economy.schema(db)
    db.execute("BEGIN IMMEDIATE")
    revision, config = economy.active(db)
    if config is not None:
        db.rollback()
        return {
            "activated": False,
            "revision": revision,
            "rtp_percent": economy.rtp_percent(config),
        }

    rtp = economy.assert_publish_guardrails(economy.PRESET)
    revision = 1
    db.execute(
        "INSERT INTO economy_configs VALUES(?,?,?)",
        (revision, economy.PRESET.model_dump_json(), time.time()),
    )
    db.commit()
    return {"activated": True, "revision": revision, "rtp_percent": rtp}


def main() -> None:
    db = orbit.open_db()
    try:
        result = activate(db)
    finally:
        if db.in_transaction:
            db.rollback()
        db.close()
    action = "activated" if result["activated"] else "unchanged"
    print(
        f'economy {action}: revision={result["revision"]} '
        f'rtp={result["rtp_percent"]:.6f}%'
    )


if __name__ == "__main__":
    main()
