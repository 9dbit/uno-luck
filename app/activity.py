"""Public virtual-Coin activity, with honest separation of live vs QA demo.

Never fabricate real winners, stake volume or personal names. LIVE data come
from settled spins, and use pseudonymous Indonesian aliases derived from
opaque account IDs, not the player's actual profile name. QA-only SIMULATION
is visibly labeled as such on every number/name. No financial transactions.
"""
from __future__ import annotations

import hashlib
import os
import time
from fastapi import APIRouter, Response

from . import spin

router = APIRouter(prefix="/api/activity",tags=["virtual activity"])
ALIASES=(
    "maxwanto","sutrisno","zomanda","rizkyan","wahyudi",
    "baguswan","prasetyo","nugroho","adityan","bayuardi",
    "dimaswan","cahyono","agustina","putriani","fitriani",
    "ratnasari","kurniawan","hidayat","nandang","suryaadi",
    "andrianto","wulandari","arifwanto","fajarwan"
)


def alias(account_id: str) -> str:
    digest=hashlib.blake2b(account_id.encode("utf-8"),digest_size=8).digest()
    name=ALIASES[int.from_bytes(digest,"big")%len(ALIASES)]
    return name[:max(3,len(name)-2)]+"**"


@router.get("/public")
def recent_activity(response: Response):
    response.headers["Cache-Control"]="no-store"
    if os.getenv("UNO_QA_ACTIVITY_DEMO")=="1":
        # Explicit QA demo only, with a fixed illustrative starting counter.
        # It must NEVER be presented as actual real-time betting volume.
        return {
            "mode":"simulation","label":"SIMULASI QA · BUKAN AKTIVITAS PEMAIN",
            "unit":"Coin virtual","demo_start_coin":889980250,
            "epoch_unix":1792774800,
            "as_of":int(time.time()),
            "recent":[
                {"name":"maxw**","payout_coin":88000},
                {"name":"sutr**","payout_coin":242250},
                {"name":"zom**","payout_coin":74000}
            ]
        }
    db=spin.connection()
    try:
        row=db.execute("SELECT COALESCE(SUM(stake),0) AS value FROM spins").fetchone()
        winners=db.execute("""SELECT account_id,payout,created_at FROM spins
            WHERE payout>0 AND stake>0 ORDER BY created_at DESC,id DESC LIMIT 16""").fetchall()
        return {
            "mode":"live","label":"AKTIVITAS TERCATAT · COIN VIRTUAL",
            "unit":"Coin virtual","total_bet_coin":int(row["value"]),
            "as_of":int(time.time()),
            "recent":[{"name":alias(w["account_id"]),
                       "payout_coin":int(w["payout"])}
                      for w in winners]
        }
    finally:
        db.close()
