"""UNO LUCK Color Match SPIN: virtual, non-redeemable game credits only.

Rule source: supplied screenshot establishes exactly one confirmed payout:
three cards sharing a color return 2x the virtual PLACE cost. All other
combinations return zero. This rule is explicitly a staging prototype,
not a claim about an existing game's full paytable.

No monetary value, purchases, paid deposits, withdrawals or exchanges.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/spin", tags=["virtual spin"])
COLORS = ("red", "yellow", "green", "blue")
FACES = tuple(str(n) for n in range(10)) + ("SKIP", "REVERSE", "+2")
COSTS = (10, 25, 50, 100, 250)
INITIAL_COINS = 1000
DAILY_COINS = 250
REFILL_COINS = 1000
COIN_CAP = 1_000_000
COOKIE = "ul_spin_guest"
TZ = ZoneInfo("Asia/Jakarta")
SCHEMA_LOCK = threading.Lock()
INITIALIZED: set[str] = set()


def database_path() -> str:
    return os.getenv("UNO_SPIN_DB_PATH", "/tmp/uno_luck_spin.sqlite3")


def connection() -> sqlite3.Connection:
    path = database_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=8, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=8000")
    with SCHEMA_LOCK:
        if path not in INITIALIZED:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL DEFAULT 'Player',
                    balance INTEGER NOT NULL DEFAULT 1000 CHECK(balance BETWEEN 0 AND 1000000),
                    spins INTEGER NOT NULL DEFAULT 0,
                    color_wins INTEGER NOT NULL DEFAULT 0,
                    last_daily TEXT,
                    last_refill TEXT,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS spins (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES accounts(id),
                    request_id TEXT NOT NULL,
                    stake INTEGER NOT NULL CHECK(stake>0),
                    payout INTEGER NOT NULL CHECK(payout>=0),
                    delta INTEGER NOT NULL,
                    balance_after INTEGER NOT NULL,
                    combo TEXT NOT NULL,
                    cards_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    UNIQUE(account_id,request_id)
                );
                CREATE INDEX IF NOT EXISTS ix_spins_account_time
                  ON spins(account_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS ledger (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES accounts(id),
                    reason TEXT NOT NULL,
                    delta INTEGER NOT NULL,
                    balance_after INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                );
            """)
            INITIALIZED.add(path)
    return db


def now_wib_day() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def utc_timestamp() -> int:
    return int(time.time())


def new_id() -> str:
    return secrets.token_urlsafe(15)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def get_account(request: Request, response: Response, db: sqlite3.Connection) -> sqlite3.Row:
    raw = request.cookies.get(COOKIE, "")
    account = None
    if re.fullmatch(r"[a-zA-Z0-9_-]{30,90}", raw):
        account = db.execute("SELECT * FROM accounts WHERE token_hash=?", (token_hash(raw),)).fetchone()
    if account is not None:
        return account

    token = secrets.token_urlsafe(36)
    account_id = new_id()
    db.execute(
        "INSERT INTO accounts(id,token_hash,display_name,balance,created_at) VALUES(?,?,?,?,?)",
        (account_id, token_hash(token), "Player", INITIAL_COINS, utc_timestamp()),
    )
    db.execute(
        "INSERT INTO ledger(id,account_id,reason,delta,balance_after,created_at) VALUES(?,?,?,?,?,?)",
        (new_id(), account_id, "welcome", INITIAL_COINS, INITIAL_COINS, utc_timestamp()),
    )
    # HTTPS on Railway; the browser can never read the guest token.
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").split(",")[0] == "https"
    response.set_cookie(COOKIE, token, httponly=True, secure=secure, samesite="lax", max_age=60 * 60 * 24 * 90, path="/")
    return db.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()


def guard_write(request: Request) -> None:
    if request.headers.get("x-uno-client") != "spin-ui":
        raise HTTPException(status_code=403, detail="Unsupported client")


def account_view(account: sqlite3.Row, *, date: str | None = None) -> dict:
    today = date or now_wib_day()
    return {
        "name": account["display_name"],
        "balance": account["balance"],
        "level": 1 + account["spins"] // 30,
        "spins": account["spins"],
        "wins": account["color_wins"],
        "daily_available": account["last_daily"] != today,
        "refill_available": account["last_refill"] != today,
    }


def rules_view() -> dict:
    return {
        "ruleset": "color-match-v1-staging",
        "virtual_only": True,
        "cost_options": COSTS,
        "default_cost": 25,
        "starting_balance": INITIAL_COINS,
        "daily_bonus": DAILY_COINS,
        "refill_bonus": REFILL_COINS,
        "paytable": [{"id": "COLOR_MATCH", "description": "3 kartu memiliki warna sama", "multiplier": 2},
                     {"id": "NO_MATCH", "description": "Warna tidak semua sama", "multiplier": 0}],
        "probability_color_match": 0.0625,
        "note": "Empat warna dipilih secara independen dan merata. Koin demo tidak punya nilai uang.",
    }


def fresh_cards() -> list[dict]:
    # Independent color draws, cryptographically secure; no client controls outcome.
    return [{"color": secrets.choice(COLORS), "face": secrets.choice(FACES)} for _ in range(3)]


def classify(cards: list[dict], stake: int) -> tuple[str, int]:
    matched = len({card["color"] for card in cards}) == 1
    return ("COLOR_MATCH", stake * 2) if matched else ("NO_MATCH", 0)


def spin_history(db: sqlite3.Connection, account_id: str, limit: int = 20) -> list[dict]:
    rows = db.execute(
        "SELECT id,stake,payout,delta,combo,cards_json,created_at FROM spins WHERE account_id=? ORDER BY created_at DESC,rowid DESC LIMIT ?",
        (account_id, limit),
    ).fetchall()
    return [{"id": row["id"], "stake": row["stake"], "payout": row["payout"],
             "delta": row["delta"], "combo": row["combo"], "cards": json.loads(row["cards_json"]),
             "created_at": row["created_at"]} for row in rows]


def account_from_session(request: Request, db: sqlite3.Connection) -> sqlite3.Row:
    raw = request.cookies.get(COOKIE, "")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{30,90}", raw):
        raise HTTPException(401, "Open the game to create a guest session")
    account = db.execute("SELECT * FROM accounts WHERE token_hash=?", (token_hash(raw),)).fetchone()
    if account is None:
        raise HTTPException(401, "Session expired. Reload the game")
    return account


class PlaceInput(BaseModel):
    stake: int = Field(default=25)
    request_id: str = Field(min_length=8, max_length=80)


class ProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=20)


@router.get("/state")
def state(request: Request, response: Response):
    db = connection()
    try:
        account = get_account(request, response, db)
        response.headers["Cache-Control"] = "no-store"
        return {"account": account_view(account), "rules": rules_view(), "history": spin_history(db, account["id"], 8), "last": spin_history(db, account["id"], 1)}
    finally:
        db.close()


@router.get("/rules")
def rules():
    return rules_view()


@router.get("/history")
def history(request: Request, response: Response):
    db = connection()
    try:
        account = account_from_session(request, db)
        response.headers["Cache-Control"] = "no-store"
        return {"items": spin_history(db, account["id"], 30)}
    finally:
        db.close()


@router.post("/place")
def place(request: Request, response: Response, payload: PlaceInput):
    guard_write(request)
    if type(payload.stake) is not int or payload.stake not in COSTS:
        raise HTTPException(422, "Invalid PLACE cost")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{8,80}", payload.request_id):
        raise HTTPException(422, "Invalid request_id")
    db = connection()
    try:
        db.execute("BEGIN IMMEDIATE")
        account = account_from_session(request, db)
        prior = db.execute("SELECT * FROM spins WHERE account_id=? AND request_id=?",
                           (account["id"], payload.request_id)).fetchone()
        if prior is not None:
            db.commit()
            response.headers["Cache-Control"] = "no-store"
            return {"id": prior["id"], "cards": json.loads(prior["cards_json"]), "stake": prior["stake"],
                    "payout": prior["payout"], "delta": prior["delta"], "combo": prior["combo"],
                    "balance": account["balance"], "replayed": True,
                    "account": account_view(account)}
        if account["balance"] < payload.stake:
            db.rollback()
            raise HTTPException(409, "Koin demo tidak cukup. Klaim hadiah atau refill gratis.")
        # Cap rapid scripted calls without trusting client-side buttons.
        last = db.execute("SELECT created_at FROM spins WHERE account_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",
                          (account["id"],)).fetchone()
        if last and time.time() - last["created_at"] < 0.25:
            db.rollback()
            raise HTTPException(429, "Tunggu sebentar sebelum PLACE berikutnya")
        cards = fresh_cards()
        combo, payout = classify(cards, payload.stake)
        delta = payout - payload.stake
        balance = min(COIN_CAP, account["balance"] + delta)
        credited_delta = balance - account["balance"]
        spin_id = new_id()
        created = time.time()
        db.execute("UPDATE accounts SET balance=?, spins=spins+1, color_wins=color_wins+? WHERE id=?",
                   (balance, int(combo == "COLOR_MATCH"), account["id"]))
        db.execute("INSERT INTO spins(id,account_id,request_id,stake,payout,delta,balance_after,combo,cards_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (spin_id, account["id"], payload.request_id, payload.stake, payout, credited_delta, balance, combo,
                    json.dumps(cards, separators=(",", ":")), created))
        db.execute("INSERT INTO ledger(id,account_id,reason,delta,balance_after,created_at) VALUES(?,?,?,?,?,?)",
                   (new_id(), account["id"], "spin:" + combo, credited_delta, balance, created))
        db.commit()
        response.headers["Cache-Control"] = "no-store"
        updated = db.execute("SELECT * FROM accounts WHERE id=?", (account["id"],)).fetchone()
        return {"id": spin_id, "cards": cards, "stake": payload.stake, "payout": payout,
                "delta": credited_delta, "combo": combo, "balance": balance, "replayed": False,
                "account": account_view(updated)}
    except Exception:
        if db.in_transaction:
            db.rollback()
        raise
    finally:
        db.close()


def bonus(request: Request, response: Response, *, kind: str, field: str, amount: int) -> dict:
    guard_write(request)
    db = connection()
    try:
        db.execute("BEGIN IMMEDIATE")
        account = account_from_session(request, db)
        date = now_wib_day()
        if account[field] == date:
            db.rollback()
            raise HTTPException(409, "Bonus ini sudah diklaim hari ini (WIB)")
        after = min(COIN_CAP, account["balance"] + amount)
        actual = after - account["balance"]
        # Field name is chosen only by server-side code, not user input.
        db.execute(f"UPDATE accounts SET balance=?, {field}=? WHERE id=?", (after, date, account["id"]))
        db.execute("INSERT INTO ledger(id,account_id,reason,delta,balance_after,created_at) VALUES(?,?,?,?,?,?)",
                   (new_id(), account["id"], kind, actual, after, utc_timestamp()))
        db.commit()
        account = db.execute("SELECT * FROM accounts WHERE id=?", (account["id"],)).fetchone()
        response.headers["Cache-Control"] = "no-store"
        return {"credited": actual, "account": account_view(account)}
    except Exception:
        if db.in_transaction:
            db.rollback()
        raise
    finally:
        db.close()


@router.post("/daily")
def claim_daily(request: Request, response: Response):
    return bonus(request, response, kind="daily", field="last_daily", amount=DAILY_COINS)


@router.post("/refill")
def claim_refill(request: Request, response: Response):
    return bonus(request, response, kind="free_refill", field="last_refill", amount=REFILL_COINS)


@router.patch("/profile")
def profile(request: Request, response: Response, payload: ProfileInput):
    guard_write(request)
    name = " ".join("".join(c for c in payload.name if c.isprintable() and c not in "<>/\\").split())
    if not 1 <= len(name) <= 20:
        raise HTTPException(422, "Nama harus 1–20 karakter")
    db = connection()
    try:
        db.execute("BEGIN IMMEDIATE")
        account = account_from_session(request, db)
        db.execute("UPDATE accounts SET display_name=? WHERE id=?", (name, account["id"]))
        db.commit()
        account = db.execute("SELECT * FROM accounts WHERE id=?", (account["id"],)).fetchone()
        response.headers["Cache-Control"] = "no-store"
        return {"account": account_view(account)}
    finally:
        db.close()
