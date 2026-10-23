"""Transparent, replay-safe Auto Play promotion for virtual-only credits.

A paid Auto batch includes ten additional free rounds and five disclosed
promotional coin grants. Round results always use the ordinary independent RNG;
the promotional awards are separate from winning-card classifications.
"""
from __future__ import annotations

import json
import re
import secrets
import sqlite3
import time
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from . import spin, economy

router = APIRouter(prefix="/api/auto", tags=["virtual auto play"])
FREE_ROUNDS = 10
PROMO_REWARDS = 5
PROMO_PERCENTS = (30, 50, 100)
PAID_ROUND_CHOICES = (1, 3, 5, 10)


class StartRequest(BaseModel):
    request_id: str = Field(min_length=12, max_length=80)
    stake: int = Field(ge=10)
    paid_rounds: int = Field(ge=1, le=10)


def schema(db: sqlite3.Connection) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS auto_sessions (
        id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL REFERENCES accounts(id),
        request_id TEXT NOT NULL,
        stake INTEGER NOT NULL,
        paid_rounds INTEGER NOT NULL,
        free_rounds INTEGER NOT NULL,
        completed_rounds INTEGER NOT NULL DEFAULT 0,
        gift_slots_json TEXT NOT NULL,
        gift_rates_json TEXT NOT NULL,
        promo_credited INTEGER NOT NULL DEFAULT 0,
        created_at REAL NOT NULL,
        finished_at REAL,
        UNIQUE(account_id, request_id)
    )""")
    db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS ix_auto_account_active
               ON auto_sessions(account_id) WHERE finished_at IS NULL""")


def active(db: sqlite3.Connection, account_id: str):
    return db.execute(
        "SELECT * FROM auto_sessions WHERE account_id=? AND finished_at IS NULL",
        (account_id,)
    ).fetchone()


def by_id(db: sqlite3.Connection, account_id: str, session_id: str):
    return db.execute(
        "SELECT * FROM auto_sessions WHERE account_id=? AND id=?",
        (account_id, session_id)
    ).fetchone()


def award_coin(row, position: int) -> int:
    """Guaranteed PROMO amount for a completed free-spin position, if scheduled."""
    slots = json.loads(row["gift_slots_json"])
    rates = json.loads(row["gift_rates_json"])
    if position not in slots:
        return 0
    index = slots.index(position)
    basis = row["stake"] * row["paid_rounds"]
    return int((Decimal(basis) * Decimal(rates[index]) / Decimal(100))
               .quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def remaining_liability(row) -> int:
    completed_free = max(0, row["completed_rounds"] - row["paid_rounds"])
    return sum(award_coin(row, slot) for slot in json.loads(row["gift_slots_json"])
               if slot > completed_free)


def view(row) -> dict | None:
    if row is None:
        return None
    total = row["paid_rounds"] + row["free_rounds"]
    return {
        "id": row["id"],
        "stake": row["stake"],
        "paid_rounds": row["paid_rounds"],
        "free_rounds": row["free_rounds"],
        "completed_rounds": row["completed_rounds"],
        "rounds_remaining": max(0, total - row["completed_rounds"]),
        "free_remaining": max(0, total - max(row["completed_rounds"], row["paid_rounds"])),
        "promotional_rewards": PROMO_REWARDS,
        "promo_credited_coin": row["promo_credited"],
        "reserved_bonus_coin": remaining_liability(row),
        "finished": row["finished_at"] is not None,
    }


@router.get("/state")
def status(request: Request, response: Response):
    from . import orbit
    db = orbit.open_db()
    try:
        account = spin.get_account(request, response, db)
        response.headers["Cache-Control"] = "no-store"
        return {"session": view(active(db, account["id"]))}
    finally:
        db.close()


@router.post("/start")
def start(request: Request, response: Response, payload: StartRequest):
    spin.guard_write(request)
    if not re.fullmatch(r"[A-Za-z0-9_-]{12,80}", payload.request_id):
        raise HTTPException(422, "ID permintaan tidak valid")
    if payload.paid_rounds not in PAID_ROUND_CHOICES:
        raise HTTPException(422, "Pilih 1, 3, 5, atau 10 ronde berbayar")
    from . import orbit
    db = orbit.open_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        account = spin.account_from_session(request, db)
        duplicate = db.execute(
            "SELECT * FROM auto_sessions WHERE account_id=? AND request_id=?",
            (account["id"], payload.request_id)
        ).fetchone()
        if duplicate:
            db.commit()
            return {"session": view(duplicate), "created": False}
        existing = active(db, account["id"])
        if existing:
            db.commit()
            return {"session": view(existing), "created": False, "resumed": True}
        if orbit.current_round(db, account["id"]):
            raise HTTPException(409, "Selesaikan ronde yang sudah dimulai sebelum AUTO")
        _, config = economy.active(db)
        options = config.stake_options if config else spin.COSTS
        if payload.stake not in options:
            raise HTTPException(422, "Nilai BET tidak tersedia")
        if account["balance"] < payload.stake * payload.paid_rounds:
            raise HTTPException(409, "Saldo tidak cukup untuk ronde AUTO berbayar")
        positions = sorted(secrets.SystemRandom().sample(range(1, FREE_ROUNDS + 1), PROMO_REWARDS))
        rates = [secrets.choice(PROMO_PERCENTS) for _ in positions]
        session_id = spin.new_id()
        db.execute(
            """INSERT INTO auto_sessions
            (id,account_id,request_id,stake,paid_rounds,free_rounds,
             gift_slots_json,gift_rates_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (session_id,account["id"],payload.request_id,payload.stake,
             payload.paid_rounds,FREE_ROUNDS,json.dumps(positions),
             json.dumps(rates),time.time())
        )
        new_row = by_id(db, account["id"], session_id)
        db.commit()
        response.headers["Cache-Control"] = "no-store"
        return {"session": view(new_row), "created": True,
                "gift": {"free_spins": FREE_ROUNDS, "voice": "Free Spiinnn!",
                         "disclosure": "5 bonus PROMO dijamin; posisi acak. Hasil kartu tetap acak."}}
    except Exception:
        if db.in_transaction:
            db.rollback()
        raise
    finally:
        db.close()


def round_terms(row) -> tuple[int, bool]:
    """Stake to debit and whether the upcoming round uses a free voucher."""
    total = row["paid_rounds"] + row["free_rounds"]
    index = row["completed_rounds"]
    if index >= total or row["finished_at"] is not None:
        raise HTTPException(409, "Sesi AUTO sudah selesai")
    free = index >= row["paid_rounds"]
    return (0 if free else row["stake"]), free


def complete_round(db: sqlite3.Connection, row, account, timestamp: float) -> tuple[int, int]:
    """Credit a disclosed promotion, separately from the card-game payout.

    The caller already holds BEGIN IMMEDIATE and has finished exactly one round.
    """
    index = row["completed_rounds"] + 1
    free_index = index - row["paid_rounds"]
    expected = award_coin(row, free_index) if free_index > 0 else 0
    credited = min(max(0, spin.COIN_CAP - account["balance"]), expected)
    if credited:
        balance = account["balance"] + credited
        db.execute("UPDATE accounts SET balance=? WHERE id=?", (balance, account["id"]))
        db.execute(
            "INSERT INTO ledger(id,account_id,reason,delta,balance_after,created_at) VALUES(?,?,?,?,?,?)",
            (spin.new_id(), account["id"], "auto_promotional_gift", credited, balance, timestamp)
        )
    finished = index == row["paid_rounds"] + row["free_rounds"]
    db.execute(
        """UPDATE auto_sessions SET completed_rounds=?,
           promo_credited=promo_credited+?, finished_at=?
           WHERE id=? AND completed_rounds=?""",
        (index, credited, timestamp if finished else None, row["id"], index-1)
    )
    return credited, expected
