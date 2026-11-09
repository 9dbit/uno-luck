"""Sandbox-only central wallet. Native intents survive timeouts and restarts.

SQLite must live on a persistent, single-instance volume. Never share these
sessions with the guest ledger. Unfinished three-pick rounds settle after 15m
using the outcome already committed before the first reservation attempt.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, StrictInt
from .agency_wallet import AgencyWallet, AgencyWalletError
from .native_locks import operation_lock, active_lock_count
from .deployment_identity import initialize_bound_database, open_bound_database, public_identity, canonical_path, requested_identity, require_play, validate_redeemed, cookie_value, runtime_health

router = APIRouter(prefix='/api/agency', tags=['Soft Tech sandbox'])
COOKIE = 'uno_agency'
SCHEMA_LOCK = threading.Lock()
_initialized = set()
DEADLINE = 15 * 60

def enabled():
    return os.environ.get('AGENCY_WALLET_MODE', '') == 'sandbox'

def validate_config():
    mode = os.environ.get('AGENCY_WALLET_MODE', '')
    if mode not in ('', 'sandbox'):
        raise RuntimeError('Only sandbox agency integration is supported')
    if enabled():
        path = os.environ.get('UNO_AGENCY_DB_PATH', '')
        if not Path(path).is_absolute():
            raise RuntimeError('UNO_AGENCY_DB_PATH must point to a persistent volume')
        wallet()
        if os.getenv('ENGINE_RESTORE_OBJECT_KEY') or os.getenv('ENGINE_RESTORE_OBJECT'):
            from scripts.native_backup import restore_from_remote
            restore_from_remote(canonical_path(path), 'uno', requested_identity('uno-luck', path))
        db = db_open(initialize=True)
        db.close()

def wallet():
    return AgencyWallet(os.environ['AGENCY_WALLET_ORIGIN'], os.environ['AGENCY_WALLET_KEY_ID'],
                        os.environ['AGENCY_WALLET_SECRET'], allow_local=os.getenv('AGENCY_WALLET_LOCAL_QA') == '1')

def db_open(*, initialize=False):
    path = canonical_path(os.environ['UNO_AGENCY_DB_PATH'])
    os.environ['UNO_AGENCY_DB_PATH'] = path
    opener = initialize_bound_database if initialize else open_bound_database
    db = opener(path, 'uno-luck')
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=30000')
    with SCHEMA_LOCK:
        if path not in _initialized:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA synchronous=FULL')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS agency_launches (
              token_hash TEXT PRIMARY KEY, request_id TEXT NOT NULL, cookie_hash TEXT NOT NULL UNIQUE,
              session_json TEXT, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS agency_rounds (
              id TEXT PRIMARY KEY, actor TEXT NOT NULL, session_json TEXT NOT NULL, stake INTEGER NOT NULL,
              cards_json TEXT NOT NULL, combo TEXT NOT NULL, tier INTEGER, payout INTEGER NOT NULL,
              picked INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'intent', central_id TEXT,
              created_at REAL NOT NULL, finished_at REAL, error_status INTEGER);
            CREATE UNIQUE INDEX IF NOT EXISTS agency_active ON agency_rounds(actor)
              WHERE state NOT IN ('failed','settled') OR (state='settled' AND picked<3);
            CREATE INDEX IF NOT EXISTS agency_actor_history
              ON agency_rounds(actor,state,created_at DESC,payout);
            CREATE TABLE IF NOT EXISTS agency_requests (
              actor TEXT NOT NULL, request_id TEXT NOT NULL, round_id TEXT NOT NULL REFERENCES agency_rounds(id),
              phase INTEGER NOT NULL, stake INTEGER NOT NULL, PRIMARY KEY(actor,request_id));
            ''')
            _initialized.add(path)
    return db

def sha(raw):
    return hashlib.sha256(raw.encode()).hexdigest()

def guard(request):
    require_play()
    if not enabled():
        raise HTTPException(404, 'Integrasi agen tidak diaktifkan')
    if request.headers.get('x-uno-client') != 'spin-ui' or request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'Unsupported client')

def remote(action, payload):
    try:
        return wallet().request(action, payload)
    except AgencyWalletError:
        raise
    except Exception:
        raise HTTPException(503, 'Koneksi wallet terputus. Ulangi permintaan yang sama; hasil ronde tetap tersimpan.') from None

class LaunchInput(BaseModel):
    token: str = Field(min_length=30, max_length=120, pattern=r'^[A-Za-z0-9_-]+$')

@router.post('/launch')
def launch(request: Request, response: Response, payload: LaunchInput):
    guard(request)
    # Deterministic secret-derived credentials recover a lost response without
    # storing the raw launch token or a browser-readable session credential.
    token_hash = sha(payload.token)
    cookie = cookie_value(payload.token, 'uno-luck', os.environ['UNO_AGENCY_DB_PATH'])
    rid = 'uno-redeem-' + token_hash
    db = db_open()
    try:
        db.execute('INSERT OR IGNORE INTO agency_launches VALUES(?,?,?,?,?)', (token_hash, rid, sha(cookie), None, time.time()))
        row = db.execute('SELECT * FROM agency_launches WHERE token_hash=?', (token_hash,)).fetchone()
        # Revalidate even a local cached redemption: central expiry is authoritative.
        s = remote('redeem', {'token': payload.token, 'request_id': row['request_id']})
        validate_redeemed(s, 'uno-luck', os.environ['UNO_AGENCY_DB_PATH'])
        if s.get('game') != 'uno-luck' or type(s.get('coin_scale')) is not int or not 0 <= s['coin_scale'] <= 8:
            raise HTTPException(409, 'UNO provider requires uno-luck and supported currency precision')
        db.execute('UPDATE agency_launches SET session_json=? WHERE token_hash=?', (json.dumps(s), token_hash))
        secure = request.url.scheme == 'https' or request.headers.get('x-forwarded-proto', '').split(',')[0] == 'https'
        response.set_cookie(COOKIE, cookie, secure=secure, httponly=True, samesite='strict', max_age=86400, path='/')
        response.headers['Cache-Control'] = 'no-store'
        return {'ok': True, 'mode': os.getenv('AGENCY_ENVIRONMENT','sandbox'), 'wallet': 'soft-tech'}
    except AgencyWalletError as exc:
        raise HTTPException(exc.status if exc.status < 500 else 503, 'Launch ditolak wallet. Buka kembali game dari website agen.') from None
    finally:
        db.close()

def session(db, request):
    require_play()
    raw = request.cookies.get(COOKIE, '')
    if not re.fullmatch('[a-f0-9]{64}', raw):
        raise HTTPException(401, 'Buka game dari website agen untuk melanjutkan')
    row = db.execute('SELECT * FROM agency_launches WHERE cookie_hash=? AND created_at>?', (sha(raw), time.time()-86400)).fetchone()
    if not row or not row['session_json']:
        raise HTTPException(401, 'Sesi agen tidak tersedia. Buka kembali dari website agen.')
    s = json.loads(row['session_json'])
    validate_redeemed(s, 'uno-luck', os.environ['UNO_AGENCY_DB_PATH'])
    return s, s['tenant_id'] + ':' + s['player_id']

def row_get(db, rid):
    return db.execute('SELECT * FROM agency_rounds WHERE id=?', (rid,)).fetchone()

def advance(db, rid):
    if db.in_transaction:
        raise RuntimeError('Native wallet callbacks require a committed intent')
    row = row_get(db, rid)
    if not row: raise HTTPException(404, 'Ronde tidak tersedia')
    with operation_lock('player:' + row['actor']), operation_lock('round:' + rid):
        return _advance_unlocked(db, rid)

def _advance_unlocked(db, rid):
    """Called with a per-round process lock, AFTER the durable intent was committed.
    No response may reveal cards until reserve is confirmed. An unknown response
    leaves the same intent for retry; no local refund or second outcome exists.
    """
    r = row_get(db, rid)
    s = json.loads(r['session_json'])
    if r['state'] == 'failed':
        raise HTTPException(r['error_status'], 'Reservasi ditolak wallet; buka kembali dari website agen jika sesi habis.')
    if r['state'] == 'intent':
        try:
            central = remote('reserve', {'tenant_id': s['tenant_id'], 'session_id': s['session_id'],
                              'round_ref': r['id'], 'stake': str(r['stake'] * 10**s['coin_scale']), 'max_payout': str(r['stake'] * 200 * 10**s['coin_scale'])})
        except AgencyWalletError as exc:
            # A definitive rejection cannot have created this identical reserve.
            # Unknown transport/5xx errors remain pending, including lost responses.
            if 400 <= exc.status < 500 and exc.status not in (408, 429):
                db.execute("UPDATE agency_rounds SET state='failed',error_status=? WHERE id=?", (exc.status, rid))
                db.commit()
            raise HTTPException(exc.status if exc.status < 500 else 503, 'Reservasi wallet belum berhasil. Periksa saldo, sesi dan risk pool agen.') from None
        db.execute("UPDATE agency_rounds SET central_id=?,state='reserved',picked=1 WHERE id=?", (central['id'], rid))
        r = row_get(db, rid)
    if r['state'] in ('reserved', 'settling') and (r['picked'] == 3 or time.time() >= r['created_at'] + DEADLINE):
        try:
            remote('settle', {'tenant_id': s['tenant_id'], 'round_id': r['central_id'], 'payout': str(r['payout'] * 10**s['coin_scale']),
                             'evidence': 'uno-orbit-agency-v1:' + sha(r['cards_json'] + ':' + str(r['tier']) + ':' + str(r['stake']))})
        except AgencyWalletError:
            raise HTTPException(503, 'Settlement menunggu rekonsiliasi wallet; hasil ronde sudah tersimpan.') from None
        db.execute("UPDATE agency_rounds SET state='settled',picked=3,finished_at=? WHERE id=?", (time.time(), rid))
    return row_get(db, rid)

def active(db, actor):
    # Match the existing partial-index predicate so SQLite can use its actor key.
    return db.execute("SELECT * FROM agency_rounds WHERE actor=? AND state NOT IN ('failed','settled') ORDER BY created_at LIMIT 1", (actor,)).fetchone()

def snapshot(db, s, actor):
    try:
        balance = remote('status', {'tenant_id': s['tenant_id'], 'session_id': s['session_id']})
    except AgencyWalletError:
        raise HTTPException(503, 'Saldo pusat belum tersedia. Coba kembali tanpa mengulangi ronde baru.') from None
    count = db.execute("SELECT count(*) n,sum(CASE WHEN payout>0 THEN 1 ELSE 0 END) wins FROM agency_rounds WHERE actor=? AND state='settled'", (actor,)).fetchone()
    return {'id': sha(actor), 'name': 'Player Soft Tech', 'balance': int(balance['balance']) / (10**s['coin_scale']), 'reserved': int(balance['reserved']) / (10**s['coin_scale']),
            'spins': count['n'], 'wins': count['wins'] or 0, 'level': 1, 'daily_available': False, 'refill_available': False,
            'wallet': 'soft-tech', 'simulation': True}

def state(request, response):
    from . import orbit
    db = db_open()
    try:
        s, actor = session(db, request)
        with operation_lock('player:' + actor):
            row = active(db, actor)
            if row:
                row = advance(db, row['id'])
            hist = db.execute("SELECT * FROM agency_rounds WHERE actor=? AND state='settled' ORDER BY created_at DESC LIMIT 8", (actor,)).fetchall()
            rules = orbit.public_rules() | {'coin_cap': None, 'wallet': 'soft-tech', 'abandonment_seconds': DEADLINE,
               'note': 'Sandbox Soft Tech: satu biaya untuk tiga kartu. Ronde yang ditinggalkan diselesaikan otomatis setelah 15 menit dengan hasil tersimpan. Tidak ada refill lokal. Saldo dan batas mengikuti Soft Tech.'}
            response.headers['Cache-Control'] = 'no-store'
            return {'account': snapshot(db, s, actor), 'round': view_round(row) if row and row['state'] != 'settled' else None,
                    'recent': [view_round(r) for r in hist], 'rules': rules}
    finally:
        db.close()

class PickInput(BaseModel):
    request_id: str = Field(min_length=12, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    stake: StrictInt = 25
    expected_phase: StrictInt = Field(ge=1, le=3)
    round_id: str | None = None

def pick(request, response, payload):
    from . import orbit, spin
    guard(request)
    try:
        p = PickInput.model_validate(payload)
    except Exception:
        raise HTTPException(422, 'request_id, stake dan fase ronde harus valid') from None
    if p.stake not in spin.COSTS:
        raise HTTPException(422, 'Biaya SPIN tidak valid')
    db = db_open()
    try:
        s, actor = session(db, request)
        with operation_lock('player:' + actor):
            db.execute('BEGIN IMMEDIATE')
            duplicate = db.execute('SELECT * FROM agency_requests WHERE actor=? AND request_id=?', (actor, p.request_id)).fetchone()
            if duplicate:
                if duplicate['stake'] != p.stake or duplicate['phase'] != p.expected_phase or (p.expected_phase > 1 and p.round_id != duplicate['round_id']):
                    raise HTTPException(409, 'Idempotency key digunakan dengan payload berbeda')
                rid, phase = duplicate['round_id'], duplicate['phase']
            else:
                r = active(db, actor)
                if r:
                    if r['state'] != 'reserved' or p.expected_phase != r['picked'] + 1 or p.round_id != r['id'] or p.stake != r['stake']:
                        raise HTTPException(409, 'Ronde berubah. Muat ulang dan lanjutkan ronde tersimpan.')
                    rid, phase = r['id'], p.expected_phase
                    db.execute('UPDATE agency_rounds SET picked=?,state=? WHERE id=?', (phase, 'settling' if phase == 3 else 'reserved', rid))
                else:
                    if p.expected_phase != 1 or p.round_id:
                        raise HTTPException(409, 'Tidak ada ronde yang menunggu fase ini')
                    cards = orbit.choose_cards()
                    tier = orbit.classify_rank(cards)
                    combo = 'COLOR_MATCH' if tier is not None else 'NO_MATCH'
                    payout = p.stake * orbit.CELEBRATIONS[tier]['multiplier'] if tier else 0
                    rid, phase = 'uno-' + secrets.token_hex(24), 1
                    db.execute('INSERT INTO agency_rounds(id,actor,session_json,stake,cards_json,combo,tier,payout,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                        (rid, actor, json.dumps(s), p.stake, json.dumps(cards, separators=(',', ':')), combo, tier, payout, time.time()))
                db.execute('INSERT INTO agency_requests VALUES(?,?,?,?,?)', (actor, p.request_id, rid, phase, p.stake))
            # Critical boundary: record outcome and requested phase before networking.
            db.commit()
            r = advance(db, rid)
            response.headers['Cache-Control'] = 'no-store'
            return {'round': view_round(r, phase), 'account': snapshot(db, s, actor), 'replayed': bool(duplicate)}
    finally:
        db.close()

def recover_due():
    """Single replica worker shares per-round locks with browser retries."""
    if os.getenv('AGENCY_ENVIRONMENT', 'sandbox') == 'production': return
    db = db_open()
    try:
        ids = [r['id'] for r in db.execute("SELECT id FROM agency_rounds WHERE state NOT IN ('failed','settled') AND created_at<? LIMIT 20", (time.time()-DEADLINE,))]
        for rid in ids:
            try:
                advance(db, rid)
            except Exception:
                if db.in_transaction:
                    db.rollback()
                # No outcome/token/secret in logs. The durable row is retried later.
    finally:
        db.close()

def worker(stop):
    while not stop.wait(30):
        try:
            recover_due()
        except sqlite3.Error:
            # Do not terminate the worker on a transient volume/locking failure.
            # Health checks will report database unavailability separately.
            continue

@router.get('/mode')
def mode(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    return {'agency': enabled(), 'environment': os.getenv('AGENCY_ENVIRONMENT','sandbox') if enabled() else None, 'play_enabled': os.getenv('AGENCY_ENVIRONMENT','sandbox')!='production'}

@router.get('/state')
def state_route(request: Request, response: Response):
    if not enabled():
        raise HTTPException(404, 'Integrasi agen tidak diaktifkan')
    return state(request, response)

@router.post('/pick')
def pick_route(request: Request, response: Response, payload: PickInput):
    return pick(request, response, payload.model_dump())


def view_round(row, phase=None):
    """Reuse the live engine presentation and actual-card rank classification."""
    from . import orbit
    return orbit.view_round(dict(row) | {'rules_version': orbit.RULES_VERSION}, phase) if row else None
