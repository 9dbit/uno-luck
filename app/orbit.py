"""Three-click UNO LUCK circular card spin. Koin are virtual and non-redeemable.

The three selected cards are chosen server-side at round creation and revealed
one by one. 80% of newly generated rounds have three cards of one color; the
remaining 20% never have a complete color match. One round costs one stake,
and pays twice that stake on a color match after its third pick.
"""
from __future__ import annotations

import json
import re
import secrets
import time
import sqlite3
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from . import spin

router = APIRouter(prefix="/api/orbit", tags=["UNO LUCK Orbit"])
WIN_PERCENT = 80
FACES = spin.FACES
COLORS = spin.COLORS


class PickRequest(BaseModel):
    request_id: str = Field(min_length=12, max_length=80)
    stake: int = 25


def create_schema(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS orbit_rounds (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL REFERENCES accounts(id),
            start_key TEXT NOT NULL,
            stake INTEGER NOT NULL,
            cards_json TEXT NOT NULL,
            picked INTEGER NOT NULL CHECK(picked BETWEEN 1 AND 3),
            payout INTEGER NOT NULL DEFAULT 0,
            combo TEXT NOT NULL,
            created_at REAL NOT NULL,
            finished_at REAL,
            UNIQUE(account_id,start_key)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ix_orbit_account_active
            ON orbit_rounds(account_id) WHERE picked < 3;
        CREATE TABLE IF NOT EXISTS orbit_requests (
            account_id TEXT NOT NULL REFERENCES accounts(id),
            request_id TEXT NOT NULL,
            round_id TEXT NOT NULL REFERENCES orbit_rounds(id),
            selected_count INTEGER NOT NULL,
            PRIMARY KEY(account_id,request_id)
        );
    """)


def open_db() -> sqlite3.Connection:
    db = spin.connection()
    with spin.SCHEMA_LOCK:
        if spin.database_path() not in _initialized:
            create_schema(db)
            _initialized.add(spin.database_path())
    return db


_initialized: set[str] = set()


def choose_cards() -> list[dict]:
    """Secure Bernoulli draw; winning and losing branches cannot overlap."""
    winner = secrets.randbelow(100) < WIN_PERCENT
    colors = [secrets.choice(COLORS) for _ in range(3)]
    if winner:
        colors = [colors[0]] * 3
    elif len(set(colors)) == 1:
        remaining = [c for c in COLORS if c != colors[0]]
        colors[2] = secrets.choice(remaining)
    return [dict(color=c, face=secrets.choice(FACES)) for c in colors]


def current_round(db: sqlite3.Connection, aid: str):
    return db.execute("SELECT * FROM orbit_rounds WHERE account_id=? AND picked<3 LIMIT 1", (aid,)).fetchone()


def view_round(round_row, phase: int | None = None) -> dict | None:
    if round_row is None:
        return None
    picked = round_row['picked'] if phase is None else min(phase, round_row['picked'])
    cards = json.loads(round_row['cards_json'])[:picked]
    complete = picked == 3
    return {
        'id': round_row['id'], 'picked': picked, 'stake': round_row['stake'],
        'cards': cards, 'complete': complete,
        'combo': round_row['combo'] if complete else None,
        'payout': round_row['payout'] if complete else None,
        'delta': round_row['payout'] - round_row['stake'] if complete else None,
    }


def public_rules() -> dict:
    return {
        'mode': 'three-pick-orbit', 'virtual_only': True, 'win_probability_percent': WIN_PERCENT,
        'stake_options': spin.COSTS,
        'payout_multiplier': 2,
        'spin_sequence': ['kiri','tengah','kanan'],
        'note': 'Satu ronde = tiga SPIN, satu biaya di awal. Warna sama menang 2x. Semua koin virtual tanpa nilai uang. Peluang 80% adalah aturan game demo, bukan pernyataan tentang UNO resmi.',
    }


@router.get('/state')
def state(request: Request, response: Response):
    db = open_db()
    try:
        account = spin.get_account(request,response,db)
        row = current_round(db, account['id'])
        hist = spin.spin_history(db, account['id'], 8)
        response.headers['Cache-Control'] = 'no-store'
        return {'account': spin.account_view(account), 'round': view_round(row),
                'recent': hist, 'rules': public_rules()}
    finally:
        db.close()


def validate_input(payload: PickRequest) -> None:
    if not re.fullmatch('[A-Za-z0-9_-]{12,80}',payload.request_id):
        raise HTTPException(422,'request_id tidak valid')
    if type(payload.stake) is not int or payload.stake not in spin.COSTS:
        raise HTTPException(422,'Biaya SPIN tidak valid')


@router.post('/pick')
def pick(request: Request, response: Response, payload: PickRequest):
    spin.guard_write(request)
    validate_input(payload)
    db = open_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        acct = spin.account_from_session(request,db)
        aid = acct['id']
        duplicate=db.execute('SELECT round_id,selected_count FROM orbit_requests WHERE account_id=? AND request_id=?',
                             (aid,payload.request_id)).fetchone()
        if duplicate:
            row=db.execute('SELECT * FROM orbit_rounds WHERE id=?', (duplicate['round_id'],)).fetchone()
            db.commit()
            response.headers['Cache-Control']='no-store'
            return {'round':view_round(row,duplicate['selected_count']),
                    'account':spin.account_view(acct),'replayed':True}
        row=current_round(db,aid)
        stamp=time.time()
        if row is None:
            if acct['balance'] < payload.stake:
                raise HTTPException(409,'Koin tidak cukup. Klaim hadiah atau refill gratis.')
            cards=choose_cards()
            combo,payout=spin.classify(cards,payload.stake)
            rid=spin.new_id()
            db.execute('INSERT INTO orbit_rounds(id,account_id,start_key,stake,cards_json,picked,combo,created_at) VALUES(?,?,?,?,?,?,?,?)',
                       (rid,aid,payload.request_id,payload.stake,json.dumps(cards,separators=(',',':')),1,combo,stamp))
            new_balance=acct['balance']-payload.stake
            db.execute('UPDATE accounts SET balance=? WHERE id=?',(new_balance,aid))
            db.execute('INSERT INTO ledger(id,account_id,reason,delta,balance_after,created_at) VALUES(?,?,?,?,?,?)',
                       (spin.new_id(),aid,'orbit_stake',-payload.stake,new_balance,stamp))
            picked=1
        else:
            # The stake is fixed on spin #1. Subsequent requests cannot change it.
            if payload.stake != row['stake']:
                raise HTTPException(409,'Biaya ronde sedang berlangsung tidak dapat diganti')
            rid=row['id']
            picked=row['picked']+1
            if picked > 3:
                raise HTTPException(409,'Ronde ini sudah selesai')
            if picked == 3:
                payout=2*row['stake'] if row['combo']=='COLOR_MATCH' else 0
                new_balance=min(spin.COIN_CAP,acct['balance']+payout)
                credited=new_balance-acct['balance']
                db.execute('UPDATE orbit_rounds SET picked=3,payout=?,finished_at=? WHERE id=?',(credited,stamp,rid))
                db.execute('UPDATE accounts SET balance=?,spins=spins+1,color_wins=color_wins+? WHERE id=?',
                           (new_balance,int(row['combo']=='COLOR_MATCH'),aid))
                db.execute('INSERT INTO ledger(id,account_id,reason,delta,balance_after,created_at) VALUES(?,?,?,?,?,?)',
                           (spin.new_id(),aid,'orbit_payout',credited,new_balance,stamp))
                db.execute('INSERT INTO spins(id,account_id,request_id,stake,payout,delta,balance_after,combo,cards_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                           (rid,aid,row['start_key'],row['stake'],credited,credited-row['stake'],new_balance,row['combo'],row['cards_json'],stamp))
            else:
                db.execute('UPDATE orbit_rounds SET picked=? WHERE id=?',(picked,rid))
        db.execute('INSERT INTO orbit_requests(account_id,request_id,round_id,selected_count) VALUES(?,?,?,?)',
                   (aid,payload.request_id,rid,picked))
        db.commit()
        updated=db.execute('SELECT * FROM accounts WHERE id=?',(aid,)).fetchone()
        updated_row=db.execute('SELECT * FROM orbit_rounds WHERE id=?',(rid,)).fetchone()
        response.headers['Cache-Control']='no-store'
        return {'round':view_round(updated_row,picked),'account':spin.account_view(updated),'replayed':False}
    except Exception:
        if db.in_transaction: db.rollback()
        raise
    finally:
        db.close()
